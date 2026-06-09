"""Shared implementation for the KLEE-family runners.

KLEE-CF, KLEE-Eager, and KLEE-Self-Comp all execute benchmark-local bitcode,
apply the same optional preprocessing, convert KLEE output into the shared JSON
schema, and replay positives with the benchmark's replay executable. The mode
profile below keeps the per-runner binary path and mode-specific flags explicit
without forking the orchestration flow again.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import resource
import signal
import shlex
import shutil
import time
from scripts.experiments.common import (
    ExperimentContext,
    LaunchedProcess,
    REPO_ROOT,
    cleanup_launched_process,
    expand_benchmark_cases,
    execute_output_captured_worker,
    expect_array,
    expect_string,
    expect_table,
    launch_output_captured_process,
    optional_string,
    optional_string_list,
    prepare_benchmark_workspace,
    resolve_repo_path,
    terminate_processes,
)
from tools.shared.tool_artifacts import resolve_artifact_path, resolve_klee_tool_layout

from tools.converters.klee_log_to_json import KLEE_OPTIONAL_DTYPES, convert_klee_output
from tools.postprocess.reproduce_positives import reproduce_json_positives
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
from tools.shared.result_schema import KIND_BRANCH, KIND_MEMORY, build_payload


SOLVER_BACKENDS = ("stp", "metasmt", "dummy", "z3")
OPTIMIZE_ARRAY_VALUES = ("false", "all", "index", "value")


@dataclass(frozen=True)
class KleeModeProfile:
    tool_id: str
    executable_artifact: str
    results_dir: str
    extra_flag: str | None = None


MODE_PROFILES = {
    "klee_cf": KleeModeProfile(
        tool_id="klee_cf",
        executable_artifact="klee-cf",
        results_dir="results/klee_cf_results",
        extra_flag="concretize_on_solver_timeout",
    ),
    "klee_eager": KleeModeProfile(
        tool_id="klee_eager",
        executable_artifact="klee-eager",
        results_dir="results/klee_eager_results",
        extra_flag="product_program_fallback",
    ),
    "klee_self_comp": KleeModeProfile(
        tool_id="klee_self_comp",
        executable_artifact="klee-self-comp",
        results_dir="results/klee_self_comp_results",
    ),
}


def _mode_profile(mode: str) -> KleeModeProfile:
    try:
        return MODE_PROFILES[mode]
    except KeyError as error:
        supported = ", ".join(sorted(MODE_PROFILES))
        raise ValueError(f"unknown KLEE-family mode {mode!r}; expected one of {supported}") from error


def _format_replay_opts(secret_inputs: list[str], public_inputs: list[str], public_mode: str) -> str:
    """Build replay CLI options for the selected secret/public input layout."""
    options: list[str] = []
    if secret_inputs:
        options.extend(["--secret", ",".join(secret_inputs)])
    if public_mode != "fix_pub" and public_inputs:
        options.extend(["--public", ",".join(public_inputs)])
    return " ".join(options)


def _input_names_from_layout(input_specs: list[str]) -> list[str]:
    """Extract symbolic input names from layout specs like name:size:buffer."""
    names: list[str] = []
    for input_spec in input_specs:
        name = input_spec.split(":", 1)[0].strip()
        if name and name not in names:
            names.append(name)
    return names


def _load_klee_cases(benchmark_definition, tool_id: str) -> list[dict[str, object]]:
    """Load KLEE-family cases, preferring explicit per-tool overrides when present."""
    raw_cases = benchmark_definition.extra_config.get("klee_cases")
    if raw_cases is not None:
        return list(expect_array(raw_cases, f"{benchmark_definition.config_location}.klee_cases"))

    location = benchmark_definition.config_location
    tool_defaults = expect_table(benchmark_definition.extra_config.get("tool_defaults") or {}, f"{location}.tool_defaults")
    klee_defaults = expect_table(tool_defaults.get("klee") or {}, f"{location}.tool_defaults.klee")
    default_secret_inputs = optional_string_list(klee_defaults, "secret_inputs", f"{location}.tool_defaults.klee")
    default_public_inputs = optional_string_list(klee_defaults, "public_inputs", f"{location}.tool_defaults.klee")
    code_path = optional_string(klee_defaults, "code_path", f"{location}.tool_defaults.klee") or benchmark_definition.code_path
    extra_args = optional_string_list(klee_defaults, "extra_args", f"{location}.tool_defaults.klee")
    mod_exp_extra_args = optional_string_list(klee_defaults, "mod_exp_extra_args", f"{location}.tool_defaults.klee")

    cases: list[dict[str, object]] = []
    for expanded_case in expand_benchmark_cases(benchmark_definition, tool_id):
        secret_inputs = list(
            tuple(optional_string_list(expanded_case.config_table, "klee_secret_inputs", expanded_case.config_location))
            or tuple(optional_string_list(expanded_case.target_table, "klee_secret_inputs", expanded_case.target_location))
            or tuple(
                _input_names_from_layout(
                    optional_string_list(expanded_case.config_table, "secret_inputs", expanded_case.config_location)
                )
            )
            or tuple(
                _input_names_from_layout(
                    optional_string_list(expanded_case.target_table, "secret_inputs", expanded_case.target_location)
                )
            )
            or default_secret_inputs
        )
        public_inputs = list(
            tuple(optional_string_list(expanded_case.config_table, "klee_public_inputs", expanded_case.config_location))
            or tuple(optional_string_list(expanded_case.target_table, "klee_public_inputs", expanded_case.target_location))
            or tuple(
                _input_names_from_layout(
                    optional_string_list(expanded_case.config_table, "public_inputs", expanded_case.config_location)
                )
            )
            or tuple(
                _input_names_from_layout(
                    optional_string_list(expanded_case.target_table, "public_inputs", expanded_case.target_location)
                )
            )
            or default_public_inputs
        )
        case = {
            "title": canonical_case_title(
                benchmark_definition.library_id,
                benchmark_definition.variant_id,
                expanded_case.target_id,
                expanded_case.config_id,
            ),
            "config_id": expanded_case.config_id,
            "bitcode": f"{benchmark_definition.code_path}/artifacts/klee/{expanded_case.output_target}/{expanded_case.config_id}.bc",
            "result_name": canonical_case_id(
                benchmark_definition.library_id,
                benchmark_definition.variant_id,
                expanded_case.target_id,
                expanded_case.config_id,
            ),
            "replay_script": f"{benchmark_definition.code_path}/artifacts/klee/{expanded_case.output_target}/{expanded_case.public_mode}_replay",
            "code_path": code_path,
            "replay_opts": _format_replay_opts(secret_inputs, public_inputs, expanded_case.public_mode),
            "source_column_suffix": expanded_case.public_mode,
            "public_mode": expanded_case.public_mode,
            "sliced": expanded_case.variant_id == "sliced",
        }
        raw_use_public_inputs = expanded_case.config_table.get("use_public_inputs")
        if raw_use_public_inputs is not None and not isinstance(raw_use_public_inputs, bool):
            raise ValueError(f"{expanded_case.config_location}.use_public_inputs must be a boolean")
        if raw_use_public_inputs and public_inputs:
            case["public_inputs"] = public_inputs
        if secret_inputs:
            case["secret_inputs"] = secret_inputs
        if extra_args:
            case["extra_args"] = list(extra_args)
        if mod_exp_extra_args:
            case["mod_exp_extra_args"] = list(mod_exp_extra_args)
        cases.append(case)
    return cases


def _filter_klee_cases(
    case_entries: list[dict[str, object]],
    config_filter: str | None,
    case_list_location: str,
) -> list[dict[str, object]]:
    """Optionally restrict KLEE cases to one explicit benchmark config id."""
    if not config_filter:
        return case_entries

    filtered_cases: list[dict[str, object]] = []
    for index, raw_case in enumerate(case_entries):
        case_location = f"{case_list_location}[{index}]"
        case_table = expect_table(raw_case, case_location)
        if expect_string(case_table, "config_id", case_location) == config_filter:
            filtered_cases.append(case_table)
    return filtered_cases


def _load_klee_preprocess_profiles(benchmark_definition, tool_id: str) -> list[dict[str, object]]:
    """Load optional KLEE preprocessing profiles for expanded benchmark cases."""
    location = benchmark_definition.config_location
    tool_defaults = expect_table(
        benchmark_definition.extra_config.get("tool_defaults") or {},
        f"{location}.tool_defaults",
    )
    klee_defaults = expect_table(tool_defaults.get("klee") or {}, f"{location}.tool_defaults.klee")
    preprocess_profiles = expect_table(
        klee_defaults.get("preprocess_profiles") or {},
        f"{location}.tool_defaults.klee.preprocess_profiles",
    )
    profiles: list[dict[str, object]] = []

    for expanded_case in expand_benchmark_cases(benchmark_definition, tool_id):
        preprocess_profile_id = optional_string(
            expanded_case.config_table,
            "preprocess",
            expanded_case.config_location,
        )
        if not preprocess_profile_id:
            continue
        preprocess_location = f"{location}.tool_defaults.klee.preprocess_profiles.{preprocess_profile_id}"
        preprocess_table = expect_table(preprocess_profiles.get(preprocess_profile_id), preprocess_location)
        arguments = optional_string_list(preprocess_table, "arguments", preprocess_location)
        if not arguments:
            raise ValueError(f"{preprocess_location}.arguments must not be empty")
        base_bitcode = f"{benchmark_definition.code_path}/artifacts/klee/{expanded_case.output_target}/{expanded_case.public_mode}.bc"
        output_bitcode = f"{benchmark_definition.code_path}/artifacts/klee/{expanded_case.output_target}/{expanded_case.config_id}.bc"
        profiles.append(
            {
                "arguments": [argument.format(input=base_bitcode, output=output_bitcode) for argument in arguments]
            }
        )
    return profiles


def main_for_mode(mode: str, argv: list[str] | None = None) -> int:
    """CLI entrypoint shared by the KLEE-family wrappers."""
    profile = _mode_profile(mode)
    parser = argparse.ArgumentParser(description="Run one of the KLEE-based experiment configurations.")
    parser.add_argument("max_time", help="Overall timeout for each KLEE run")
    parser.add_argument("--sym-size", type=int, default=4)
    parser.add_argument("--loop-max-iterations", type=int, default=10)
    parser.add_argument("--max-solver-time", default="30s")
    parser.add_argument("--kill-after", default="1800s")
    parser.add_argument("--max-memory", type=int, default=10000)
    parser.add_argument("--config", help="Run only KLEE cases whose config id matches this value")
    parser.add_argument("--mod-exp-only", action="store_true")
    parser.add_argument("--search", default="random-path,nurs:covnew")
    if profile.extra_flag == "concretize_on_solver_timeout":
        parser.add_argument("--concretize-on-solver-timeout", default="true")
    elif profile.extra_flag == "product_program_fallback":
        parser.add_argument("--product-program-fallback", action="store_true")
    parser.add_argument("--solver-backend", default="stp", choices=SOLVER_BACKENDS)
    parser.add_argument("--optimize-array", default="false", choices=OPTIMIZE_ARRAY_VALUES)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream per-case worker stdout/stderr to the terminal while also writing worker logs",
    )
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument(
        "--results-dir",
        default=profile.results_dir,
        help="Directory where run outputs are written",
    )
    parser.add_argument(
        "--benchmarks",
        help=(
            "Comma-separated benchmark groups to run. Valid: "
            + ",".join(format_benchmark_selector(library_id, variant_id) for library_id, variant_id in selected_benchmarks(mode, None))
        ),
    )
    parser.add_argument(
        "--max-parallel-cases",
        type=int,
        help="Maximum number of per-case workers this runner may execute concurrently",
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
    if args.max_parallel_cases is not None and args.max_parallel_cases <= 0:
        raise SystemExit("Error: max_parallel_cases must be a positive integer when set")

    try:
        benchmarks = selected_benchmarks(mode, args.benchmarks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    limit_bytes = 70_000_000 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    klee_layout = resolve_klee_tool_layout(profile.executable_artifact)
    klee_executable = str(klee_layout.binary)
    loop_limiter_plugin = str(resolve_artifact_path("loop_limiter_plugin", expected_kind="shared-library"))
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
        context.log(f"config={args.config or '<all>'}")
        context.log(f"mod_exp_only={'true' if args.mod_exp_only else 'false'}")
        context.log(f"search_strategies={args.search}")
        if profile.extra_flag == "concretize_on_solver_timeout":
            context.log(f"concretize_on_solver_timeout={args.concretize_on_solver_timeout}")
        elif profile.extra_flag == "product_program_fallback":
            context.log(
                f"product_program_fallback={'true' if args.product_program_fallback else 'false'}"
            )
        context.log(f"solver_backend={args.solver_backend}")
        context.log(f"optimize_array={args.optimize_array}")
        context.log(f"verbose={'true' if args.verbose else 'false'}")
        context.log(f"tmp_dir={Path(args.tmp_dir).expanduser().resolve()}")
        context.log(f"results_dir={results_dir}")
        context.log(f"klee_executable={klee_executable}")
        context.log(f"loop_limiter_plugin={loop_limiter_plugin}")
        context.log(
            "benchmarks="
            + ",".join(format_benchmark_selector(library_id, variant_id) for library_id, variant_id in benchmarks)
        )
        context.log("##########")

        launched_runs: list[LaunchedProcess] = []
        launch_failures = 0

        def reap_finished(*, block_until_one: bool) -> int:
            overall = 0
            while True:
                finished: list[LaunchedProcess] = []
                for launched in launched_runs:
                    launched.process.join(timeout=0)
                    if launched.process.exitcode is not None:
                        finished.append(launched)

                if finished:
                    for launched in finished:
                        return_code = launched.process.exitcode if launched.process.exitcode is not None else 1
                        status = "done" if return_code == 0 else f"failed with exit code {return_code}"
                        print(f"[{launched.tag}] {status}; log: {launched.log_path}")
                        if return_code != 0:
                            overall = 1
                        launched.reader.join()
                        cleanup_launched_process(launched)
                        launched_runs.remove(launched)
                    return overall

                if not block_until_one:
                    return overall
                time.sleep(0.2)

        def handle_signal(signum: int, _frame: object) -> None:
            print("interrupted, stopping KLEE case workers", file=os.sys.stderr)
            terminate_processes(launched_runs)
            raise SystemExit(130)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        seen_result_names: set[str] = set()
        try:
            for library_id, variant_id in benchmarks:
                benchmark_definition = definition(library_id, variant_id)
                case_entries = _filter_klee_cases(
                    _load_klee_cases(benchmark_definition, mode),
                    args.config,
                    f"{benchmark_definition.config_location}.klee_cases",
                )
                if not case_entries:
                    continue
                if mode not in benchmark_definition.tools:
                    raise ValueError(
                        f"{benchmark_definition.config_location}.klee_cases requires {mode!r} in tools"
                    )
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
                    while args.max_parallel_cases is not None and len(launched_runs) >= args.max_parallel_cases:
                        launch_failures |= reap_finished(block_until_one=True)
                    launched_runs.append(
                        launch_output_captured_process(
                            worker_tag,
                            run_benchmark,
                            (
                                None,
                                None,
                                str(results_dir),
                                args,
                                klee_executable,
                                loop_limiter_plugin,
                                mode,
                                library_id,
                                variant_id,
                                index,
                            ),
                            log_path=worker_log_path,
                            verbose=args.verbose,
                        )
                    )
            while launched_runs:
                launch_failures |= reap_finished(block_until_one=True)
            if launch_failures != 0:
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
    klee_executable: str,
    loop_limiter_plugin: str,
    mode: str,
    library_id: str,
    variant_id: str,
    case_index: int | None = None,
    output_queue: object | None = None,
) -> None:
    """Build one benchmark variant and execute one or more selected KLEE cases."""
    def worker_main() -> None:
        local_profile = _mode_profile(mode)
        local_context = context or ExperimentContext()
        local_env = env or dict(os.environ)
        local_results_dir = Path(results_dir)
        local_env["KLEE_TOOL_ID"] = local_profile.executable_artifact

        benchmark_definition = definition(library_id, variant_id)
        build = build_for_tool(benchmark_definition, mode)
        selector_text = format_benchmark_selector(library_id, variant_id)
        local_context.log("##########")
        local_context.log(f"Begin experiments for {selector_text}")
        local_context.log("##########")
        # Each worker creates its own benchmark-local workspace only after the
        # parent has already chosen one benchmark/case pair for this process.
        with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
            local_context.log(f"temporary_workspace={workspace.root}")
            build_command = [
                "python",
                "-m",
                "tools.build_benchmark",
                "--tool",
                mode,
                "--benchmark",
                selector_text,
                "--preset",
                build.preset.format(sym_size=args.sym_size),
            ]
            local_context.run(build_command, env=local_env, cwd=workspace.root)
            preprocess_profiles = _load_klee_preprocess_profiles(benchmark_definition, mode)
            if preprocess_profiles:
                if mode not in benchmark_definition.tools:
                    raise ValueError(
                        f"{benchmark_definition.config_location}.tool_defaults.klee.preprocess_profiles requires {mode!r} in tools"
                    )
                loop_limiter = Path(loop_limiter_plugin)
                # Preprocessing stays explicit in the benchmark TOML because only a
                # subset of cases need loop bounding and each benchmark blacklists a
                # different set of helper routines.
                for index, profile_entry in enumerate(preprocess_profiles):
                    profile_table = expect_table(
                        profile_entry,
                        f"{benchmark_definition.config_location}.tool_defaults.klee.preprocess_steps[{index}]",
                    )
                    arguments = optional_string_list(
                        profile_table,
                        "arguments",
                        f"{benchmark_definition.config_location}.tool_defaults.klee.preprocess_steps[{index}]",
                    )
                    if not arguments:
                        raise ValueError(
                            f"{benchmark_definition.config_location}.tool_defaults.klee.preprocess_steps[{index}].arguments must not be empty"
                        )
                    local_context.run(
                        [
                            "opt",
                            "-load",
                            str(loop_limiter),
                            f"-load-pass-plugin={loop_limiter}",
                            "-passes=loop-simplify,loop-limiter",
                            f"-max-iterations={args.loop_max_iterations}",
                            *arguments,
                        ],
                        env=local_env,
                        cwd=workspace.root,
                    )

            case_entries = _filter_klee_cases(
                _load_klee_cases(benchmark_definition, mode),
                args.config,
                f"{benchmark_definition.config_location}.klee_cases",
            )
            if not case_entries:
                if case_index is None:
                    return
                if args.config:
                    raise SystemExit(
                        f"benchmark {selector_text!r} does not define KLEE cases for config {args.config!r}"
                    )
                raise SystemExit(f"benchmark {selector_text!r} does not define KLEE cases")
            if mode not in benchmark_definition.tools:
                raise ValueError(f"{benchmark_definition.config_location}.klee_cases requires {mode!r} in tools")
            if case_index is None:
                selected_case_indexes = range(len(case_entries))
            else:
                if case_index < 0 or case_index >= len(case_entries):
                    raise SystemExit(
                        f"internal worker case index {case_index} is out of range for benchmark {selector_text!r}"
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
                title = expect_string(case_table, "title", case_location)
                bitcode = expect_string(case_table, "bitcode", case_location)
                result_name = expect_string(case_table, "result_name", case_location)
                replay_script = expect_string(case_table, "replay_script", case_location)
                code_path = expect_string(case_table, "code_path", case_location)
                output_metadata = {
                    **normalized_case_output_metadata(case_table, case_location),
                    "library_key": benchmark_definition.library_id,
                }

                bitcode_path = workspace.resolve_repo_path(bitcode)
                bitcode_dir = bitcode_path.parent
                replay_script_path = workspace.resolve_repo_path(replay_script)
                code_root = workspace.resolve_code_path(code_path)
                case_owner_definition = definition_for_path(str(bitcode_path))
                if case_owner_definition is None:
                    raise SystemExit(f"Error: cannot infer library from path '{bitcode}'")
                library = case_owner_definition.library_id
                replay_secret = ""
                replay_public = ""
                replay_args: list[str] = []
                replay_secret_inputs = optional_string_list(case_table, "secret_inputs", case_location)
                replay_public_inputs = optional_string_list(case_table, "public_inputs", case_location)
                if replay_secret_inputs:
                    replay_secret = ",".join(replay_secret_inputs)
                    replay_args.extend(["--secret", replay_secret])
                    if replay_public_inputs:
                        replay_public = ",".join(replay_public_inputs)
                        replay_args.extend(["--public", replay_public])
                else:
                    replay_opts = expect_string(case_table, "replay_opts", case_location)
                    replay_args = shlex.split(replay_opts) if replay_opts else []
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
                    raise SystemExit("Error: KLEE case must define secret_inputs or replay_opts with --secret")

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
                    klee_executable,
                    "--libc=uclibc",
                    "--posix-runtime",
                    "--external-calls=all",
                    f"--solver-backend={args.solver_backend}",
                ]
                if local_profile.extra_flag == "concretize_on_solver_timeout":
                    command.append(f"--concretize-on-solver-timeout={args.concretize_on_solver_timeout}")
                elif local_profile.extra_flag == "product_program_fallback":
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

                analysis_kinds = [KIND_BRANCH, KIND_MEMORY]

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
                )
                if reproduce_return_code != 0:
                    raise SystemExit(reproduce_return_code)

    execute_output_captured_worker(output_queue, worker_main)
