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
import shlex
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import (
    CampaignTool,
    ExperimentContext,
    REPO_ROOT,
    expect_array,
    expect_string,
    expect_table,
    optional_string,
    prepare_benchmark_workspace,
    resolve_repo_path,
)
from tools.converters.self_comp_log_to_json import convert_self_comp_log
from tools.shared.experiment_registry import build_for_tool, definition, definition_for_path, selected_benchmarks

# Keep timestamps in the live log stream so the converter can recover event
# timing without needing another wrapper script on disk.
TIMESTAMP_CODE = "import sys,time\nfor raw in sys.stdin.buffer:\n    line = raw.decode('utf-8', errors='replace')\n    sys.stdout.write(f'[{time.time():.3f}] {line}')\n    sys.stdout.flush()"


CAMPAIGN_TOOL = CampaignTool(tool_id="self_comp", module_name=__name__)


def main(argv: list[str] | None = None) -> int:
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
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument(
        "--benchmarks",
        help=f"Comma-separated benchmark groups to run. Valid: {','.join(selected_benchmarks('self_comp', None))}",
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
        context.log(f"tmp_dir={Path(args.tmp_dir).expanduser().resolve()}")
        context.log(f"benchmarks={','.join(benchmarks)}")
        context.log("##########")

        for benchmark in benchmarks:
            benchmark_definition = definition(benchmark)
            build = build_for_tool(benchmark, "self_comp")
            context.log("##########")
            context.log(f"Begin experiments for {benchmark_definition.display_name}")
            context.log("##########")
            with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
                context.log(f"temporary_workspace={workspace.root}")
                build_command = [build.script, build.tool_flag]
                if build.preset:
                    build_command.extend(["--preset", build.preset.format(sym_size=args.sym_size)])
                context.run(build_command, cwd=workspace.root)
                raw_cases = benchmark_definition.extra_config.get("self_comp_cases")
                if raw_cases is None:
                    continue
                if "self_comp" not in benchmark_definition.tools:
                    raise ValueError(f"{benchmark_definition.config_location}.self_comp_cases requires 'self_comp' in tools")
                for index, raw_case in enumerate(expect_array(raw_cases, f"{benchmark_definition.config_location}.self_comp_cases")):
                    case_table = expect_table(raw_case, f"{benchmark_definition.config_location}.self_comp_cases[{index}]")
                    converter_args: list[str] = []
                    if secret_layout := optional_string(case_table, "secret_layout", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"):
                        converter_args.extend(["--secret-layout", secret_layout])
                    if public_layout := optional_string(case_table, "public_layout", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"):
                        converter_args.extend(["--public-layout", public_layout])
                    run_case(
                        context,
                        workspace,
                        klee_root,
                        results_dir,
                        args,
                        expect_string(case_table, "title", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"),
                        expect_string(case_table, "bitcode", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"),
                        expect_string(case_table, "result_name", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"),
                        expect_string(case_table, "json_name", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"),
                        expect_string(case_table, "replay_executable", f"{benchmark_definition.config_location}.self_comp_cases[{index}]"),
                        *converter_args,
                    )
    return 0


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
    *converter_args: str,
) -> None:
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
        f"--max-memory={args.max_memory} --emit-all-errors=true {shlex.quote(bitcode)} 2>&1 | "
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
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error
    cleanup_outputs()


if __name__ == "__main__":
    raise SystemExit(main())
