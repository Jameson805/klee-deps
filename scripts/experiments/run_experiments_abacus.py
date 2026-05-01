#!/usr/bin/env python3
"""Launch the ABACUS-only campaign from TOML.

Unlike the main campaign runner, this mode executes one configuration at a time
inside a pre-existing ABACUS environment. The control flow stays in one
function because the batch is linear: validate config, launch each sym-size
through isolated workspace copies, then merge the per-size JSON outputs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tomllib

from scripts.experiments.common import REPO_ROOT
from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main
from tools.shared.experiment_registry import selected_benchmarks


RUNNER_MODULE = "scripts.experiments.parallel_klee_copies"
RUN_ABACUS_MODULE = "scripts.experiments.run_abacus"


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

    benchmark_csv = benchmark_csv_from_config(benchmarks_section.get("abacus"), "benchmarks.abacus")
    try:
        normalized_benchmarks = selected_benchmarks("abacus", benchmark_csv)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    abacus_root = Path(abacus_root_raw).resolve()
    if not abacus_root.is_dir():
        raise SystemExit(f"abacus root path does not exist: {abacus_root}")

    python_bin = "python"
    output_dir = Path(output_raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    bench_args = [] if benchmark_csv is None else ["--benchmarks", ",".join(normalized_benchmarks)]
    for sym_size in sym_sizes:
        destination = output_dir / f"abacus_{sym_size}"
        if args.postprocess_only:
            continue
        process = subprocess.Popen(
            [
                python_bin,
                "-m",
                RUNNER_MODULE,
                "--tmp-dir",
                tmp_dir_raw,
                "--clean-destination",
                str(num_copies),
                "results/abacus_results",
                str(destination),
                "--",
                python_bin,
                "-m",
                RUN_ABACUS_MODULE,
                str(abacus_root),
                "--sym-size",
                str(sym_size),
                *bench_args,
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(f"[ABACUS SYM {sym_size}] {line}", end="")
        process.stdout.close()
        if process.wait() != 0:
            raise SystemExit(1)

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