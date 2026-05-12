"""Shared implementation for the KLEE-CF and KLEE-Eager runners.

The two modes differ mostly in binary path and a handful of flags, so they
share one runner that builds benchmark-local artifacts, applies optional loop
preprocessing, converts KLEE output into the shared JSON schema, and replays
positives with the benchmark's replay executable.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import signal
import shlex
import shutil
import sys

from scripts.experiments.common import (
    ExperimentContext,
    LaunchedProcess,
    REPO_ROOT,
    execute_output_captured_worker,
    expect_array,
    expect_string,
    expect_table,
    launch_output_captured_process,
    optional_string_list,
    prepare_benchmark_workspace,
    resolve_repo_path,
    terminate_processes,
    wait_for_processes,
)
from tools.converters.klee_log_to_json import KLEE_OPTIONAL_DTYPES, convert_klee_output
from tools.postprocess.reproduce_positives import reproduce_json_positives
from tools.shared.experiment_registry import (
    build_for_tool,
    definition,
    definition_for_path,
    normalized_case_output_metadata,
    selected_benchmarks,
)
from tools.shared.result_schema import KIND_BRANCH, KIND_MEMORY, build_payload


SOLVER_BACKENDS = ("stp", "metasmt", "dummy", "z3")
OPTIMIZE_ARRAY_VALUES = ("false", "all", "index", "value")


def main_for_mode(mode: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one of the KLEE-based experiment configurations.")
    parser.add_argument("max_time", help="Overall timeout for each KLEE run")
    parser.add_argument("--sym-size", type=int, default=4)
    parser.add_argument("--loop-max-iterations", type=int, default=10)
    parser.add_argument("--max-solver-time", default="30s")
    parser.add_argument("--kill-after", default="1800s")
    parser.add_argument("--max-memory", type=int, default=10000)
    parser.add_argument("--mod-exp-only", action="store_true")
    parser.add_argument("--search", default="random-path,nurs:covnew")
    if mode == "klee_cf":
        parser.add_argument("--concretize-on-solver-timeout", default="true")
    else:
        parser.add_argument("--product-program-fallback", action="store_true")
    parser.add_argument("--solver-backend", default="stp", choices=SOLVER_BACKENDS)
    parser.add_argument("--optimize-array", default="false", choices=OPTIMIZE_ARRAY_VALUES)
    parser.add_argument("--pin-root")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream per-case worker stdout/stderr to the terminal while also writing worker logs",
    )
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument(
        "--results-dir",
        default=("results/klee_cf_results" if mode == "klee_cf" else "results/klee_eager_results"),
        help="Directory where run outputs are written",
    )
    parser.add_argument(
        "--benchmarks",
        help=f"Comma-separated benchmark groups to run. Valid: {','.join(selected_benchmarks(mode, None))}",
    )
    args = parser.parse_args(argv)

    if args.loop_max_iterations < 0:
        raise SystemExit(
            f"Error: loop_max_iterations must be a non-negative integer (got '{args.loop_max_iterations}')"
        )
    if args.sym_size < 0:
        raise SystemExit(f"Error: sym_size must be a non-negative integer (got '{args.sym_size}')")
    if args.max_memory < 0:
        raise SystemExit(f"Error: max_memory must be a non-negative integer (got '{args.max_memory}')")

    try:
        benchmarks = selected_benchmarks(mode, args.benchmarks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    limit_bytes = 70_000_000 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    klee_bin_dir = REPO_ROOT / (
        "klee-controlflow/build/bin" if mode == "klee_cf" else "klee-eager/build/bin"
    )
    env = dict(os.environ)
    env["PATH"] = f"{klee_bin_dir}:{env.get('PATH', '')}"
    os.environ["PATH"] = env["PATH"]
    results_dir = resolve_repo_path(args.results_dir)

    shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "output.log").open("a", encoding="utf-8") as output_handle:
        context = ExperimentContext(output_handle)
        context.log("##########")
        context.log("Args:")
        context.log(f"max_time={args.max_time}")
        context.log(f"sym_size={args.sym_size}")
        context.log(f"loop_max_iterations={args.loop_max_iterations}")
        context.log(f"max_solver_time={args.max_solver_time}")
        context.log(f"kill_after={args.kill_after}")
        context.log(f"max_memory={args.max_memory}")
        context.log(f"mod_exp_only={'true' if args.mod_exp_only else 'false'}")
        context.log(f"search_strategies={args.search}")
        if mode == "klee_cf":
            context.log(f"concretize_on_solver_timeout={args.concretize_on_solver_timeout}")
        else:
            context.log(
                f"product_program_fallback={'true' if args.product_program_fallback else 'false'}"
            )
        context.log(f"solver_backend={args.solver_backend}")
        context.log(f"optimize_array={args.optimize_array}")
        context.log(f"pin_root={args.pin_root or os.environ.get('PIN_ROOT', '<unset>')}")
        context.log(f"verbose={'true' if args.verbose else 'false'}")
        context.log(f"tmp_dir={Path(args.tmp_dir).expanduser().resolve()}")
        context.log(f"results_dir={results_dir}")
        context.log(f"benchmarks={','.join(benchmarks)}")
        context.log("##########")

        launched_runs: list[LaunchedProcess] = []

        def handle_signal(signum: int, _frame: object) -> None:
            print("interrupted, stopping KLEE case workers", file=os.sys.stderr)
            terminate_processes(launched_runs)
            raise SystemExit(130)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        seen_result_names: set[str] = set()
        try:
            for benchmark in benchmarks:
                benchmark_definition = definition(benchmark)
                raw_cases = benchmark_definition.extra_config.get("klee_cases")
                if raw_cases is None:
                    continue
                if not ({"klee_cf", "klee_eager"} & benchmark_definition.tools):
                    raise ValueError(
                        f"{benchmark_definition.config_location}.klee_cases requires a KLEE tool in tools"
                    )
                case_entries = expect_array(raw_cases, f"{benchmark_definition.config_location}.klee_cases")
                # The parent process only enumerates benchmark/case pairs. Each
                # spawned child below creates its own temporary workspace inside
                # run_benchmark and executes exactly one selected case there.
                for index, raw_case in enumerate(case_entries):
                    case_location = f"{benchmark_definition.config_location}.klee_cases[{index}]"
                    case_table = expect_table(raw_case, case_location)
                    result_name = expect_string(case_table, "result_name", case_location)
                    if result_name in seen_result_names:
                        raise SystemExit(f"duplicate KLEE result_name across selected cases: {result_name}")
                    seen_result_names.add(result_name)
                    worker_tag = expect_string(case_table, "title", case_location)
                    worker_log_path = results_dir / "_worker_logs" / f"{result_name}.log"
                    worker_log_path.parent.mkdir(parents=True, exist_ok=True)
                    context.log(
                        f"[{worker_tag}] starting; output root: {results_dir}; log: {worker_log_path}"
                    )
                    launched_runs.append(
                        launch_output_captured_process(
                            worker_tag,
                            run_benchmark,
                            (None, None, str(results_dir), args, mode, benchmark, index),
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
    env: dict[str, str] | None,
    results_dir: Path | str,
    args: argparse.Namespace,
    mode: str,
    benchmark_id: str,
    case_index: int | None = None,
    output_queue: object | None = None,
) -> None:
    def worker_main() -> None:
        local_context = context or ExperimentContext()
        local_env = env or dict(os.environ)
        local_results_dir = Path(results_dir)

        benchmark_definition = definition(benchmark_id)
        build = build_for_tool(benchmark_id, mode)
        local_context.log("##########")
        local_context.log(f"Begin experiments for {benchmark_definition.display_name}")
        local_context.log("##########")
        # Each worker creates its own benchmark-local workspace only after the
        # parent has already chosen one benchmark/case pair for this process.
        with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
            local_context.log(f"temporary_workspace={workspace.root}")
            build_command = [build.script, build.tool_flag]
            if build.preset:
                build_command.extend(["--preset", build.preset.format(sym_size=args.sym_size)])
            build_command.extend(build.extra_args)
            local_context.run(build_command, env=local_env, cwd=workspace.root)
            raw_steps = benchmark_definition.extra_config.get("klee_preprocess_steps")
            if raw_steps is not None:
                if not ({"klee_cf", "klee_eager"} & benchmark_definition.tools):
                    raise ValueError(f"{benchmark_definition.config_location}.klee_preprocess_steps requires a KLEE tool in tools")
                loop_limiter = REPO_ROOT / "loop-limiter/build/libLoopLimiter.so"
                # Preprocessing stays explicit in the benchmark TOML because only a
                # subset of cases need loop bounding and each benchmark blacklists a
                # different set of helper routines.
                for index, raw_step in enumerate(expect_array(raw_steps, f"{benchmark_definition.config_location}.klee_preprocess_steps")):
                    step_table = expect_table(raw_step, f"{benchmark_definition.config_location}.klee_preprocess_steps[{index}]")
                    arguments = optional_string_list(
                        step_table,
                        "arguments",
                        f"{benchmark_definition.config_location}.klee_preprocess_steps[{index}]",
                    )
                    if not arguments:
                        raise ValueError(
                            f"{benchmark_definition.config_location}.klee_preprocess_steps[{index}].arguments must not be empty"
                        )
                    local_context.run(
                        [
                            "opt",
                            "-load",
                            str(loop_limiter),
                            f"-load-pass-plugin={loop_limiter}",
                            "-passes=loop-limiter",
                            f"-max-iterations={args.loop_max_iterations}",
                            *arguments,
                        ],
                        env=local_env,
                        cwd=workspace.root,
                    )

            raw_cases = benchmark_definition.extra_config.get("klee_cases")
            if raw_cases is None:
                if case_index is None:
                    return
                raise SystemExit(f"benchmark {benchmark_id!r} does not define KLEE cases")
            if not ({"klee_cf", "klee_eager"} & benchmark_definition.tools):
                raise ValueError(f"{benchmark_definition.config_location}.klee_cases requires a KLEE tool in tools")
            case_entries = expect_array(raw_cases, f"{benchmark_definition.config_location}.klee_cases")
            if case_index is None:
                selected_case_indexes = range(len(case_entries))
            else:
                if case_index < 0 or case_index >= len(case_entries):
                    raise SystemExit(
                        f"internal worker case index {case_index} is out of range for benchmark {benchmark_id!r}"
                    )
                selected_case_indexes = [case_index]
            # Parallel KLEE workers always arrive here with one concrete index,
            # so each child runs exactly one case from this loop.
            for selected_case_index in selected_case_indexes:
                raw_case = case_entries[selected_case_index]
                case_location = f"{benchmark_definition.config_location}.klee_cases[{selected_case_index}]"
                case_table = expect_table(raw_case, case_location)
                extra_args = list(optional_string_list(case_table, "extra_args", case_location))
                if args.mod_exp_only:
                    extra_args.extend(
                        optional_string_list(
                            case_table,
                            "mod_exp_extra_args",
                            case_location,
                        )
                    )
                memory_flag = case_table.get("memory_flag")
                if not isinstance(memory_flag, bool):
                    raise ValueError(f"{case_location}.memory_flag must be a boolean")
                title = expect_string(case_table, "title", case_location)
                bitcode = expect_string(case_table, "bitcode", case_location)
                result_name = expect_string(case_table, "result_name", case_location)
                replay_script = expect_string(case_table, "replay_script", case_location)
                replay_opts = expect_string(case_table, "replay_opts", case_location)
                code_path = expect_string(case_table, "code_path", case_location)
                output_metadata = {
                    **normalized_case_output_metadata(case_table, case_location),
                    "library_key": benchmark_definition.benchmark_id.removesuffix("_sliced"),
                }

                bitcode_path = workspace.resolve_repo_path(bitcode)
                bitcode_dir = bitcode_path.parent
                replay_script_path = workspace.resolve_repo_path(replay_script)
                code_root = workspace.resolve_code_path(code_path)
                case_owner_definition = definition_for_path(str(bitcode_path))
                if case_owner_definition is None:
                    raise SystemExit(f"Error: cannot infer library from path '{bitcode}'")
                library = case_owner_definition.library_id
                replay_args = shlex.split(replay_opts) if replay_opts else []
                replay_secret = ""
                replay_public = ""
                replay_arg_index = 0
                while replay_arg_index < len(replay_args):
                    option_name = replay_args[replay_arg_index]
                    if option_name not in ("--secret", "--public"):
                        raise SystemExit(f"Error: unsupported KLEE replay option '{option_name}'")
                    if replay_arg_index + 1 >= len(replay_args):
                        raise SystemExit(f"Error: missing value for {option_name}")
                    if option_name == "--secret":
                        replay_secret = replay_args[replay_arg_index + 1]
                    else:
                        replay_public = replay_args[replay_arg_index + 1]
                    replay_arg_index += 2
                if not replay_secret:
                    raise SystemExit("Error: replay_opts must provide --secret for reproduce_positives")

                def cleanup_outputs() -> None:
                    # Always clear benchmark-local KLEE output before and after a case so a
                    # stale `klee-out-*` tree from a previous run cannot be mistaken for the
                    # current result when multiple cases share one benchmark directory.
                    (bitcode_dir / "klee-last").unlink(missing_ok=True)
                    for candidate in bitcode_dir.glob("klee-out-*"):
                        shutil.rmtree(candidate, ignore_errors=True)

                local_context.log("=========")
                local_context.log(title)
                local_context.log("=========")
                cleanup_outputs()

                command = [
                    "timeout",
                    "--foreground",
                    "--signal=INT",
                    f"--kill-after={args.kill_after}",
                    args.max_time,
                    str(
                        REPO_ROOT
                        / ("klee-controlflow/build/bin/klee" if mode == "klee_cf" else "klee-eager/build/bin/klee")
                    ),
                    "--libc=uclibc",
                    "--posix-runtime",
                    "--external-calls=all",
                    f"--solver-backend={args.solver_backend}",
                ]
                if mode == "klee_cf":
                    command.append(f"--concretize-on-solver-timeout={args.concretize_on_solver_timeout}")
                else:
                    command.append(
                        f"--product-program-fallback={'true' if args.product_program_fallback else 'false'}"
                    )
                command.extend(
                    [
                        "--kdalloc",
                        "--kdalloc-constants-size=5",
                        "--kdalloc-globals-size=5",
                        "--kdalloc-heap-size=20",
                        "--kdalloc-stack-size=10",
                        "--dump-states-on-halt=false",
                        "--use-batching-search=false",
                        *[f"--search={item}" for item in args.search.split(",") if item],
                        *([] if args.optimize_array == "false" else [f"--optimize-array={args.optimize_array}"]),
                        f"--max-solver-time={args.max_solver_time}",
                        f"--max-memory={args.max_memory}",
                        "--emit-all-errors=true",
                        str(bitcode_path),
                    ]
                )
                local_context.run(command, env=local_env, check=False, cwd=bitcode_dir)

                source_output = bitcode_dir / "klee-out-0"
                if not source_output.is_dir():
                    raise SystemExit(f"Error: missing KLEE output directory '{source_output}'")
                destination = local_results_dir / result_name
                shutil.rmtree(destination, ignore_errors=True)
                shutil.move(str(source_output), str(destination))
                cleanup_outputs()

                converter_options = {
                    "filename": "",
                    "lines": "",
                    "src_prefix": "",
                    "secret": "",
                    "public": "",
                }
                # Benchmark TOML still stores a compact CLI-like vocabulary for filters and
                # replay layout so we do not need another nested schema just for these few
                # optional switches.
                combined_args = [*extra_args, *replay_args]
                option_index = 0
                while option_index < len(combined_args):
                    option_name = combined_args[option_index]
                    if option_name == "--ctchecker-prefix":
                        if option_index + 1 >= len(combined_args):
                            raise SystemExit(f"Error: missing value for {option_name}")
                        option_index += 2
                        continue
                    if option_name not in ("--filename", "--lines", "--src-prefix", "--secret", "--public"):
                        raise SystemExit(f"Error: unsupported KLEE conversion option '{option_name}'")
                    if option_index + 1 >= len(combined_args):
                        raise SystemExit(f"Error: missing value for {option_name}")
                    converter_options[option_name[2:].replace("-", "_")] = combined_args[option_index + 1]
                    option_index += 2

                analysis_kinds = [KIND_BRANCH]
                if memory_flag:
                    analysis_kinds.append(KIND_MEMORY)

                case_json = local_results_dir / f"{result_name}.json"
                combined_rows: list[dict[str, object]] = []

                # Branch and memory findings now share one JSON file and are
                # distinguished only by the canonical per-row `kind` field.
                for kind in analysis_kinds:
                    try:
                        payload = convert_klee_output(
                            kind=kind,
                            klee_output=str(destination),
                            code_path=str(code_root),
                            filename=converter_options["filename"],
                            lines=converter_options["lines"],
                            src_prefix=converter_options["src_prefix"],
                            secret=converter_options["secret"],
                            public=converter_options["public"],
                            library=library,
                        )
                    except (FileNotFoundError, RuntimeError, ValueError) as error:
                        raise SystemExit(f"Error: {error}") from error
                    for row in payload.get("data", []):
                        if isinstance(row, dict):
                            combined_rows.append(dict(row))

                combined_rows.sort(
                    key=lambda row: (
                        str(row.get("filename") or ""),
                        int(row.get("line") or -1),
                        int(row.get("column") or -1),
                        str(row.get("kind") or ""),
                        int(row.get("inst_id") or -1),
                    )
                )
                combined_payload = build_payload(
                    combined_rows,
                    optional_dtypes=KLEE_OPTIONAL_DTYPES,
                    metadata=output_metadata,
                )
                with case_json.open("w", encoding="utf-8") as handle:
                    json.dump(combined_payload, handle, indent=2)
                    handle.write("\n")

                reproduce_command = [
                    "python",
                    "tools/postprocess/reproduce_positives.py",
                    "--json",
                    str(case_json),
                    "--klee-output",
                    str(destination),
                    "--executable",
                    str(replay_script_path),
                    "--library",
                    library,
                    "--output",
                    str(case_json),
                ]
                if args.pin_root:
                    reproduce_command.extend(["--pin-root", args.pin_root])
                reproduce_command.extend(replay_args)
                local_context.log(f"$ {shlex.join(reproduce_command)}")
                reproduce_return_code = reproduce_json_positives(
                    input_json=str(case_json),
                    klee_output=str(destination),
                    executable=str(replay_script_path),
                    secret=replay_secret,
                    public=replay_public,
                    output=str(case_json),
                    library=library,
                    pin_root=args.pin_root,
                )
                if reproduce_return_code != 0:
                    raise SystemExit(reproduce_return_code)

    execute_output_captured_worker(output_queue, worker_main)
