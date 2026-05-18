#!/usr/bin/env python3
"""Run the self-composition baseline and normalize its logs.

Self-composition differs from the other runners because its raw finding format
is the stdout log itself. This runner therefore builds the benchmark, timestamps
the live KLEE stream into a per-case log, and then converts that log into the
shared JSON schema, optionally replaying each positive finding.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import resource
import signal
import shlex
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import (
    CampaignTool,
    ExperimentContext,
    LaunchedProcess,
    REPO_ROOT,
    expand_benchmark_cases,
    execute_output_captured_worker,
    expect_array,
    expect_string,
    expect_table,
    launch_output_captured_process,
    optional_string,
    prepare_benchmark_workspace,
    resolve_case_template,
    resolve_repo_path,
    terminate_processes,
    wait_for_processes,
)
from tools.converters.self_comp_log_to_json import convert_self_comp_log
from tools.shared.experiment_registry import (
    build_for_tool,
    canonical_case_id,
    canonical_case_title,
    definition,
    definition_for_path,
    format_benchmark_selector,
    normalized_case_output_metadata,
    selected_benchmarks,
)

# Keep timestamps in the live log stream so the converter can recover event
# timing without needing another wrapper script on disk.
TIMESTAMP_CODE = "import sys,time\nfor raw in sys.stdin.buffer:\n    line = raw.decode('utf-8', errors='replace')\n    sys.stdout.write(f'[{time.time():.3f}] {line}')\n    sys.stdout.flush()"


CAMPAIGN_TOOL = CampaignTool(tool_id="self_comp", module_name=__name__)


def _load_self_comp_cases(benchmark_definition) -> list[dict[str, object]]:
    """Load self-composition cases, preferring explicit overrides when present."""
    raw_cases = benchmark_definition.extra_config.get("self_comp_cases")
    if raw_cases is not None:
        return list(expect_array(raw_cases, f"{benchmark_definition.config_location}.self_comp_cases"))

    cases: list[dict[str, object]] = []
    for expanded_case in expand_benchmark_cases(benchmark_definition, "self_comp"):
        case_title = canonical_case_title(
            benchmark_definition.library_id,
            benchmark_definition.variant_id,
            expanded_case.target_id,
            expanded_case.config_id,
        )
        case_id = canonical_case_id(
            benchmark_definition.library_id,
            benchmark_definition.variant_id,
            expanded_case.target_id,
            expanded_case.config_id,
        )
        case = {
            "title": f"{case_title} Self-Comp",
            "bitcode": resolve_case_template(
                benchmark_definition,
                expanded_case,
                "self_comp_bitcode",
                f"{benchmark_definition.code_path}/self_comp_{expanded_case.config_id}{expanded_case.target_suffix}.bc",
            ),
            "result_name": f"{case_id}_self_comp",
            "json_name": f"{case_id}.json",
            "replay_executable": resolve_case_template(
                benchmark_definition,
                expanded_case,
                "self_comp_replay_executable",
                f"klee_{expanded_case.public_mode}_replay{expanded_case.target_suffix}",
            ),
            "source_column_suffix": expanded_case.public_mode,
            "public_mode": expanded_case.public_mode,
            "sliced": expanded_case.variant_id == "sliced",
        }
        secret_layout = optional_string(
            expanded_case.config_table,
            "secret_layout",
            expanded_case.config_location,
        ) or optional_string(
            expanded_case.target_table,
            "secret_layout",
            expanded_case.target_location,
        )
        public_layout = optional_string(
            expanded_case.config_table,
            "public_layout",
            expanded_case.config_location,
        ) or optional_string(
            expanded_case.target_table,
            "public_layout",
            expanded_case.target_location,
        )
        if secret_layout:
            case["secret_layout"] = secret_layout
        if public_layout:
            case["public_layout"] = public_layout
        cases.append(case)
    return cases


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for direct self-composition runs across benchmarks."""
    parser = argparse.ArgumentParser(description="Run the self-composition baseline over the configured benchmark set.")
    parser.add_argument("--klee-root", required=True, help="Path containing the klee binary")
    parser.add_argument("--max-time", required=True, help="Overall timeout for each KLEE run")
    parser.add_argument("--sym-size", type=int, default=4)
    parser.add_argument("--max-solver-time", default="30s")
    parser.add_argument("--kill-after", default="1800s")
    parser.add_argument("--max-memory", type=int, default=10000)
    parser.add_argument("--search", default="random-path,nurs:covnew")
    parser.add_argument("--results-dir", default="results/self_comp_results")
    parser.add_argument("--no-reproduce", action="store_true")
    parser.add_argument("--reproduce-timeout", type=int, default=180)
    parser.add_argument("--pin-root")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream per-case worker stdout/stderr to the terminal while also writing worker logs",
    )
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument(
        "--benchmarks",
        help=(
            "Comma-separated benchmark groups to run. Valid: "
            + ",".join(format_benchmark_selector(library_id, variant_id) for library_id, variant_id in selected_benchmarks("self_comp", None))
        ),
    )
    args = parser.parse_args(argv)

    if args.sym_size < 0:
        raise SystemExit(f"Error: sym_size must be a non-negative integer (got '{args.sym_size}')")
    if args.max_memory < 0:
        raise SystemExit(f"Error: max_memory must be a non-negative integer (got '{args.max_memory}')")
    if args.reproduce_timeout < 0:
        raise SystemExit(f"Error: reproduce_timeout must be a non-negative integer (got '{args.reproduce_timeout}')")

    try:
        benchmarks = selected_benchmarks("self_comp", args.benchmarks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    limit_bytes = 70_000_000 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    klee_root = resolve_repo_path(args.klee_root)
    args.klee_root = str(klee_root)
    args.tmp_dir = str(Path(args.tmp_dir).expanduser().resolve())
    results_dir = resolve_repo_path(args.results_dir)
    shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "output.log").open("a", encoding="utf-8") as output_handle:
        context = ExperimentContext(output_handle)
        context.log("##########")
        context.log("Args:")
        context.log(f"klee_root={klee_root}")
        context.log(f"max_time={args.max_time}")
        context.log(f"sym_size={args.sym_size}")
        context.log(f"max_solver_time={args.max_solver_time}")
        context.log(f"kill_after={args.kill_after}")
        context.log(f"max_memory={args.max_memory}")
        context.log(f"search_strategies={args.search}")
        context.log(f"results_dir={results_dir}")
        context.log(f"do_reproduce={0 if args.no_reproduce else 1}")
        context.log(f"reproduce_timeout={args.reproduce_timeout}")
        context.log(f"pin_root={args.pin_root or os.environ.get('PIN_ROOT', '<unset>')}")
        context.log(f"verbose={'true' if args.verbose else 'false'}")
        context.log(f"tmp_dir={args.tmp_dir}")
        context.log(
            "benchmarks="
            + ",".join(format_benchmark_selector(library_id, variant_id) for library_id, variant_id in benchmarks)
        )
        context.log("##########")

        launched_runs: list[LaunchedProcess] = []

        def handle_signal(signum: int, _frame: object) -> None:
            print("interrupted, stopping self-comp case workers", file=sys.stderr)
            terminate_processes(launched_runs)
            raise SystemExit(130)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        seen_result_names: set[str] = set()
        seen_json_names: set[str] = set()
        try:
            for library_id, variant_id in benchmarks:
                benchmark_definition = definition(library_id, variant_id)
                case_entries = _load_self_comp_cases(benchmark_definition)
                if not case_entries:
                    continue
                if "self_comp" not in benchmark_definition.tools:
                    raise ValueError(f"{benchmark_definition.config_location}.self_comp_cases requires 'self_comp' in tools")
                # The parent only enumerates benchmark/case pairs and launches one
                # worker per case. Each child creates its own temporary workspace
                # inside run_benchmark and executes exactly one selected case there.
                for index, raw_case in enumerate(case_entries):
                    case_location = f"{benchmark_definition.config_location}.self_comp_cases[{index}]"
                    case_table = expect_table(raw_case, case_location)
                    title = expect_string(case_table, "title", case_location)
                    result_name = expect_string(case_table, "result_name", case_location)
                    json_name = expect_string(case_table, "json_name", case_location)
                    if result_name in seen_result_names:
                        raise SystemExit(f"duplicate self-comp result_name across selected cases: {result_name}")
                    if json_name in seen_json_names:
                        raise SystemExit(f"duplicate self-comp json_name across selected cases: {json_name}")
                    seen_result_names.add(result_name)
                    seen_json_names.add(json_name)
                    worker_log_path = results_dir / "_worker_logs" / f"{result_name}.log"
                    worker_log_path.parent.mkdir(parents=True, exist_ok=True)
                    context.log(
                        f"[{title}] starting; output root: {results_dir}; log: {worker_log_path}"
                    )
                    launched_runs.append(
                        launch_output_captured_process(
                            title,
                            run_benchmark,
                            (None, str(results_dir), args, library_id, variant_id, index),
                            log_path=worker_log_path,
                            verbose=args.verbose,
                        )
                    )
            if wait_for_processes(launched_runs) != 0:
                raise SystemExit(1)
        except BaseException:
            terminate_processes(launched_runs)
            raise
    return 0


def run_benchmark(
    context: ExperimentContext | None,
    results_dir: Path | str,
    args: argparse.Namespace,
    library_id: str,
    variant_id: str,
    case_index: int,
    output_queue: object | None = None,
) -> None:
    """Build one benchmark variant and execute exactly one self-composition case."""
    def worker_main() -> None:
        local_context = context or ExperimentContext()
        local_results_dir = Path(results_dir)
        klee_root = Path(args.klee_root)
        benchmark_definition = definition(library_id, variant_id)
        build = build_for_tool(benchmark_definition, "self_comp")
        selector_text = format_benchmark_selector(library_id, variant_id)
        local_context.log("##########")
        local_context.log(f"Begin experiments for {selector_text}")
        local_context.log("##########")
        with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
            local_context.log(f"temporary_workspace={workspace.root}")
            build_command = [build.script, build.tool_flag]
            build_command.extend(["--preset", build.preset.format(sym_size=args.sym_size)])
            local_context.run(build_command, cwd=workspace.root)

            case_entries = _load_self_comp_cases(benchmark_definition)
            if not case_entries:
                raise SystemExit(f"benchmark {selector_text!r} does not define self-comp cases")
            if "self_comp" not in benchmark_definition.tools:
                raise ValueError(f"{benchmark_definition.config_location}.self_comp_cases requires 'self_comp' in tools")
            if case_index < 0 or case_index >= len(case_entries):
                raise SystemExit(
                    f"internal worker case index {case_index} is out of range for benchmark {selector_text!r}"
                )
            case_location = f"{benchmark_definition.config_location}.self_comp_cases[{case_index}]"
            case_table = expect_table(case_entries[case_index], case_location)
            converter_args: list[str] = []
            if secret_layout := optional_string(case_table, "secret_layout", case_location):
                converter_args.extend(["--secret-layout", secret_layout])
            if public_layout := optional_string(case_table, "public_layout", case_location):
                converter_args.extend(["--public-layout", public_layout])
            output_metadata = {
                **normalized_case_output_metadata(case_table, case_location),
                "library_key": benchmark_definition.library_id,
            }
            run_case(
                local_context,
                workspace,
                klee_root,
                local_results_dir,
                args,
                expect_string(case_table, "title", case_location),
                expect_string(case_table, "bitcode", case_location),
                expect_string(case_table, "result_name", case_location),
                expect_string(case_table, "json_name", case_location),
                expect_string(case_table, "replay_executable", case_location),
                output_metadata,
                *converter_args,
            )

    execute_output_captured_worker(output_queue, worker_main)


def run_case(
    context: ExperimentContext,
    workspace,
    klee_root: Path,
    results_dir: Path,
    args: argparse.Namespace,
    title: str,
    bitcode: str,
    result_name: str,
    json_name: str,
    replay_executable: str,
    metadata: dict[str, object],
    *converter_args: str,
) -> None:
    """Run one self-comp case and convert the live KLEE log to shared JSON."""
    bitcode_path = workspace.resolve_repo_path(bitcode)
    bitcode_dir = bitcode_path.parent
    case_log = results_dir / f"{result_name}.log"
    case_json = results_dir / json_name
    benchmark_definition = definition_for_path(str(bitcode_path))
    if benchmark_definition is None:
        raise SystemExit(f"Error: cannot infer library from path '{bitcode}'")
    library = benchmark_definition.library_id
    code_root = workspace.resolve_code_path(benchmark_definition.code_path)

    def cleanup_outputs() -> None:
        # Self-comp cases reuse one benchmark directory, so stale KLEE outputs
        # from earlier cases would otherwise bleed into the next conversion.
        (bitcode_dir / "klee-last").unlink(missing_ok=True)
        for candidate in bitcode_dir.glob("klee-out-*"):
            shutil.rmtree(candidate, ignore_errors=True)

    context.log("=========")
    context.log(title)
    context.log("=========")

    cleanup_outputs()
    search_args = " ".join(shlex.quote(f"--search={item}") for item in args.search.split(",") if item)
    klee_binary = klee_root / "klee"
    klee_script = (
        f"timeout --foreground --signal=INT --kill-after={shlex.quote(args.kill_after)} {shlex.quote(args.max_time)} "
        f"stdbuf -oL -eL {shlex.quote(str(klee_binary))} --libc=uclibc --posix-runtime --external-calls=all "
        f"--kdalloc --kdalloc-constants-size=5 --kdalloc-globals-size=5 --kdalloc-heap-size=20 --kdalloc-stack-size=10 "
        f"--dump-states-on-halt=false --use-batching-search=false {search_args} --max-solver-time={shlex.quote(args.max_solver_time)} "
        f"--max-memory={args.max_memory} --emit-all-errors=true {shlex.quote(str(bitcode_path))} 2>&1 | "
        f"python -u -c {shlex.quote(TIMESTAMP_CODE)} || true"
    )
    context.run_and_capture(["bash", "-euo", "pipefail", "-c", klee_script], log_path=case_log, cwd=bitcode_dir, check=False)

    klee_output = bitcode_dir / "klee-out-0"
    if klee_output.is_dir():
        destination = results_dir / result_name
        shutil.rmtree(destination, ignore_errors=True)
        klee_output.rename(destination)
    else:
        context.log(f"Warning: missing output directory '{klee_output}'")

    secret_layout = ""
    public_layout = ""
    arg_index = 0
    while arg_index < len(converter_args):
        option_name = converter_args[arg_index]
        if option_name not in ("--secret-layout", "--public-layout"):
            raise SystemExit(f"Error: unsupported self-comp converter option '{option_name}'")
        if arg_index + 1 >= len(converter_args):
            raise SystemExit(f"Error: missing value for {option_name}")
        if option_name == "--secret-layout":
            secret_layout = converter_args[arg_index + 1]
        else:
            public_layout = converter_args[arg_index + 1]
        arg_index += 2

    replay_path_string = None
    if not args.no_reproduce:
        replay_path = bitcode_dir / replay_executable
        if not replay_path.is_file() or not os.access(replay_path, os.X_OK):
            raise SystemExit(f"Error: replay executable not found or not executable: {replay_path}")
        replay_path_string = str(replay_path)
    try:
        convert_self_comp_log(
            log_path=str(case_log),
            output_path=str(case_json),
            sym_size=args.sym_size,
            reproduce=not args.no_reproduce,
            replay_executable=replay_path_string,
            secret_layout=secret_layout,
            public_layout=public_layout,
            reproduce_timeout=args.reproduce_timeout,
            pin_root=args.pin_root,
            code_root=str(code_root),
            library=library,
            metadata=metadata,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error
    cleanup_outputs()


if __name__ == "__main__":
    raise SystemExit(main())
