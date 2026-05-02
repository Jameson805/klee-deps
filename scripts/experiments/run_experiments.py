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
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import shlex
import sys
import tomllib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import (
    CampaignTool,
    LaunchedProcess,
    REPO_ROOT,
    benchmark_csv_from_config,
    duration_to_seconds,
    launch_prefixed_module,
    resolve_repo_path,
    terminate_processes,
    wait_for_processes,
    worker_log_path,
)
from tools.postprocess.apply_sliced_map import main as apply_sliced_map_main
from tools.postprocess.filter_merged_results import main as filter_merged_results_main
from tools.postprocess.merge_csv_by_location import main as merge_csv_by_location_main
from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main
from tools.postprocess.merge_results import main as merge_results_main
from tools.postprocess.summarize_reproduction_status import main as summarize_reproduction_status_main
from tools.shared.experiment_registry import available_campaign_tools, selected_benchmarks


@dataclass(frozen=True)
class RunDefinition:
    run_key: str
    tag: str
    tool_name: str
    destination_name: str
    args_template: tuple[str, ...]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the main experiment campaign.")
    parser.add_argument("config", help="Path to campaign TOML config")
    parser.add_argument("--postprocess-only", action="store_true", help="Run only merge and postprocess steps")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream worker stdout/stderr to the terminal while also writing per-worker logs",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path
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
    temp_dir_raw = campaign.get("temp_dir", "/datapool/theta-lin-experiments/tmp")
    if not isinstance(temp_dir_raw, str) or not temp_dir_raw:
        raise SystemExit("campaign.temp_dir must be a non-empty string")
    output_raw = campaign.get("output", "/datapool/theta-lin-experiments/20260404")
    if not isinstance(output_raw, str) or not output_raw:
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
    sliced_map_raw = campaign.get("sliced_map_csv", "configs/postprocess/sliced_map.csv")
    filtered_locations_raw = campaign.get("filtered_locations_csv", "configs/postprocess/filtered_locations.csv")
    ideal_selection_raw = campaign.get("ideal_config_selection_csv", "configs/postprocess/ideal_config_selection.csv")
    by_library_output_prefix = campaign.get("by_library_output_prefix", "filtered_reproduction_status_by_library")
    if not isinstance(sliced_map_raw, str) or not sliced_map_raw:
        raise SystemExit("campaign.sliced_map_csv must be a non-empty string")
    if not isinstance(filtered_locations_raw, str) or not filtered_locations_raw:
        raise SystemExit("campaign.filtered_locations_csv must be a non-empty string")
    if not isinstance(ideal_selection_raw, str) or not ideal_selection_raw:
        raise SystemExit("campaign.ideal_config_selection_csv must be a non-empty string")
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

    output_dir = resolve_repo_path(output_raw)
    sliced_map_csv = resolve_repo_path(sliced_map_raw)
    filtered_locations_csv = resolve_repo_path(filtered_locations_raw)
    ideal_config_selection_csv = resolve_repo_path(ideal_selection_raw)

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
        benchmark_csv_by_tool[tool_name] = None if benchmark_csv is None else ",".join(normalized)

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

    output_dir.mkdir(parents=True, exist_ok=True)
    run_targets: list[tuple[str, str]] = []
    launched_runs: list[LaunchedProcess] = []
    run_env = dict(os.environ)

    def handle_signal(signum: int, _frame: object) -> None:
        print("interrupted, stopping experiment runs", file=sys.stderr)
        terminate_processes(launched_runs)
        raise SystemExit(130)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def launch_run(tag: str, dst: str, tool: CampaignTool, base_args: list[str]) -> None:
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
            )
            print(
                f"[{worker_tag}] starting; results: {worker_destination}; log: {current_worker_log_path}"
            )
            launched_runs.append(
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
        for required_file in (sliced_map_csv, filtered_locations_csv, ideal_config_selection_csv):
            if not required_file.is_file():
                raise SystemExit(f"missing required file: {required_file}")

        output_str = str(output_dir)
        for tag, destination in run_targets:
            print(f"[{tag} MERGE JSON] merge_json_runs_by_experiment {shlex.join([destination])}")
            if merge_json_runs_main([destination]) != 0:
                raise SystemExit(1)
        print(
            f"[MERGE CSV ALL] merge_results {shlex.join([output_str, '-o', f'{output_str}/merged_results.csv'])}"
        )
        if merge_results_main([output_str, "-o", f"{output_str}/merged_results.csv"]) != 0:
            raise SystemExit(1)
        print(
            f"[MERGE CSV SLICED] merge_results {shlex.join([output_str, '--sliced', '-o', f'{output_str}/sliced_merged_results.csv'])}"
        )
        if merge_results_main([output_str, "--sliced", "-o", f"{output_str}/sliced_merged_results.csv"]) != 0:
            raise SystemExit(1)
        print(
            "[RELABEL CSV SLICED] apply_sliced_map "
            + shlex.join(
                [
                    f"{output_str}/sliced_merged_results.csv",
                    "--map",
                    str(sliced_map_csv),
                    "--output",
                    f"{output_str}/sliced_relabeled_merged_results.csv",
                ]
            )
        )
        if apply_sliced_map_main(
            [
                f"{output_str}/sliced_merged_results.csv",
                "--map",
                str(sliced_map_csv),
                "--output",
                f"{output_str}/sliced_relabeled_merged_results.csv",
            ]
        ) != 0:
            raise SystemExit(1)
        print(
            "[MERGE CSV BY LOCATION] merge_csv_by_location "
            + shlex.join(
                [
                    f"{output_str}/merged_results.csv",
                    f"{output_str}/sliced_relabeled_merged_results.csv",
                    "-o",
                    f"{output_str}/all_merged_results.csv",
                ]
            )
        )
        if merge_csv_by_location_main(
            [
                f"{output_str}/merged_results.csv",
                f"{output_str}/sliced_relabeled_merged_results.csv",
                "-o",
                f"{output_str}/all_merged_results.csv",
            ]
        ) != 0:
            raise SystemExit(1)
        print(
            "[FILTER CSV ALL] filter_merged_results "
            + shlex.join(
                [
                    f"{output_str}/all_merged_results.csv",
                    "--filter",
                    str(filtered_locations_csv),
                    "--output",
                    f"{output_str}/filtered_merged_results.csv",
                ]
            )
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
        print(
            "[SUMMARY REPRO STATUS] summarize_reproduction_status "
            + shlex.join(
                [
                    output_str,
                    "--filter",
                    str(filtered_locations_csv),
                    "--sliced-map",
                    str(sliced_map_csv),
                    "--selection-csv",
                    str(ideal_config_selection_csv),
                    "--by-library-selection-tables",
                    "--by-library-output-prefix",
                    f"{output_str}/{by_library_output_prefix}",
                    "--output",
                    f"{output_str}/filtered_reproduction_status_summary.csv",
                ]
            )
        )
        if summarize_reproduction_status_main(
            [
                output_str,
                "--filter",
                str(filtered_locations_csv),
                "--sliced-map",
                str(sliced_map_csv),
                "--selection-csv",
                str(ideal_config_selection_csv),
                "--by-library-selection-tables",
                "--by-library-output-prefix",
                f"{output_str}/{by_library_output_prefix}",
                "--output",
                f"{output_str}/filtered_reproduction_status_summary.csv",
            ]
        ) != 0:
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
        enabled = runs_section.get(run_definition.run_key, True)
        if not isinstance(enabled, bool):
            raise SystemExit(f"runs.{run_definition.run_key} must be a boolean")
        if not enabled:
            continue
        tool = available_tools[run_definition.tool_name]
        try:
            run_args = [item.format(**template_values) for item in run_definition.args_template]
        except KeyError as error:
            raise SystemExit(
                f"run_definitions.{run_definition.run_key}.args references unknown template key '{error.args[0]}'"
            ) from error
        launch_run(
            run_definition.tag,
            str(output_dir / run_definition.destination_name),
            tool,
            run_args,
        )

    if not args.postprocess_only and wait_for_processes(launched_runs) != 0:
        raise SystemExit(1)
    run_postprocess()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
