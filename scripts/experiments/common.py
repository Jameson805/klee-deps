"""Small shared utilities for experiment runners.

This module intentionally stays narrow: it owns only generic path, TOML, and
logging helpers that are reused by multiple runners. Tool-specific config
parsing stays in the runner that executes it so the orchestration code remains
easy to follow without chasing abstractions across files.
"""

from __future__ import annotations

from dataclasses import dataclass
import errno
import importlib
import multiprocessing
import os
import queue
import shutil
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import traceback
from types import TracebackType
from typing import Callable, TextIO


REPO_ROOT = Path(__file__).resolve().parents[2]
_DURATION_TOKEN_RE = re.compile(r"(?P<amount>\d+)(?P<unit>[hmsHMS])")
_TRANSIENT_BENCHMARK_DIR_NAMES = {"build"}


@dataclass(frozen=True)
class BenchmarkWorkspace:
    """Temporary workspace that copies one benchmark and symlinks the rest.

    The shared benchmark builder still compiles in-place inside each benchmark's
    source tree, so runners isolate one benchmark by creating a temporary
    workspace that mirrors the repo tree, copies only the target benchmark
    subtree, and symlinks all other top-level paths back to the original repo.
    """

    root: Path
    benchmark_root: Path

    def __enter__(self) -> BenchmarkWorkspace:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def resolve_repo_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.root / candidate

    def resolve_code_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate

        workspace_candidate = self.root / candidate
        if workspace_candidate.exists():
            return workspace_candidate

        benchmark_candidate = self.benchmark_root / candidate
        if benchmark_candidate.exists():
            return benchmark_candidate

        return workspace_candidate


@dataclass(frozen=True)
class CampaignTool:
    """Describe how the campaign layer launches one runner module.

    The campaign orchestrator treats runners as black-box CLIs with a small set
    of conventional arguments. Keeping that contract explicit here avoids hard-
    coding per-tool argument wiring inside the campaign scripts.
    """

    tool_id: str
    module_name: str
    benchmark_arg: str | None = "--benchmarks"
    results_dir_arg: str | None = "--results-dir"
    tmp_dir_arg: str | None = "--tmp-dir"
    case_parallel_arg: str | None = None

    def build_worker_argv(
        self,
        base_args: list[str],
        *,
        benchmark_csv: str | None,
        results_dir: Path,
        tmp_dir: str,
        case_parallelism: int | None = None,
    ) -> list[str]:
        """Append the standard campaign-managed CLI arguments for one worker."""
        argv = list(base_args)
        if self.tmp_dir_arg is not None:
            argv.extend([self.tmp_dir_arg, tmp_dir])
        if self.results_dir_arg is not None:
            argv.extend([self.results_dir_arg, str(results_dir)])
        if self.benchmark_arg is not None and benchmark_csv:
            argv.extend([self.benchmark_arg, benchmark_csv])
        if self.case_parallel_arg is not None and case_parallelism is not None:
            argv.extend([self.case_parallel_arg, str(case_parallelism)])
        return argv


@dataclass
class LaunchedProcess:
    """Track one spawned worker process plus its output-forwarding thread."""

    tag: str
    process: multiprocessing.Process
    reader: threading.Thread
    log_path: Path
    output_queue: object | None = None


class _QueueWriter:
    encoding = "utf-8"

    def __init__(self, queue_handle: object) -> None:
        self.queue_handle = queue_handle

    def write(self, text: str) -> int:
        if text:
            try:
                if hasattr(self.queue_handle, "put"):
                    self.queue_handle.put(text)
                else:
                    self.queue_handle.send(text)
            except (BrokenPipeError, OSError):
                return len(text)
        return len(text)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


def redirect_output_to_queue(output_queue: object) -> None:
    """Redirect stdout and stderr into a multiprocessing queue or pipe."""
    writer = _QueueWriter(output_queue)
    sys.stdout = writer
    sys.stderr = writer


def restore_output_streams(stdout: TextIO, stderr: TextIO) -> None:
    """Restore stdout and stderr after queue redirection."""
    sys.stdout = stdout
    sys.stderr = stderr


def forward_worker_output(
    process: multiprocessing.Process,
    tag: str,
    log_path: Path,
    output_queue: object,
    *,
    verbose: bool = False,
) -> None:
    def receive_with_timeout(timeout: float) -> tuple[bool, str | None]:
        if hasattr(output_queue, "get"):
            try:
                return True, output_queue.get(timeout=timeout)
            except queue.Empty:
                return False, None

        if not output_queue.poll(timeout):
            return False, None
        try:
            return True, output_queue.recv()
        except EOFError:
            return True, None

    def receive_nowait() -> tuple[bool, str | None]:
        if hasattr(output_queue, "get_nowait"):
            try:
                return True, output_queue.get_nowait()
            except queue.Empty:
                return False, None

        if not output_queue.poll(0):
            return False, None
        try:
            return True, output_queue.recv()
        except EOFError:
            return False, None

    with log_path.open("w", encoding="utf-8", buffering=1) as log_handle:
        while True:
            has_chunk, chunk = receive_with_timeout(0.1)
            if not has_chunk:
                if process.exitcode is not None:
                    break
                continue
            if chunk is None:
                break
            log_handle.write(chunk)
            if verbose:
                print(f"[{tag}] {chunk}", end="")

        while True:
            has_chunk, chunk = receive_nowait()
            if not has_chunk:
                break
            if chunk is None:
                continue
            log_handle.write(chunk)
            if verbose:
                print(f"[{tag}] {chunk}", end="")


def _run_module_worker(
    module_name: str,
    argv: list[str],
    env: dict[str, str],
    cwd: str,
    output_queue: object,
) -> None:
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    redirect_output_to_queue(output_queue)
    exit_code = 0
    try:
        os.environ.clear()
        os.environ.update(env)
        os.chdir(cwd)

        module = importlib.import_module(module_name)
        main_func = getattr(module, "main", None)
        if not callable(main_func):
            raise AttributeError(f"{module_name} does not expose callable main(argv=None)")

        result = main_func(argv)
        if result is None:
            exit_code = 0
        elif isinstance(result, int):
            exit_code = result
        else:
            raise TypeError(
                f"{module_name}.main returned unsupported exit code type {type(result).__name__}"
            )
    except SystemExit as error:
        if error.code is None:
            exit_code = 0
        elif isinstance(error.code, int):
            exit_code = error.code
        else:
            print(error.code, file=sys.stderr)
            exit_code = 1
    except KeyboardInterrupt:
        exit_code = 130
    except BaseException:
        traceback.print_exc()
        exit_code = 1
    finally:
        restore_output_streams(original_stdout, original_stderr)
        try:
            if hasattr(output_queue, "put"):
                output_queue.put(None)
            else:
                output_queue.send(None)
        except Exception:
            pass
        try:
            output_queue.close()
        except Exception:
            pass

    raise SystemExit(exit_code)


def launch_output_captured_process(
    tag: str,
    target: Callable[..., None],
    target_args: tuple[object, ...],
    *,
    log_path: Path,
    verbose: bool = False,
) -> LaunchedProcess:
    """Spawn a worker process and stream its combined output into ``log_path``."""
    ctx = multiprocessing.get_context("spawn")
    output_queue, child_output_queue = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=target,
        args=(*target_args, child_output_queue),
        name=tag,
    )
    process.start()
    child_output_queue.close()
    reader = threading.Thread(
        target=forward_worker_output,
        args=(process, tag, log_path, output_queue),
        kwargs={"verbose": verbose},
        daemon=True,
    )
    reader.start()
    return LaunchedProcess(
        tag=tag,
        process=process,
        reader=reader,
        log_path=log_path,
        output_queue=output_queue,
    )


def execute_output_captured_worker(
    output_queue: object | None,
    worker: Callable[[], object | None],
) -> None:
    """Run one worker body while mirroring its output into the parent queue."""
    if output_queue is None:
        worker()
        return

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    redirect_output_to_queue(output_queue)
    exit_code = 0
    try:
        result = worker()
        if result is None:
            exit_code = 0
        elif isinstance(result, int):
            exit_code = result
        else:
            raise TypeError(
                f"worker returned unsupported exit code type {type(result).__name__}"
            )
    except SystemExit as error:
        if error.code is None:
            exit_code = 0
        elif isinstance(error.code, int):
            exit_code = error.code
        else:
            print(error.code, file=sys.stderr)
            exit_code = 1
    except KeyboardInterrupt:
        exit_code = 130
    except BaseException:
        traceback.print_exc()
        exit_code = 1
    finally:
        restore_output_streams(original_stdout, original_stderr)
        try:
            if hasattr(output_queue, "put"):
                output_queue.put(None)
            else:
                output_queue.send(None)
        except Exception:
            pass
        try:
            output_queue.close()
        except Exception:
            pass

    raise SystemExit(exit_code)


def launch_prefixed_module(
    tag: str,
    module_name: str,
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = REPO_ROOT,
    log_path: Path | None = None,
    verbose: bool = False,
) -> LaunchedProcess:
    """Run another Python module in a spawned worker with captured output."""
    ctx = multiprocessing.get_context("spawn")
    output_queue, child_output_queue = ctx.Pipe(duplex=False)
    effective_log_path = log_path or cwd / f"{tag.replace('/', '_').replace(' ', '_')}.log"
    process = ctx.Process(
        target=_run_module_worker,
        args=(module_name, argv, dict(env or os.environ), str(cwd), child_output_queue),
        name=tag,
    )
    process.start()
    child_output_queue.close()
    reader = threading.Thread(
        target=forward_worker_output,
        args=(process, tag, effective_log_path, output_queue),
        kwargs={"verbose": verbose},
        daemon=True,
    )
    reader.start()
    return LaunchedProcess(
        tag=tag,
        process=process,
        reader=reader,
        log_path=effective_log_path,
        output_queue=output_queue,
    )


def cleanup_launched_process(launched: LaunchedProcess, *, close_queue: bool = True) -> None:
    """Release multiprocessing IPC/process handles to avoid resource leaks."""
    if close_queue and launched.output_queue is not None:
        try:
            launched.output_queue.close()
        except Exception:
            pass
        if hasattr(launched.output_queue, "join_thread"):
            try:
                launched.output_queue.join_thread()
            except Exception:
                pass
    try:
        launched.process.close()
    except Exception:
        pass


def worker_log_path(destination_root: Path, copy_index: int) -> Path:
    """Return the standard per-worker log path for one destination root."""
    log_root = destination_root / "_worker_logs"
    log_root.mkdir(parents=True, exist_ok=True)
    return log_root / f"{copy_index}.log"


def _process_is_alive(process: multiprocessing.Process) -> bool:
    try:
        return process.is_alive()
    except ValueError:
        # multiprocessing.Process raises when the handle has already been closed.
        return False


def _process_join(process: multiprocessing.Process, timeout: float | None = None) -> None:
    try:
        if timeout is None:
            process.join()
        else:
            process.join(timeout=timeout)
    except ValueError:
        return None


def _process_exitcode(process: multiprocessing.Process) -> int:
    try:
        code = process.exitcode
    except ValueError:
        code = None
    return code if code is not None else 1


def wait_for_processes(processes: list[LaunchedProcess]) -> int:
    """Wait for all launched workers and return a combined exit status."""
    overall = 0
    for launched in processes:
        _process_join(launched.process)
        return_code = _process_exitcode(launched.process)
        status = "done" if return_code == 0 else f"failed with exit code {return_code}"
        print(f"[{launched.tag}] {status}; log: {launched.log_path}")
        if return_code != 0:
            overall = 1
    for launched in processes:
        launched.reader.join()
        cleanup_launched_process(launched)
    return overall


def terminate_processes(processes: list[LaunchedProcess]) -> None:
    """Stop all active worker processes, escalating from terminate to kill."""
    for launched in processes:
        if _process_is_alive(launched.process):
            print(f"[{launched.tag}] stopping; log: {launched.log_path}", file=sys.stderr)
            launched.process.terminate()
    for launched in processes:
        if _process_is_alive(launched.process):
            _process_join(launched.process, timeout=2)
            if _process_is_alive(launched.process):
                print(f"[{launched.tag}] killing after timeout; log: {launched.log_path}", file=sys.stderr)
                launched.process.kill()
    for launched in processes:
        if _process_is_alive(launched.process):
            _process_join(launched.process, timeout=2)
    for launched in processes:
        launched.reader.join(timeout=1)
        # Closing Queue semaphores before a spawned child is fully dead can
        # make that child fail in SemLock._rebuild during interpreter startup.
        cleanup_launched_process(launched, close_queue=not _process_is_alive(launched.process))


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve a repository-relative path against ``REPO_ROOT``."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def prepare_benchmark_workspace(benchmark_root: str | Path, tmp_dir: str | Path = "/tmp") -> BenchmarkWorkspace:
    """Create an isolated temporary workspace for one benchmark subtree.

    Benchmarks derive paths from their location in the repository, so runners
    cannot simply point them at arbitrary build directories. This helper copies
    the selected benchmark subtree and symlinks the rest of the repository.
    """
    benchmark_source = resolve_repo_path(benchmark_root).resolve()
    if not benchmark_source.is_dir():
        raise ValueError(f"benchmark root does not exist: {benchmark_source}")
    try:
        benchmark_relative = benchmark_source.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ValueError(f"benchmark root must stay inside the repository: {benchmark_source}") from error

    temp_root = Path(tmp_dir).expanduser().resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    try:
        workspace_root = Path(
            tempfile.mkdtemp(prefix=f"benchmark-{benchmark_source.name}.", dir=str(temp_root))
        )
    except OSError as error:
        if error.errno == errno.ENOSPC:
            raise OSError(
                errno.ENOSPC,
                f"no space left in temporary workspace root {temp_root}; rerun with --tmp-dir on a filesystem with more free space",
            ) from error
        raise

    current_source = REPO_ROOT
    current_workspace = workspace_root

    def ignore_transient_entries(_directory: str, entry_names: list[str]) -> set[str]:
        return {
            entry_name
            for entry_name in entry_names
            if entry_name in _TRANSIENT_BENCHMARK_DIR_NAMES
        }

    for depth, part in enumerate(benchmark_relative.parts):
        source_child = current_source / part
        workspace_child = current_workspace / part
        is_leaf = depth == len(benchmark_relative.parts) - 1

        if not is_leaf:
            workspace_child.mkdir(parents=True, exist_ok=True)
            for sibling in current_source.iterdir():
                if sibling.name == part:
                    continue
                sibling_workspace = current_workspace / sibling.name
                if sibling_workspace.exists():
                    continue
                sibling_workspace.symlink_to(sibling, target_is_directory=sibling.is_dir())
            current_source = source_child
            current_workspace = workspace_child
            continue
        try:
            shutil.copytree(
                source_child,
                workspace_child,
                symlinks=True,
                ignore=ignore_transient_entries,
            )
        except OSError as error:
            shutil.rmtree(workspace_root, ignore_errors=True)
            if error.errno == errno.ENOSPC:
                raise OSError(
                    errno.ENOSPC,
                    f"no space left while copying benchmark workspace into {workspace_root}; rerun with --tmp-dir on a filesystem with more free space",
                ) from error
            raise
        return BenchmarkWorkspace(
            root=workspace_root,
            benchmark_root=workspace_child,
        )

    raise AssertionError(f"failed to materialize benchmark workspace for {benchmark_source}")


def benchmark_csv_from_config(value: object, label: str) -> str | None:
    """Normalize a TOML benchmark selection value to the runner CSV format."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if not value:
            return None
        if not all(isinstance(item, str) for item in value):
            raise ValueError(f"{label} must be a string or array of strings")
        return ",".join(value)
    raise ValueError(f"{label} must be a string or array of strings")


def duration_to_seconds(value: str | int, location: str) -> int:
    """Parse the short duration syntax used by campaign and runner CLIs."""
    if isinstance(value, bool):
        raise ValueError(f"{location} must be a positive duration")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{location} must be a positive duration")
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{location} must be a non-empty duration string like '60', '1m', or '2h30m'"
        )

    text = value.strip().replace(" ", "")
    if text.isdigit():
        seconds = int(text)
        if seconds <= 0:
            raise ValueError(f"{location} must be a positive duration")
        return seconds

    multipliers = {"h": 3600, "m": 60, "s": 1}
    total_seconds = 0
    position = 0
    while position < len(text):
        match = _DURATION_TOKEN_RE.match(text, position)
        if match is None:
            raise ValueError(
                f"{location} must use h/m/s suffixes like '1m', '4h', or '2h30m'"
            )
        total_seconds += int(match.group("amount")) * multipliers[match.group("unit").lower()]
        position = match.end()

    if total_seconds <= 0:
        raise ValueError(f"{location} must be a positive duration")
    return total_seconds


def expect_table(value: object, location: str) -> dict[str, object]:
    """Require a TOML table-like value and return it as a dictionary."""
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a TOML table")
    return value


def expect_array(value: object, location: str) -> list[object]:
    """Require a TOML array-like value and return it as a list."""
    if not isinstance(value, list):
        raise ValueError(f"{location} must be an array")
    return value


def expect_string(table: dict[str, object], key: str, location: str) -> str:
    """Read one required non-empty string field from a TOML table."""
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string")
    return value


def optional_string(table: dict[str, object], key: str, location: str) -> str | None:
    """Read one optional non-empty string field from a TOML table."""
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string when present")
    return value


def optional_string_list(table: dict[str, object], key: str, location: str) -> tuple[str, ...]:
    """Read one optional array of non-empty strings from a TOML table."""
    value = table.get(key)
    if value is None:
        return ()
    values = expect_array(value, f"{location}.{key}")
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"{location}.{key} must contain only non-empty strings")
    return tuple(values)


@dataclass(frozen=True)
class ExpandedBenchmarkCase:
    """One generic benchmark case produced from targets, configs, and filters."""

    variant_id: str
    tool_id: str
    target_id: str
    config_id: str
    public_mode: str
    target_location: str
    config_location: str
    target_table: dict[str, object]
    config_table: dict[str, object]

    @property
    def output_target(self) -> str:
        if not self.target_id:
            return self.target_id
        if self.variant_id == "default":
            return self.target_id
        return f"{self.target_id}_{self.variant_id}"

    @property
    def target_suffix(self) -> str:
        return f"_{self.output_target}" if self.output_target else ""


def matches_case_exclusion(
    exclusion_table: dict[str, object],
    *,
    variant_id: str,
    target_id: str,
    config_id: str,
    tool_id: str,
    location: str,
) -> bool:
    """Return whether one exclusion entry suppresses a candidate case."""
    exclusion_variant = optional_string(exclusion_table, "variant", location)
    exclusion_target = optional_string(exclusion_table, "target", location)
    exclusion_config = optional_string(exclusion_table, "config", location)
    exclusion_tool = optional_string(exclusion_table, "tool", location)
    if all(value is None for value in (exclusion_variant, exclusion_target, exclusion_config, exclusion_tool)):
        raise ValueError(f"{location} must constrain at least one of variant/target/config/tool")
    if exclusion_variant not in (None, variant_id):
        return False
    if exclusion_target not in (None, target_id):
        return False
    if exclusion_config not in (None, config_id):
        return False
    if exclusion_tool not in (None, tool_id):
        return False
    return True


def expand_benchmark_cases(benchmark_definition, tool_id: str) -> list[ExpandedBenchmarkCase]:
    """Expand the shared benchmark matrix into tool-filtered case candidates.

    This centralizes the repeated ``targets x configs x tools x exclusions``
    expansion logic so new runners only need to map an expanded case into their
    own tool-specific inputs and outputs.
    """
    if "configs" not in benchmark_definition.extra_config:
        return []

    location = benchmark_definition.config_location
    variant_id = benchmark_definition.variant_id
    raw_target_entries = benchmark_definition.extra_config.get("targets")
    configs = expect_array(benchmark_definition.extra_config.get("configs"), f"{location}.configs")
    exclusions = expect_array(benchmark_definition.extra_config.get("exclusions") or [], f"{location}.exclusions")

    parsed_targets: list[tuple[str, str, set[str], str, dict[str, object]]] = []
    if raw_target_entries is None:
        parsed_targets.append(
            (
                "",
                "",
                set(benchmark_definition.tools),
                f"{location}.targets[default]",
                {},
            )
        )
    else:
        for target_index, raw_target in enumerate(expect_array(raw_target_entries, f"{location}.targets")):
            target_location = f"{location}.targets[{target_index}]"
            target_table = expect_table(raw_target, target_location)
            target_id = expect_string(target_table, "target", target_location)
            parsed_targets.append(
                (
                    target_id,
                    set(optional_string_list(target_table, "tools", target_location) or benchmark_definition.tools),
                    target_location,
                    target_table,
                )
            )

    cases: list[ExpandedBenchmarkCase] = []
    benchmark_tools = set(benchmark_definition.tools)
    for target_id, target_tools, target_location, target_table in parsed_targets:
        for config_index, raw_config in enumerate(configs):
            config_location = f"{location}.configs[{config_index}]"
            config_table = expect_table(raw_config, config_location)
            config_id = expect_string(config_table, "config", config_location)
            config_tools = set(optional_string_list(config_table, "tools", config_location) or benchmark_definition.tools)
            case_tools = target_tools & config_tools & benchmark_tools
            if tool_id not in case_tools:
                continue
            if any(
                matches_case_exclusion(
                    expect_table(raw_exclusion, f"{location}.exclusions[{index}]"),
                    variant_id=variant_id,
                    target_id=target_id,
                    config_id=config_id,
                    tool_id=tool_id,
                    location=f"{location}.exclusions[{index}]",
                )
                for index, raw_exclusion in enumerate(exclusions)
            ):
                continue
            cases.append(
                ExpandedBenchmarkCase(
                    variant_id=variant_id,
                    tool_id=tool_id,
                    target_id=target_id,
                    config_id=config_id,
                    public_mode=expect_string(config_table, "public_mode", config_location),
                    target_location=target_location,
                    config_location=config_location,
                    target_table=target_table,
                    config_table=config_table,
                )
            )
    return cases


@dataclass
class ExperimentContext:
    """Shared logging and subprocess helper for experiment runner scripts.

    The experiment entrypoints all need the same behavior: print progress to the
    terminal, optionally mirror that output into a shared `output.log`, and run
    subprocesses while streaming their combined stdout/stderr line by line.
    This class keeps that behavior consistent across the different runners.
    """

    output_handle: TextIO | None = None

    @staticmethod
    def _stop_streamed_process(process: subprocess.Popen[str]) -> None:
        try:
            process.terminate()
        except ProcessLookupError:
            return
        except Exception:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except ProcessLookupError:
                return
            except Exception:
                return
            try:
                process.wait(timeout=2)
            except Exception:
                return

    def log(self, message: str = "") -> None:
        """Write a message to stdout and mirror it to the shared output log."""
        print(message)
        if self.output_handle is not None:
            self.output_handle.write(f"{message}\n")
            self.output_handle.flush()

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> int:
        """Run a command and stream its merged output to the active log sinks.

        Returns the process exit code. When `check` is true, a non-zero exit
        code terminates the current runner via `SystemExit`.
        """
        self.log(f"$ {shlex.join(command)}")
        process = subprocess.Popen(
            command,
            cwd=cwd or REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                rendered = line.rstrip("\n")
                print(rendered)
                if self.output_handle is not None:
                    self.output_handle.write(f"{rendered}\n")
                    self.output_handle.flush()
        except KeyboardInterrupt:
            self._stop_streamed_process(process)
            raise
        return_code = process.wait()
        if check and return_code != 0:
            raise SystemExit(return_code)
        return return_code



    def run_and_capture(
        self,
        command: list[str],
        *,
        log_path: Path,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        prefix: str | None = None,
    ) -> int:
        """Run a command like `run`, and also save raw output to `log_path`.

        `prefix` is applied only to the mirrored terminal/shared-log output; the
        per-command log file keeps the original subprocess output unchanged.
        """
        self.log(f"$ {shlex.join(command)}")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as handle:
            process = subprocess.Popen(
                command,
                cwd=cwd or REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            try:
                for line in process.stdout:
                    rendered = line.rstrip("\n")
                    if prefix:
                        rendered = f"{prefix}{rendered}"
                    print(rendered)
                    if self.output_handle is not None:
                        self.output_handle.write(f"{rendered}\n")
                        self.output_handle.flush()
                    handle.write(line)
                    handle.flush()
            except KeyboardInterrupt:
                self._stop_streamed_process(process)
                raise
            return_code = process.wait()

        if check and return_code != 0:
            raise SystemExit(return_code)
        return return_code
