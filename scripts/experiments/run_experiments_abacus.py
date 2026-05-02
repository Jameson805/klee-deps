#!/usr/bin/env python3
"""Launch the ABACUS-only campaign from TOML.

Unlike the main campaign runner, this mode executes one ABACUS configuration at
a time inside a pre-existing ABACUS environment. The control flow stays in one
function because the batch is linear: validate config, launch each sym-size as
multiple direct worker processes, then merge the per-size JSON outputs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import (
    REPO_ROOT,
    LaunchedProcess,
    benchmark_csv_from_config,
    launch_prefixed_module,
    terminate_processes,
    wait_for_processes,
    worker_log_path,
)
from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main
from tools.shared.experiment_registry import campaign_tool, selected_benchmarks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ABACUS-only campaign inside one existing container.")
    parser.add_argument("config", help="Path to ABACUS campaign TOML config")
    parser.add_argument("--postprocess-only", action="store_true", help="Run only merge steps")
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
    if not isinstance(campaign, dict):
        raise SystemExit("campaign config must be a TOML table")
    if not isinstance(benchmarks_section, dict):
        raise SystemExit("benchmarks config must be a TOML table")

    abacus_root_raw = campaign.get("abacus_root")
    if not isinstance(abacus_root_raw, str) or not abacus_root_raw:
        raise SystemExit("campaign.abacus_root must be a non-empty string")
    num_copies = campaign.get("num_copies", 10)
    if not isinstance(num_copies, int) or num_copies <= 0:
        raise SystemExit("campaign.num_copies must be a positive integer")
    tmp_dir_raw = campaign.get("tmp_dir", "/tmp")
    if not isinstance(tmp_dir_raw, str) or not tmp_dir_raw:
        raise SystemExit("campaign.tmp_dir must be a non-empty string")
    output_raw = campaign.get("output", str(REPO_ROOT / "results/abacus_experiments"))
    if not isinstance(output_raw, str) or not output_raw:
        raise SystemExit("campaign.output must be a non-empty string")
    sym_sizes = campaign.get("sym_sizes", [4, 16])
    if not isinstance(sym_sizes, list) or not sym_sizes:
        raise SystemExit("campaign.sym_sizes must be a non-empty array of integers")
    if not all(isinstance(sym_size, int) and sym_size >= 0 for sym_size in sym_sizes):
        raise SystemExit("campaign.sym_sizes must contain only non-negative integers")

    try:
        benchmark_csv = benchmark_csv_from_config(benchmarks_section.get("abacus"), "benchmarks.abacus")
    except ValueError as error:
        raise SystemExit(str(error)) from error
    try:
        normalized_benchmarks = selected_benchmarks("abacus", benchmark_csv)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    abacus_root = Path(abacus_root_raw).resolve()
    if not abacus_root.is_dir():
        raise SystemExit(f"abacus root path does not exist: {abacus_root}")

    tool = campaign_tool("abacus")
    output_dir = Path(output_raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_csv_value = None if benchmark_csv is None else ",".join(normalized_benchmarks)
    for sym_size in sym_sizes:
        destination = output_dir / f"abacus_{sym_size}"
        if args.postprocess_only:
            continue
        launched_runs: list[LaunchedProcess] = []
        try:
            destination.mkdir(parents=True, exist_ok=True)
            for copy_index in range(num_copies):
                worker_destination = destination / str(copy_index)
                worker_destination.mkdir(parents=True, exist_ok=True)
                current_worker_log_path = worker_log_path(destination, copy_index)
                worker_argv = tool.build_worker_argv(
                    [str(abacus_root), "--sym-size", str(sym_size)],
                    benchmark_csv=benchmark_csv_value,
                    results_dir=worker_destination,
                    tmp_dir=tmp_dir_raw,
                )
                launched_runs.append(
                    launch_prefixed_module(
                        f"ABACUS SYM {sym_size} #{copy_index}",
                        tool.module_name,
                        worker_argv,
                        cwd=REPO_ROOT,
                        log_path=current_worker_log_path,
                    )
                )
            if wait_for_processes(launched_runs) != 0:
                raise SystemExit(1)
        except BaseException:
            terminate_processes(launched_runs)
            raise

    for sym_size in sym_sizes:
        destination = output_dir / f"abacus_{sym_size}"
        if merge_json_runs_main([str(destination)]) != 0:
            raise SystemExit(1)

    print("All Abacus prototype runs completed.")
    print(f"Collected Abacus output root: {output_dir}")
    print(f"Per-size merged JSON generated under: {output_dir}/abacus_<sym>")
    print("Run validation separately on merged results when needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
