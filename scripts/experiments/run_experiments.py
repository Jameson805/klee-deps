#!/usr/bin/env python3
"""Launch the main multi-tool experiment campaign from TOML.

This runner is intentionally orchestration-heavy: it reads one campaign file,
launches each enabled configuration directly as multiple per-worker runner
processes, and then runs the merge/filter/report pipeline over the collected
outputs. Each tool runner now creates benchmark-local temporary workspaces on
its own, so the campaign layer only needs to allocate per-worker result roots.
"""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import shlex
import shutil
import sys
import time
import tomllib

from scripts.experiments.common import (
    CampaignTool,
    LaunchedProcess,
    REPO_ROOT,
    benchmark_csv_from_config,
    cleanup_launched_process,
    duration_to_seconds,
    launch_prefixed_module,
    resolve_repo_path,
    terminate_processes,
    worker_log_path,
)
from tools.shared.configuration_metadata import (
    copy_column_metadata,
    derive_run_configuration,
    write_run_metadata,
)
from tools.shared.campaign_tools import available_campaign_tools
from tools.shared.experiment_registry import format_benchmark_selector, selected_benchmarks


@dataclass(frozen=True)
class RunDefinition:
    """One configured campaign run before worker expansion."""

    run_key: str
    tag: str
    tool_name: str
    destination_name: str
    args_template: tuple[str, ...]


class TeeStream:
    """Mirror text writes into multiple text streams."""

    def __init__(self, *streams: object) -> None:
        self._streams = streams

    def write(self, text: str) -> int:
        for stream in self._streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()

    def isatty(self) -> bool:
        return any(getattr(stream, "isatty", lambda: False)() for stream in self._streams)


def orchestrator_log_path(output_dir: Path) -> Path:
    """Return the top-level log path for the campaign orchestrator."""
    return output_dir / "_orchestrator.log"


def resolve_campaign_path(path: str | Path) -> Path:
    """Resolve config paths after expanding shell-style environment variables."""
    expanded = Path(os.path.expandvars(os.fspath(path))).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (REPO_ROOT / expanded).resolve()


def detect_cpu_budget() -> int | None:
    """Best-effort CPU budget for this process, honoring Linux affinity when available."""
    try:
        affinity = os.sched_getaffinity(0)
    except (AttributeError, OSError):
        affinity = None
    if affinity:
        return len(affinity)

    process_cpu_count = getattr(os, "process_cpu_count", None)
    if callable(process_cpu_count):
        count = process_cpu_count()
        if isinstance(count, int) and count > 0:
            return count

    count = os.cpu_count()
    if isinstance(count, int) and count > 0:
        return count
    return None


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the main multi-tool campaign orchestrator."""
    parser = argparse.ArgumentParser(description="Run the main experiment campaign.")
    parser.add_argument("config", help="Path to campaign TOML config")
    parser.add_argument("--postprocess-only", action="store_true", help="Run only merge and postprocess steps")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream worker stdout/stderr to the terminal while also writing per-worker logs",
    )
    parser.add_argument(
        "--all-positives",
        action="store_true",
        help=(
            "Keep positives even when they were not reproduced in merge_results CSVs and downstream CSV-based "
            "postprocessing; merged per-configuration JSON always retains all positives."
        ),
    )
    args = parser.parse_args(argv)

    config_path = resolve_campaign_path(args.config)
    if not config_path.is_file():
        raise SystemExit(f"missing config file: {config_path}")

    with config_path.open("rb") as handle:
        raw_config = tomllib.load(handle)

    campaign = raw_config.get("campaign", {})
    benchmarks_section = raw_config.get("benchmarks", {})
    runs_section = raw_config.get("runs", {})
    run_definitions_section = raw_config.get("run_definitions", {})
    if not isinstance(campaign, dict):
        raise SystemExit("campaign config must be a TOML table")
    if not isinstance(benchmarks_section, dict):
        raise SystemExit("benchmarks config must be a TOML table")
    if not isinstance(runs_section, dict):
        raise SystemExit("runs config must be a TOML table")
    if not isinstance(run_definitions_section, dict):
        raise SystemExit("run_definitions config must be a TOML table")

    num_copies = campaign.get("num_copies", 10)
    if not isinstance(num_copies, int) or num_copies <= 0:
        raise SystemExit("campaign.num_copies must be a positive integer")
    max_parallel_workers_raw = campaign.get("max_parallel_workers")
    if max_parallel_workers_raw is None:
        max_parallel_workers: int | None = None
    else:
        if not isinstance(max_parallel_workers_raw, int) or max_parallel_workers_raw <= 0:
            raise SystemExit("campaign.max_parallel_workers must be a positive integer when set")
        max_parallel_workers = max_parallel_workers_raw
    temp_dir_value = campaign.get("temp_dir", "/datapool/theta-lin-experiments/tmp")
    if not isinstance(temp_dir_value, str) or not temp_dir_value:
        raise SystemExit("campaign.temp_dir must be a non-empty string")
    output_value = campaign.get("output", "/datapool/theta-lin-experiments/20260404")
    if not isinstance(output_value, str) or not output_value:
        raise SystemExit("campaign.output must be a non-empty string")
    run_time = campaign.get("run_time", "4h")
    if not isinstance(run_time, str) or not run_time:
        raise SystemExit("campaign.run_time must be a non-empty string")
    run_time_seconds_raw = campaign.get("run_time_seconds")
    if run_time_seconds_raw is None:
        try:
            run_time_seconds = duration_to_seconds(run_time, "campaign.run_time")
        except ValueError as error:
            raise SystemExit(str(error)) from error
    else:
        if not isinstance(run_time_seconds_raw, int) or run_time_seconds_raw <= 0:
            raise SystemExit("campaign.run_time_seconds must be a positive integer when set")
        run_time_seconds = run_time_seconds_raw
    sliced_map_value = campaign.get("sliced_map_csv", "configs/postprocess/sliced_map.csv")
    filtered_locations_value = campaign.get("filtered_locations_csv", "configs/postprocess/filtered_locations.csv")
    ideal_selection_value = campaign.get("ideal_config_selection_csv")
    aggregate_output_prefix = campaign.get("aggregate_output_prefix", "aggregated")
    by_library_output_prefix = campaign.get("by_library_output_prefix", "filtered_reproduction_status_by_library")
    if not isinstance(sliced_map_value, str) or not sliced_map_value:
        raise SystemExit("campaign.sliced_map_csv must be a non-empty string")
    if not isinstance(filtered_locations_value, str) or not filtered_locations_value:
        raise SystemExit("campaign.filtered_locations_csv must be a non-empty string")
    if ideal_selection_value is not None and (
        not isinstance(ideal_selection_value, str) or not ideal_selection_value
    ):
        raise SystemExit(
            "campaign.ideal_config_selection_csv must be a non-empty string when set"
        )
    if not isinstance(aggregate_output_prefix, str) or not aggregate_output_prefix:
        raise SystemExit("campaign.aggregate_output_prefix must be a non-empty string")
    if not isinstance(by_library_output_prefix, str) or not by_library_output_prefix:
        raise SystemExit("campaign.by_library_output_prefix must be a non-empty string")

    available_tools = available_campaign_tools()
    unexpected_benchmark_keys = sorted(
        key for key in benchmarks_section if key != "all" and key not in available_tools
    )
    if unexpected_benchmark_keys:
        raise SystemExit(
            "benchmarks contains unknown tool keys: " + ", ".join(unexpected_benchmark_keys)
        )

    temp_dir_raw = str(resolve_campaign_path(temp_dir_value))
    output_raw = str(resolve_campaign_path(output_value))
    sliced_map_raw = str(resolve_campaign_path(sliced_map_value))
    filtered_locations_raw = str(resolve_campaign_path(filtered_locations_value))
    ideal_selection_raw = (
        str(resolve_campaign_path(ideal_selection_value))
        if ideal_selection_value is not None
        else None
    )

    output_dir = Path(output_raw)
    sliced_map_csv = Path(sliced_map_raw)
    filtered_locations_csv = Path(filtered_locations_raw)
    ideal_config_selection_csv = (
        Path(ideal_selection_raw)
        if ideal_selection_raw is not None
        else None
    )

    try:
        config_benchmarks_all = benchmark_csv_from_config(benchmarks_section.get("all"), "benchmarks.all")
    except ValueError as error:
        raise SystemExit(str(error)) from error
    benchmark_csv_by_tool: dict[str, str | None] = {}
    for tool_name in sorted(available_tools):
        try:
            benchmark_csv = (
                benchmark_csv_from_config(benchmarks_section.get(tool_name), f"benchmarks.{tool_name}")
                or config_benchmarks_all
            )
        except ValueError as error:
            raise SystemExit(str(error)) from error
        try:
            normalized = selected_benchmarks(tool_name, benchmark_csv)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        benchmark_csv_by_tool[tool_name] = (
            None
            if benchmark_csv is None
            else ",".join(
                format_benchmark_selector(library_id, target_id)
                for library_id, target_id in normalized
            )
        )

    run_definitions: list[RunDefinition] = []
    for run_key, raw_definition in run_definitions_section.items():
        if not isinstance(raw_definition, dict):
            raise SystemExit(f"run_definitions.{run_key} must be a TOML table")
        tag = raw_definition.get("tag")
        tool_name = raw_definition.get("tool")
        destination_name = raw_definition.get("destination")
        args_template = raw_definition.get("args")
        if not isinstance(tag, str) or not tag:
            raise SystemExit(f"run_definitions.{run_key}.tag must be a non-empty string")
        if not isinstance(tool_name, str) or tool_name not in available_tools:
            raise SystemExit(f"run_definitions.{run_key}.tool must be one of {', '.join(sorted(available_tools))}")
        if not isinstance(destination_name, str) or not destination_name:
            raise SystemExit(f"run_definitions.{run_key}.destination must be a non-empty string")
        if not isinstance(args_template, list) or not args_template or not all(isinstance(item, str) for item in args_template):
            raise SystemExit(f"run_definitions.{run_key}.args must be a non-empty array of strings")
        run_definitions.append(
            RunDefinition(
                run_key=run_key,
                tag=tag,
                tool_name=tool_name,
                destination_name=destination_name,
                args_template=tuple(args_template),
            )
        )
    if not run_definitions:
        raise SystemExit("run_definitions must contain at least one campaign run")

    enabled_run_keys: set[str] = set()
    for run_definition in run_definitions:
        enabled = runs_section.get(run_definition.run_key, True)
        if not isinstance(enabled, bool):
            raise SystemExit(f"runs.{run_definition.run_key} must be a boolean")
        if enabled:
            enabled_run_keys.add(run_definition.run_key)

    output_dir.mkdir(parents=True, exist_ok=True)
    run_targets: list[tuple[str, str]] = []
    run_metadata_by_destination: dict[str, dict[str, object]] = {}
    active_runs: list[LaunchedProcess] = []
    run_env = dict(os.environ)
    launch_failures = 0
    cpu_budget = detect_cpu_budget()
    orchestrator_log = orchestrator_log_path(output_dir)

    with orchestrator_log.open("w", encoding="utf-8", buffering=1) as orchestrator_log_handle, contextlib.redirect_stdout(
        TeeStream(sys.stdout, orchestrator_log_handle)
    ), contextlib.redirect_stderr(TeeStream(sys.stderr, orchestrator_log_handle)):
        if cpu_budget is not None and max_parallel_workers is not None and max_parallel_workers > cpu_budget:
            print(
                "configured max_parallel_workers exceeds detected CPU budget "
                f"({max_parallel_workers} > {cpu_budget}); this can oversubscribe Slurm allocations and slow runs",
                file=sys.stderr,
            )

        for env_var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            run_env.setdefault(env_var, "1")

        effective_parallel_budget = max_parallel_workers if max_parallel_workers is not None else cpu_budget
        per_worker_case_limit: int | None = None
        if effective_parallel_budget is not None and enabled_run_keys:
            total_campaign_workers = len(enabled_run_keys) * num_copies
            per_worker_case_limit = max(1, effective_parallel_budget // total_campaign_workers)
            print(
                "campaign will cap each top-level worker to "
                f"{per_worker_case_limit} concurrent inner cases "
                f"across {total_campaign_workers} campaign workers"
            )

        build_jobs = 1
        if cpu_budget is not None and effective_parallel_budget is not None:
            build_jobs = max(1, cpu_budget // max(1, effective_parallel_budget))
        run_env.setdefault("KLEE_DEPS_BUILD_JOBS", str(build_jobs))
        print(f"campaign build parallelism per case worker: {run_env['KLEE_DEPS_BUILD_JOBS']}")

        def reap_finished(*, block_until_one: bool) -> int:
            overall = 0
            while True:
                finished: list[LaunchedProcess] = []
                for launched in active_runs:
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
                        active_runs.remove(launched)
                    return overall

                if not block_until_one:
                    return overall
                time.sleep(0.2)

        def handle_signal(signum: int, _frame: object) -> None:
            print("interrupted, stopping experiment runs", file=sys.stderr)
            terminate_processes(active_runs)
            raise SystemExit(130)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        def launch_run(tag: str, dst: str, tool: CampaignTool, base_args: list[str]) -> None:
            nonlocal launch_failures
            # Preserve the destination root layout expected by the merge step:
            # destination/0, destination/1, ... each contain one worker's outputs.
            run_targets.append((tag, dst))
            if args.postprocess_only:
                return
            destination_root = Path(dst)
            destination_root.mkdir(parents=True, exist_ok=True)
            for copy_index in range(num_copies):
                worker_destination = destination_root / str(copy_index)
                worker_destination.mkdir(parents=True, exist_ok=True)
                worker_tag = f"{tag} #{copy_index}"
                current_worker_log_path = worker_log_path(destination_root, copy_index)
                worker_argv = tool.build_worker_argv(
                    base_args,
                    benchmark_csv=benchmark_csv_by_tool[tool.tool_id],
                    results_dir=worker_destination,
                    tmp_dir=temp_dir_raw,
                    case_parallelism=per_worker_case_limit,
                )
                print(
                    f"[{worker_tag}] starting; results: {worker_destination}; log: {current_worker_log_path}"
                )
                while max_parallel_workers is not None and len(active_runs) >= max_parallel_workers:
                    launch_failures |= reap_finished(block_until_one=True)
                active_runs.append(
                    launch_prefixed_module(
                        worker_tag,
                        tool.module_name,
                        worker_argv,
                        env=run_env,
                        cwd=REPO_ROOT,
                        log_path=current_worker_log_path,
                        verbose=args.verbose,
                    )
                )

        def run_postprocess() -> None:
            # Keep the postprocess flow aligned with the CLI tools users already know,
            # but call the Python entry points directly so the campaign fails fast on
            # argument or import errors without another subprocess layer.
            from tools.postprocess.aggregate_experiment_groups import main as aggregate_experiment_groups_main
            from tools.postprocess.apply_sliced_map import main as apply_sliced_map_main
            from tools.postprocess.filter_merged_results import main as filter_merged_results_main
            from tools.postprocess.merge_csv_by_location import main as merge_csv_by_location_main
            from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main
            from tools.postprocess.merge_results import main as merge_results_main
            from tools.postprocess.merge_verification_timings import main as merge_verification_timings_main
            from tools.postprocess.summarize_reproduction_status import main as summarize_reproduction_status_main

            required_files = [sliced_map_csv, filtered_locations_csv]
            if ideal_config_selection_csv is not None:
                required_files.append(ideal_config_selection_csv)

            for required_file in required_files:
                if not required_file.is_file():
                    raise SystemExit(f"missing required file: {required_file}")

            output_str = str(output_dir)
            merge_results_extra_args = ["--all-positives"] if args.all_positives else []

            for tag, destination in run_targets:
                merge_json_args = [destination]
                print(f"[{tag} MERGE JSON] merge_json_runs_by_experiment {shlex.join(merge_json_args)}")
                if merge_json_runs_main(merge_json_args) != 0:
                    raise SystemExit(1)
            merged_results_args = [output_str, *merge_results_extra_args, "-o", f"{output_str}/merged_results.csv"]
            print(
                f"[MERGE CSV ALL] merge_results {shlex.join(merged_results_args)}"
            )
            if merge_results_main(merged_results_args) != 0:
                raise SystemExit(1)
            sliced_merged_results_args = [
                output_str,
                "--sliced",
                *merge_results_extra_args,
                "-o",
                f"{output_str}/sliced_merged_results.csv",
            ]
            print(
                f"[MERGE CSV SLICED] merge_results {shlex.join(sliced_merged_results_args)}"
            )
            sliced_merge_rc: int
            try:
                sliced_merge_rc = merge_results_main(sliced_merged_results_args)
            except SystemExit as error:
                code = error.code
                if isinstance(code, str) and code.startswith("No sliced top-level result JSON files found"):
                    sliced_merge_rc = 1
                else:
                    raise

            if sliced_merge_rc != 0:
                print("No sliced results found, proceeding without slicing.")
                all_merged_results_path = f"{output_str}/all_merged_results.csv"
                merged_results_path = f"{output_str}/merged_results.csv"
                shutil.copyfile(merged_results_path, all_merged_results_path)
                copy_column_metadata(merged_results_path, all_merged_results_path)
            else:
                sliced_relabeled_results_path = f"{output_str}/sliced_relabeled_merged_results.csv"
                print(
                    "[APPLY SLICED MAP] apply_sliced_map "
                    + shlex.join(
                        [
                            f"{output_str}/sliced_merged_results.csv",
                            "-m",
                            str(sliced_map_csv),
                            "-o",
                            sliced_relabeled_results_path,
                            "--keep-unmapped",
                        ]
                    )
                )
                if apply_sliced_map_main(
                    [
                        f"{output_str}/sliced_merged_results.csv",
                        "-m",
                        str(sliced_map_csv),
                        "-o",
                        sliced_relabeled_results_path,
                        "--keep-unmapped",
                    ]
                ) != 0:
                    raise SystemExit(1)

                print(
                    "[MERGE CSV BY LOCATION] merge_csv_by_location "
                    + shlex.join(
                        [
                            f"{output_str}/merged_results.csv",
                            sliced_relabeled_results_path,
                            "-o",
                            f"{output_str}/all_merged_results.csv",
                        ]
                    )
                )
                if merge_csv_by_location_main(
                    [
                        f"{output_str}/merged_results.csv",
                        sliced_relabeled_results_path,
                        "-o",
                        f"{output_str}/all_merged_results.csv",
                    ]
                ) != 0:
                    raise SystemExit(1)

            print(
                f"[FILTER CSV ALL] filter_merged_results {shlex.join([f'{output_str}/all_merged_results.csv', '--filter', str(filtered_locations_csv), '--output', f'{output_str}/filtered_merged_results.csv'])}"
            )
            if filter_merged_results_main(
                [
                    f"{output_str}/all_merged_results.csv",
                    "--filter",
                    str(filtered_locations_csv),
                    "--output",
                    f"{output_str}/filtered_merged_results.csv",
                ]
            ) != 0:
                raise SystemExit(1)

            timing_args = [
                output_str,
                "--output",
                f"{output_str}/verification_times.csv",
                "--best-output",
                f"{output_str}/verification_times_best_by_tool.csv",
                "--best-latex-output",
                f"{output_str}/verification_times_best_by_tool.tex",
            ]
            print(
                "[MERGE VERIFICATION TIMES] merge_verification_timings "
                + shlex.join(timing_args)
            )
            if merge_verification_timings_main(timing_args) != 0:
                raise SystemExit(1)

            aggregate_output_base = f"{output_str}/{aggregate_output_prefix}"
            aggregate_args = [
                f"{output_str}/filtered_merged_results.csv",
                "--output",
                aggregate_output_base,
            ]
            if ideal_config_selection_csv is not None:
                aggregate_args.extend(["--selection-csv", str(ideal_config_selection_csv)])
            print(
                "[AGGREGATE CONFIGS] aggregate_experiment_groups "
                + shlex.join(aggregate_args)
            )
            try:
                if aggregate_experiment_groups_main(aggregate_args) != 0:
                    raise SystemExit(1)
            except ValueError as error:
                message = str(error)
                if "Image size of" in message and "too large" in message:
                    print(
                        "aggregate_experiment_groups plot output overflowed matplotlib limits; "
                        "continuing without finishing aggregate plots."
                    )
                else:
                    raise

            summary_base_args = [
                output_str,
                "--filter",
                str(filtered_locations_csv),
                "--sliced-map",
                str(sliced_map_csv),
                "--output",
                f"{output_str}/filtered_reproduction_status_summary.csv",
            ]
            summary_selection_args = [
                *summary_base_args,
                "--selected-output",
                f"{output_str}/filtered_reproduction_status_best_of.csv",
                "--selected-latex-output",
                f"{output_str}/filtered_reproduction_status_best_of.tex",
                "--by-library-selection-tables",
                "--by-library-output-prefix",
                f"{output_str}/{by_library_output_prefix}",
            ]
            if ideal_config_selection_csv is not None:
                summary_selection_args.extend([
                    "--selection-csv",
                    str(ideal_config_selection_csv),
                ])
            print(
                "[SUMMARY REPRO STATUS] summarize_reproduction_status "
                + shlex.join(summary_selection_args)
            )
            if summarize_reproduction_status_main(summary_selection_args) != 0:
                raise SystemExit(1)

        template_values: dict[str, str] = {}
        for key, value in campaign.items():
            if isinstance(value, bool):
                template_values[key] = "true" if value else "false"
            elif isinstance(value, (str, int, float)):
                template_values[key] = str(value)
        template_values["run_time"] = run_time
        template_values["run_time_seconds"] = str(run_time_seconds)
        template_values["temp_dir"] = temp_dir_raw
        template_values["output"] = output_raw

        for run_definition in run_definitions:
            if run_definition.run_key not in enabled_run_keys:
                continue
            tool = available_tools[run_definition.tool_name]
            try:
                run_args = [item.format(**template_values) for item in run_definition.args_template]
            except KeyError as error:
                raise SystemExit(
                    f"run_definitions.{run_definition.run_key}.args references unknown template key '{error.args[0]}'"
                ) from error
            destination_name = run_definition.destination_name
            if destination_name in run_metadata_by_destination:
                raise SystemExit(f"duplicate run destination name {destination_name!r}")
            run_metadata_by_destination[destination_name] = derive_run_configuration(
                run_definition.tool_name,
                destination_name,
                run_args,
            )
            launch_run(
                run_definition.tag,
                str(output_dir / destination_name),
                tool,
                run_args,
            )

        write_run_metadata(output_dir, run_metadata_by_destination)

        if not args.postprocess_only:
            while active_runs:
                launch_failures |= reap_finished(block_until_one=True)
            if launch_failures != 0:
                raise SystemExit(1)
        run_postprocess()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
