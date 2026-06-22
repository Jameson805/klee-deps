#!/usr/bin/env python3
"""Run the ABACUS prototype across the configured benchmark cases.

Each benchmark case follows the same three-stage flow: build the benchmark,
invoke the Pin-based ABACUS trace collection, and convert the resulting log
into the repository's shared JSON schema for later merging.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import shlex
import shutil
import sys

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
    resolve_repo_path,
    terminate_processes,
    wait_for_processes,
)
from tools.converters.abacus_log_to_json import convert_abacus_log
from tools.shared.experiment_registry import (
    build_for_tool,
    canonical_case_id,
    definition,
    definition_for_path,
    format_benchmark_selector,
    normalized_case_output_metadata,
    runner_profile_for_definition,
    selected_benchmarks,
)


CAMPAIGN_TOOL = CampaignTool(tool_id="abacus", module_name=__name__)


def _resolve_preset_name(preset_template: str, sym_size: int | None, *, owner: str) -> str:
    """Resolve one preset template, requiring a sym size only when the template uses it."""
    if "{sym_size}" in preset_template:
        if sym_size is None:
            raise SystemExit(f"{owner} requires --sym-size because preset {preset_template!r} depends on it")
        return preset_template.format(sym_size=sym_size)
    return preset_template


def _load_abacus_cases(benchmark_definition) -> list[dict[str, object]]:
    """Load ABACUS cases, preferring explicit per-tool overrides when present."""
    raw_cases = benchmark_definition.extra_config.get("abacus_cases")
    if raw_cases is not None:
        return list(expect_array(raw_cases, f"{benchmark_definition.config_location}.abacus_cases"))

    cases: list[dict[str, object]] = []
    for expanded_case in expand_benchmark_cases(benchmark_definition, "abacus"):
        case = {
            "executable": f"{benchmark_definition.code_path}/artifacts/abacus/{expanded_case.output_target}/{expanded_case.artifact_config}",
            "outfile": f"{canonical_case_id(benchmark_definition.library_id, benchmark_definition.target_id, expanded_case.config_id)}.txt",
            "config": expanded_case.config_id,
            "sliced": benchmark_definition.target_id.endswith("_sliced"),
        }
        runner_profile = optional_string(
            expanded_case.config_table,
            "runner_profile",
            expanded_case.config_location,
        ) or optional_string(
            expanded_case.target_table,
            "runner_profile",
            expanded_case.target_location,
        )
        if isinstance(runner_profile, str) and runner_profile:
            case["runner_profile"] = runner_profile
        cases.append(case)
    return cases


def remove_suffix(value: str, suffix: str) -> str:
    """Drop ``suffix`` from ``value`` when it is present."""
    if value.endswith(suffix):
        return value[:-len(suffix)]
    return value


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for direct ABACUS runs across selected benchmarks."""
    parser = argparse.ArgumentParser(description="Run the ABACUS prototype over the configured benchmark set.")
    parser.add_argument("abacus_root", help="Path to the ABACUS checkout")
    parser.add_argument(
        "--sym-size",
        type=int,
        help="Symbol size in bytes for benchmarks whose build or runner presets depend on it",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream per-case worker stdout/stderr to the terminal while also writing worker logs",
    )
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument("--results-dir", default="results/abacus_results", help="Directory where run outputs are written")
    parser.add_argument(
        "--benchmarks",
        help=(
            "Comma-separated benchmark groups to run. Valid: "
            + ",".join(format_benchmark_selector(library_id, target_id) for library_id, target_id in selected_benchmarks("abacus", None))
        ),
    )
    args = parser.parse_args(argv)

    if args.sym_size is not None and args.sym_size < 0:
        raise SystemExit(f"Invalid --sym-size value: {args.sym_size}")

    try:
        benchmarks = selected_benchmarks("abacus", args.benchmarks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    abacus_root = resolve_repo_path(args.abacus_root).resolve()
    if not abacus_root.is_dir():
        raise SystemExit(f"ABACUS root does not exist: {abacus_root}")
    args.abacus_root = str(abacus_root)
    args.tmp_dir = str(Path(args.tmp_dir).expanduser().resolve())

    results_dir = resolve_repo_path(args.results_dir)
    shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "output.log").open("a", encoding="utf-8") as output_handle:
        context = ExperimentContext(output_handle)
        context.log("##########")
        context.log("Args:")
        context.log(f"abacus_root={abacus_root}")
        context.log(f"sym_size={args.sym_size if args.sym_size is not None else 'auto'}")
        context.log(f"verbose={'true' if args.verbose else 'false'}")
        context.log(f"tmp_dir={args.tmp_dir}")
        context.log(f"results_dir={results_dir}")
        context.log(
            "benchmarks="
            + ",".join(format_benchmark_selector(library_id, target_id) for library_id, target_id in benchmarks)
        )
        context.log("##########")
        launched_runs: list[LaunchedProcess] = []

        def handle_signal(signum: int, _frame: object) -> None:
            print("interrupted, stopping ABACUS case workers", file=sys.stderr)
            terminate_processes(launched_runs)
            raise SystemExit(130)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        seen_case_outputs: set[str] = set()
        try:
            for library_id, target_id in benchmarks:
                benchmark_definition = definition(library_id, target_id)
                case_entries = _load_abacus_cases(benchmark_definition)
                if not case_entries:
                    continue
                # The parent only enumerates benchmark/case pairs and launches one
                # worker per case. Each child creates its own temporary workspace
                # inside run_benchmark and executes exactly one case there.
                for index, raw_case in enumerate(case_entries):
                    case_location = f"{benchmark_definition.config_location}.abacus_cases[{index}]"
                    case_table = expect_table(raw_case, case_location)
                    executable = expect_string(case_table, "executable", case_location)
                    outfile = expect_string(case_table, "outfile", case_location)
                    output_stem = Path(outfile).stem
                    if output_stem in seen_case_outputs:
                        raise SystemExit(f"duplicate ABACUS output stem across selected cases: {output_stem}")
                    seen_case_outputs.add(output_stem)
                    worker_tag = f"{format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.target_id)} ({Path(executable).name})"
                    worker_log_path = results_dir / "_worker_logs" / f"{output_stem}.log"
                    worker_log_path.parent.mkdir(parents=True, exist_ok=True)
                    context.log(
                        f"[{worker_tag}] starting; output root: {results_dir}; log: {worker_log_path}"
                    )
                    launched_runs.append(
                        launch_output_captured_process(
                            worker_tag,
                            run_benchmark,
                            (None, str(results_dir), args, library_id, target_id, index),
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
    context,
    results_dir,
    args,
    library_id,
    target_id,
    case_index,
    output_queue=None,
):
    """Build one benchmark target and execute exactly one selected ABACUS case."""
    def worker_main() -> None:
        local_context = context or ExperimentContext()
        local_results_dir = Path(results_dir)
        abacus_root = Path(args.abacus_root)
        benchmark_definition = definition(library_id, target_id)
        build = build_for_tool(benchmark_definition, "abacus")
        selector_text = format_benchmark_selector(library_id, target_id)
        local_context.log("##########")
        local_context.log(f"Begin experiments for {selector_text}")
        local_context.log("##########")
        with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
            local_context.log(f"temporary_workspace={workspace.root}")
            build_command = [
                "python",
                "-m",
                "tools.build_benchmark",
                "--tool",
                "abacus",
                "--benchmark",
                selector_text,
                "--preset",
                _resolve_preset_name(
                    build.preset,
                    args.sym_size,
                    owner=f"ABACUS build preset for {selector_text}",
                ),
            ]
            local_context.run(build_command, cwd=workspace.root)

            case_entries = _load_abacus_cases(benchmark_definition)
            if not case_entries:
                raise SystemExit(f"benchmark {selector_text!r} does not define ABACUS cases")
            if case_index < 0 or case_index >= len(case_entries):
                raise SystemExit(
                    f"internal worker case index {case_index} is out of range for benchmark {selector_text!r}"
                )
            case_location = f"{benchmark_definition.config_location}.abacus_cases[{case_index}]"
            case_table = expect_table(case_entries[case_index], case_location)
            runner_profile_id = optional_string(case_table, "runner_profile", case_location)
            resolved_runner_config: str | None = None
            resolved_preset_name: str | None = None
            if runner_profile_id is not None:
                _resolved_profile_id, runner_profile = runner_profile_for_definition(
                    benchmark_definition,
                    runner_profile_id,
                )
                resolved_runner_config = str(resolve_repo_path(runner_profile.config))
                resolved_preset_name = _resolve_preset_name(
                    runner_profile.preset,
                    args.sym_size,
                    owner=f"ABACUS runner preset for {selector_text}",
                )
            output_metadata = {
                **normalized_case_output_metadata(case_table, case_location),
                "library": benchmark_definition.library_id,
                "target": benchmark_definition.target_id,
            }
            run_case(
                local_context,
                workspace,
                abacus_root,
                local_results_dir,
                args.sym_size if args.sym_size is not None else 0,
                expect_string(case_table, "executable", case_location),
                expect_string(case_table, "outfile", case_location),
                metadata=output_metadata,
                runner_config=resolved_runner_config,
                preset_name=resolved_preset_name,
            )

    execute_output_captured_worker(output_queue, worker_main)


def run_case(
    context,
    workspace,
    abacus_root,
    results_dir,
    sym_size,
    executable,
    outfile,
    *,
    metadata,
    runner_config=None,
    preset_name=None
):
    """Run one ABACUS case and convert its output to the shared JSON schema."""
    executable_path = workspace.resolve_repo_path(executable)
    benchmark_definition = definition_for_path(str(executable_path))
    if benchmark_definition is None:
        raise SystemExit(f"Error: cannot infer library from executable '{executable}'")
    library = benchmark_definition.library_id

    case_log = results_dir / f"{Path(outfile).stem}.log"
    case_json = results_dir / f"{Path(outfile).stem}.json"
    pin_binary = abacus_root / "Intel-Pin-Archive" / "pin"
    pin_tool = abacus_root / "Pintools" / "obj-ia32" / "MyPinToolLinux.so"
    qif_binary = abacus_root / "build" / "App" / "QIF" / "QIF"
    # Pin writes trace side effects into the current working directory and QIF
    # consumes them immediately, so both commands stay in one shell script.
    script = "\n".join(
        [
            f"{shlex.quote(str(pin_binary))} -t {shlex.quote(str(pin_tool))} -- {shlex.quote(str(executable_path))}",
            f"{shlex.quote(str(qif_binary))} ./Inst_data.txt -f Function.txt -d {shlex.quote(str(executable_path))} -o {shlex.quote(str(results_dir / outfile))}",
        ]
    )

    context.log("=========")
    context.log(str(executable_path))
    context.log("=========")
    context.run_and_capture(["bash", "-euo", "pipefail", "-c", script], log_path=case_log, cwd=executable_path.parent)

    context.log("-----")
    context.log(f"Converting {case_log} -> {case_json}")
    context.log("-----")
    try:
        convert_abacus_log(
            log_path=str(case_log),
            executable_path=str(executable_path),
            output_path=str(case_json),
            runner_config=runner_config,
            preset_name=preset_name,
            code_root=str(workspace.resolve_code_path(benchmark_definition.code_path)),
            library=library,
            metadata=metadata,
        )
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())
