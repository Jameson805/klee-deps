#!/usr/bin/env python3
"""Launch the main multi-tool experiment campaign from TOML.

This runner is intentionally orchestration-heavy: it reads one campaign file,
spawns isolated workspace-copy runs for each enabled configuration, and then
runs the merge/filter/report pipeline over the collected outputs. The command
matrix lives in TOML so most experiment changes do not require editing code.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import threading
import tomllib
from typing import Sequence

from scripts.experiments.common import REPO_ROOT, duration_to_seconds
from tools.postprocess.apply_sliced_map import main as apply_sliced_map_main
from tools.postprocess.filter_merged_results import main as filter_merged_results_main
from tools.postprocess.merge_csv_by_location import main as merge_csv_by_location_main
from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main
from tools.postprocess.merge_results import main as merge_results_main
from tools.postprocess.summarize_reproduction_status import main as summarize_reproduction_status_main
from tools.shared.experiment_registry import selected_benchmarks


RUNNER_MODULE = "scripts.experiments.parallel_klee_copies"
MERGE_JSON_SCRIPT = "tools/postprocess/merge_json_runs_by_experiment.py"
MERGE_RESULTS_SCRIPT = "tools/postprocess/merge_results.py"
APPLY_SLICED_MAP_SCRIPT = "tools/postprocess/apply_sliced_map.py"
MERGE_CSV_BY_LOCATION_SCRIPT = "tools/postprocess/merge_csv_by_location.py"
FILTER_MERGED_RESULTS_SCRIPT = "tools/postprocess/filter_merged_results.py"
SUMMARIZE_REPRODUCTION_STATUS_SCRIPT = "tools/postprocess/summarize_reproduction_status.py"


@dataclass(frozen=True)
class RunDefinition:
    run_key: str
    tag: str
    tool_name: str
    source: str
    destination_name: str
    command_template: tuple[str, ...]


@dataclass
class LaunchedProcess:
    tag: str
    process: subprocess.Popen[str]
    reader: threading.Thread


def _forward_output(process: subprocess.Popen[str], tag: str) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{tag}] {line}", end="")
    process.stdout.close()


def launch_prefixed_command(
    tag: str,
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = REPO_ROOT,
) -> LaunchedProcess:
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    reader = threading.Thread(target=_forward_output, args=(process, tag), daemon=True)
    reader.start()
    return LaunchedProcess(tag=tag, process=process, reader=reader)


def wait_for_processes(processes: Sequence[LaunchedProcess]) -> int:
    overall = 0
    for launched in processes:
        if launched.process.wait() != 0:
            overall = 1
    for launched in processes:
        launched.reader.join()
    return overall


def terminate_processes(processes: Sequence[LaunchedProcess]) -> None:
    for launched in processes:
        if launched.process.poll() is None:
            launched.process.terminate()
    for launched in processes:
        if launched.process.poll() is None:
            try:
                launched.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                launched.process.kill()
    for launched in processes:
        launched.reader.join(timeout=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the main experiment campaign.")
    parser.add_argument("config", help="Path to campaign TOML config")
    parser.add_argument("--postprocess-only", action="store_true", help="Run only merge and postprocess steps")
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
    klee_root = campaign.get("klee_root", "/home/theta-lin/klee/build/bin")
    if not isinstance(klee_root, str) or not klee_root:
        raise SystemExit("campaign.klee_root must be a non-empty string")
    pin_root_raw = campaign.get("pin_root")
    if pin_root_raw is not None and (not isinstance(pin_root_raw, str) or not pin_root_raw):
        raise SystemExit("campaign.pin_root must be a non-empty string when set")
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

    def resolve_repo_path(raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return REPO_ROOT / path

    def benchmark_csv_from_config(value: object, label: str) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            if not value:
                return None
            if not all(isinstance(item, str) for item in value):
                raise SystemExit(f"{label} must be a string or array of strings")
            return ",".join(value)
        raise SystemExit(f"{label} must be a string or array of strings")

    output_dir = resolve_repo_path(output_raw)
    pin_root = resolve_repo_path(pin_root_raw) if pin_root_raw is not None else None
    sliced_map_csv = resolve_repo_path(sliced_map_raw)
    filtered_locations_csv = resolve_repo_path(filtered_locations_raw)
    ideal_config_selection_csv = resolve_repo_path(ideal_selection_raw)
    if pin_root is not None and not pin_root.is_dir():
        raise SystemExit(f"campaign.pin_root does not exist: {pin_root}")

    config_benchmarks_all = benchmark_csv_from_config(benchmarks_section.get("all"), "benchmarks.all")
    benchmark_overrides = {
        "klee_cf": benchmark_csv_from_config(benchmarks_section.get("klee_cf"), "benchmarks.klee_cf") or config_benchmarks_all,
        "klee_eager": benchmark_csv_from_config(benchmarks_section.get("klee_eager"), "benchmarks.klee_eager") or config_benchmarks_all,
        "self_comp": benchmark_csv_from_config(benchmarks_section.get("self_comp"), "benchmarks.self_comp") or config_benchmarks_all,
        "binsec": benchmark_csv_from_config(benchmarks_section.get("binsec"), "benchmarks.binsec") or config_benchmarks_all,
    }
    benchmark_args = {}
    for tool_name, benchmark_csv in benchmark_overrides.items():
        try:
            normalized = selected_benchmarks(tool_name, benchmark_csv)
        except ValueError as error:
            raise SystemExit(str(error)) from error
        benchmark_args[tool_name] = [] if benchmark_csv is None else ["--benchmarks", ",".join(normalized)]

    run_definitions: list[RunDefinition] = []
    for run_key, raw_definition in run_definitions_section.items():
        if not isinstance(raw_definition, dict):
            raise SystemExit(f"run_definitions.{run_key} must be a TOML table")
        tag = raw_definition.get("tag")
        tool_name = raw_definition.get("tool")
        source = raw_definition.get("source")
        destination_name = raw_definition.get("destination")
        command_template = raw_definition.get("command")
        if not isinstance(tag, str) or not tag:
            raise SystemExit(f"run_definitions.{run_key}.tag must be a non-empty string")
        if not isinstance(tool_name, str) or tool_name not in benchmark_args:
            raise SystemExit(f"run_definitions.{run_key}.tool must be one of {', '.join(sorted(benchmark_args))}")
        if not isinstance(source, str) or not source:
            raise SystemExit(f"run_definitions.{run_key}.source must be a non-empty string")
        if not isinstance(destination_name, str) or not destination_name:
            raise SystemExit(f"run_definitions.{run_key}.destination must be a non-empty string")
        if not isinstance(command_template, list) or not command_template or not all(isinstance(item, str) for item in command_template):
            raise SystemExit(f"run_definitions.{run_key}.command must be a non-empty array of strings")
        run_definitions.append(
            RunDefinition(
                run_key=run_key,
                tag=tag,
                tool_name=tool_name,
                source=source,
                destination_name=destination_name,
                command_template=tuple(command_template),
            )
        )
    if not run_definitions:
        raise SystemExit("run_definitions must contain at least one campaign run")

    python_bin = "python"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_targets: list[tuple[str, str]] = []
    launched_runs: list[LaunchedProcess] = []
    run_env = dict(os.environ)
    if pin_root is not None:
        run_env["PIN_ROOT"] = str(pin_root)

    def handle_signal(signum: int, _frame: object) -> None:
        print("interrupted, stopping experiment runs", file=sys.stderr)
        terminate_processes(launched_runs)
        raise SystemExit(130)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def launch_run(tag: str, src: str, dst: str, command: list[str]) -> None:
        # Record destinations even in postprocess-only mode so rerunning the
        # merge phase does not depend on rebuilding the run matrix by hand.
        run_targets.append((tag, dst))
        if args.postprocess_only:
            return
        launched_runs.append(
            launch_prefixed_command(
                tag,
                [
                    python_bin,
                    "-m",
                    RUNNER_MODULE,
                    "--tmp-dir",
                    temp_dir_raw,
                    "--clean-destination",
                    str(num_copies),
                    src,
                    dst,
                    "--",
                    *command,
                ],
                env=run_env,
            )
        )

    template_values = {
        "python_bin": python_bin,
        "run_time": run_time,
        "run_time_seconds": str(run_time_seconds),
        "klee_root": klee_root,
    }
    for run_definition in run_definitions:
        enabled = runs_section.get(run_definition.run_key, True)
        if not isinstance(enabled, bool):
            raise SystemExit(f"runs.{run_definition.run_key} must be a boolean")
        if not enabled:
            continue
        command = [item.format(**template_values) for item in run_definition.command_template]
        command.extend(benchmark_args[run_definition.tool_name])
        launch_run(
            run_definition.tag,
            run_definition.source,
            str(output_dir / run_definition.destination_name),
            command,
        )

    if not args.postprocess_only and wait_for_processes(launched_runs) != 0:
        raise SystemExit(1)
    run_postprocess(
        run_targets,
        output_dir,
        sliced_map_csv,
        filtered_locations_csv,
        ideal_config_selection_csv,
        by_library_output_prefix,
    )
    return 0


def run_postprocess(
    run_targets: list[tuple[str, str]],
    output_dir: Path,
    sliced_map_csv: Path,
    filtered_locations_csv: Path,
    ideal_config_selection_csv: Path,
    by_library_output_prefix: str,
) -> None:
    # Keep the postprocess flow aligned with the CLI tools users already know,
    # but call the Python entry points directly so the campaign fails fast on
    # argument or import errors without another subprocess layer.
    for required_file in (sliced_map_csv, filtered_locations_csv, ideal_config_selection_csv):
        if not required_file.is_file():
            raise SystemExit(f"missing required file: {required_file}")

    python_bin = "python"
    output_str = str(output_dir)
    for tag, destination in run_targets:
        command = [python_bin, MERGE_JSON_SCRIPT, destination]
        print(f"[{tag} MERGE JSON] $ {shlex.join(command)}")
        if merge_json_runs_main([destination]) != 0:
            raise SystemExit(1)
    command = [python_bin, MERGE_RESULTS_SCRIPT, output_str, "-o", f"{output_str}/merged_results.csv"]
    print(f"[MERGE CSV ALL] $ {shlex.join(command)}")
    if merge_results_main([output_str, "-o", f"{output_str}/merged_results.csv"]) != 0:
        raise SystemExit(1)
    command = [python_bin, MERGE_RESULTS_SCRIPT, output_str, "--sliced", "-o", f"{output_str}/sliced_merged_results.csv"]
    print(f"[MERGE CSV SLICED] $ {shlex.join(command)}")
    if merge_results_main([output_str, "--sliced", "-o", f"{output_str}/sliced_merged_results.csv"]) != 0:
        raise SystemExit(1)
    command = [
        python_bin,
        APPLY_SLICED_MAP_SCRIPT,
        f"{output_str}/sliced_merged_results.csv",
        "--map",
        str(sliced_map_csv),
        "--output",
        f"{output_str}/sliced_relabeled_merged_results.csv",
    ]
    print(f"[RELABEL CSV SLICED] $ {shlex.join(command)}")
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
    command = [
        python_bin,
        MERGE_CSV_BY_LOCATION_SCRIPT,
        f"{output_str}/merged_results.csv",
        f"{output_str}/sliced_relabeled_merged_results.csv",
        "-o",
        f"{output_str}/all_merged_results.csv",
    ]
    print(f"[MERGE CSV ALL] $ {shlex.join(command)}")
    if merge_csv_by_location_main(
        [
            f"{output_str}/merged_results.csv",
            f"{output_str}/sliced_relabeled_merged_results.csv",
            "-o",
            f"{output_str}/all_merged_results.csv",
        ]
    ) != 0:
        raise SystemExit(1)
    command = [
        python_bin,
        FILTER_MERGED_RESULTS_SCRIPT,
        f"{output_str}/all_merged_results.csv",
        "--filter",
        str(filtered_locations_csv),
        "--output",
        f"{output_str}/filtered_merged_results.csv",
    ]
    print(f"[FILTER CSV ALL] $ {shlex.join(command)}")
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
    command = [
        python_bin,
        SUMMARIZE_REPRODUCTION_STATUS_SCRIPT,
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
    print(f"[SUMMARY REPRO STATUS] $ {shlex.join(command)}")
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


if __name__ == "__main__":
    raise SystemExit(main())