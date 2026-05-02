"""Small shared utilities for experiment runners.

This module intentionally stays narrow: it owns only generic path, TOML, and
logging helpers that are reused by multiple runners. Tool-specific config
parsing stays in the runner that executes it so the orchestration code remains
easy to follow without chasing abstractions across files.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from typing import TextIO


REPO_ROOT = Path(__file__).resolve().parents[2]
_DURATION_TOKEN_RE = re.compile(r"(?P<amount>\d+)(?P<unit>[hmsHMS])")


@dataclass(frozen=True)
class BenchmarkWorkspace:
    """Temporary workspace that copies one benchmark and symlinks the rest.

    The benchmark build scripts expect the repository layout around them to stay
    intact because they derive `repo_root` from their own path. To isolate one
    benchmark without cloning the whole repository, runners create a temporary
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
    tool_id: str
    module_name: str
    benchmark_arg: str | None = "--benchmarks"
    results_dir_arg: str | None = "--results-dir"
    tmp_dir_arg: str | None = "--tmp-dir"

    def build_worker_argv(
        self,
        base_args: list[str],
        *,
        benchmark_csv: str | None,
        results_dir: Path,
        tmp_dir: str,
    ) -> list[str]:
        argv = list(base_args)
        if self.tmp_dir_arg is not None:
            argv.extend([self.tmp_dir_arg, tmp_dir])
        if self.results_dir_arg is not None:
            argv.extend([self.results_dir_arg, str(results_dir)])
        if self.benchmark_arg is not None and benchmark_csv:
            argv.extend([self.benchmark_arg, benchmark_csv])
        return argv


@dataclass
class LaunchedProcess:
    tag: str
    process: multiprocessing.Process
    reader: threading.Thread
    log_path: Path


class _QueueWriter:
    encoding = "utf-8"

    def __init__(self, output_queue: object) -> None:
        self.output_queue = output_queue

    def write(self, text: str) -> int:
        if text:
            self.output_queue.put(text)
        return len(text)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


def _run_module_worker(
    module_name: str,
    argv: list[str],
    env: dict[str, str],
    cwd: str,
    output_queue: object,
) -> None:
    writer = _QueueWriter(output_queue)
    sys.stdout = writer
    sys.stderr = writer
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
    except BaseException:
        traceback.print_exc()
        exit_code = 1
    finally:
        output_queue.put(None)

    raise SystemExit(exit_code)


def _forward_worker_output(
    process: multiprocessing.Process,
    tag: str,
    log_path: Path,
    output_queue: object,
    *,
    verbose: bool,
) -> None:
    with log_path.open("w", encoding="utf-8", buffering=1) as log_handle:
        while True:
            try:
                chunk = output_queue.get(timeout=0.1)
            except queue.Empty:
                if process.exitcode is not None:
                    break
                continue
            if chunk is None:
                break
            log_handle.write(chunk)
            if verbose:
                print(f"[{tag}] {chunk}", end="")

        while True:
            try:
                chunk = output_queue.get_nowait()
            except queue.Empty:
                break
            if chunk is None:
                continue
            log_handle.write(chunk)
            if verbose:
                print(f"[{tag}] {chunk}", end="")


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
    ctx = multiprocessing.get_context("spawn")
    output_queue = ctx.Queue()
    effective_log_path = log_path or cwd / f"{tag.replace('/', '_').replace(' ', '_')}.log"
    process = ctx.Process(
        target=_run_module_worker,
        args=(module_name, argv, dict(env or os.environ), str(cwd), output_queue),
        name=tag,
    )
    process.start()
    reader = threading.Thread(
        target=_forward_worker_output,
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
    )


def worker_log_path(destination_root: Path, copy_index: int) -> Path:
    log_root = destination_root / "_worker_logs"
    log_root.mkdir(parents=True, exist_ok=True)
    return log_root / f"{copy_index}.log"


def wait_for_processes(processes: list[LaunchedProcess]) -> int:
    overall = 0
    for launched in processes:
        launched.process.join()
        return_code = launched.process.exitcode if launched.process.exitcode is not None else 1
        status = "done" if return_code == 0 else f"failed with exit code {return_code}"
        print(f"[{launched.tag}] {status}; log: {launched.log_path}")
        if return_code != 0:
            overall = 1
    for launched in processes:
        launched.reader.join()
    return overall


def terminate_processes(processes: list[LaunchedProcess]) -> None:
    for launched in processes:
        if launched.process.is_alive():
            print(f"[{launched.tag}] stopping; log: {launched.log_path}", file=sys.stderr)
            launched.process.terminate()
    for launched in processes:
        if launched.process.is_alive():
            launched.process.join(timeout=2)
            if launched.process.is_alive():
                print(f"[{launched.tag}] killing after timeout; log: {launched.log_path}", file=sys.stderr)
                launched.process.kill()
    for launched in processes:
        launched.reader.join(timeout=1)


def resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def prepare_benchmark_workspace(benchmark_root: str | Path, tmp_dir: str | Path = "/tmp") -> BenchmarkWorkspace:
    benchmark_source = resolve_repo_path(benchmark_root).resolve()
    if not benchmark_source.is_dir():
        raise ValueError(f"benchmark root does not exist: {benchmark_source}")
    try:
        benchmark_relative = benchmark_source.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ValueError(f"benchmark root must stay inside the repository: {benchmark_source}") from error

    temp_root = Path(tmp_dir).expanduser().resolve()
    temp_root.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(
        tempfile.mkdtemp(prefix=f"benchmark-{benchmark_source.name}.", dir=str(temp_root))
    )

    current_source = REPO_ROOT
    current_workspace = workspace_root
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

        shutil.copytree(source_child, workspace_child, symlinks=True)
        return BenchmarkWorkspace(
            root=workspace_root,
            benchmark_root=workspace_child,
        )

    raise AssertionError(f"failed to materialize benchmark workspace for {benchmark_source}")


def benchmark_csv_from_config(value: object, label: str) -> str | None:
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
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a TOML table")
    return value


def expect_array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be an array")
    return value


def expect_string(table: dict[str, object], key: str, location: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string")
    return value


def optional_string(table: dict[str, object], key: str, location: str) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string when present")
    return value


def optional_string_list(table: dict[str, object], key: str, location: str) -> tuple[str, ...]:
    value = table.get(key)
    if value is None:
        return ()
    values = expect_array(value, f"{location}.{key}")
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"{location}.{key} must contain only non-empty strings")
    return tuple(values)


@dataclass
class ExperimentContext:
    """Shared logging and subprocess helper for experiment runner scripts.

    The experiment entrypoints all need the same behavior: print progress to the
    terminal, optionally mirror that output into a shared `output.log`, and run
    subprocesses while streaming their combined stdout/stderr line by line.
    This class keeps that behavior consistent across the different runners.
    """

    output_handle: TextIO | None = None

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
        for line in process.stdout:
            rendered = line.rstrip("\n")
            print(rendered)
            if self.output_handle is not None:
                self.output_handle.write(f"{rendered}\n")
                self.output_handle.flush()
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
            return_code = process.wait()

        if check and return_code != 0:
            raise SystemExit(return_code)
        return return_code
