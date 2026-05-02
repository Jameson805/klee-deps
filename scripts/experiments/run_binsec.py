#!/usr/bin/env python3
"""Run BINSEC experiments and normalize their output.

The runner keeps benchmark-specific metadata in TOML, but the execution flow is
always the same: build the benchmark, run BINSEC once per configured case, then
convert the stats file into the shared JSON format and replay positives when a
matching replay binary exists.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import (
    CampaignTool,
    ExperimentContext,
    REPO_ROOT,
    duration_to_seconds,
    expect_array,
    expect_string,
    expect_table,
    optional_string_list,
    prepare_benchmark_workspace,
    resolve_repo_path,
)
from tools.converters.binsec_toml_to_json import convert_binsec_toml
from tools.shared.experiment_registry import build_for_tool, definition, definition_for_path, selected_benchmarks


CAMPAIGN_TOOL = CampaignTool(tool_id="binsec", module_name=__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BINSEC over the configured benchmark set.")
    parser.add_argument("max_time", help="Timeout for BINSEC (for example: 60, 1m, 4h, 2h30m)")
    parser.add_argument("--sym-size", type=int, default=4)
    parser.add_argument("--jump-enum", type=int, default=10)
    parser.add_argument("--sse-depth", type=int, default=1_000_000_000_000)
    parser.add_argument("--fml-solver", default="z3")
    parser.add_argument("--smt-solver", default="z3")
    parser.add_argument("--pin-root")
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument("--results-dir", default="results/binsec_results", help="Directory where run outputs are written")
    parser.add_argument(
        "--benchmarks",
        help=f"Comma-separated benchmark groups to run. Valid: {','.join(selected_benchmarks('binsec', None))}",
    )
    args = parser.parse_args(argv)

    try:
        args.max_time_seconds = duration_to_seconds(args.max_time, "max_time")
    except ValueError as error:
        raise SystemExit(f"Error: {error}") from error

    for name in ("sym_size", "jump_enum", "sse_depth"):
        value = getattr(args, name)
        if value < 0:
            raise SystemExit(f"Error: {name} must be a non-negative integer (got '{value}')")
    if not args.fml_solver:
        raise SystemExit("Error: fml solver name must be non-empty")
    if not args.smt_solver:
        raise SystemExit("Error: smt solver name must be non-empty")

    try:
        benchmarks = selected_benchmarks("binsec", args.benchmarks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    results_dir = resolve_repo_path(args.results_dir)
    shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "output.log").open("a", encoding="utf-8") as output_handle:
        context = ExperimentContext(output_handle)
        context.log("##########")
        context.log("Args:")
        context.log(f"max_time={args.max_time}")
        context.log(f"max_time_seconds={args.max_time_seconds}")
        context.log(f"sym_size={args.sym_size}")
        context.log(f"jump_enum={args.jump_enum}")
        context.log(f"sse_depth={args.sse_depth}")
        context.log(f"binsec_fml_solver={args.fml_solver}")
        context.log(f"binsec_smt_solver={args.smt_solver}")
        context.log(f"pin_root={args.pin_root or os.environ.get('PIN_ROOT', '<unset>')}")
        context.log(f"tmp_dir={Path(args.tmp_dir).expanduser().resolve()}")
        context.log(f"results_dir={results_dir}")
        context.log(f"benchmarks={','.join(benchmarks)}")
        context.log("##########")

        for benchmark in benchmarks:
            benchmark_definition = definition(benchmark)
            build = build_for_tool(benchmark, "binsec")
            with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
                context.log(f"temporary_workspace={workspace.root}")
                build_command = [build.script, build.tool_flag]
                if build.preset:
                    build_command.extend(["--preset", build.preset.format(sym_size=args.sym_size)])
                context.log("##########")
                context.log(f"Begin experiments for {benchmark_definition.display_name}")
                context.log("##########")
                context.run(build_command, cwd=workspace.root)

                raw_cases = benchmark_definition.extra_config.get("binsec_cases")
                if raw_cases is None:
                    continue
                if "binsec" not in benchmark_definition.tools:
                    raise ValueError(f"{benchmark_definition.config_location}.binsec_cases requires 'binsec' in tools")
                for index, raw_case in enumerate(expect_array(raw_cases, f"{benchmark_definition.config_location}.binsec_cases")):
                    case_table = expect_table(raw_case, f"{benchmark_definition.config_location}.binsec_cases[{index}]")
                    converter_args: list[str] = []
                    for secret_input in optional_string_list(
                        case_table,
                        "secret_inputs",
                        f"{benchmark_definition.config_location}.binsec_cases[{index}]",
                    ):
                        converter_args.extend(["--secret-input", secret_input])
                    for public_input in optional_string_list(
                        case_table,
                        "public_inputs",
                        f"{benchmark_definition.config_location}.binsec_cases[{index}]",
                    ):
                        converter_args.extend(["--public-input", public_input])
                    run_case(
                        context,
                        workspace,
                        results_dir,
                        args,
                        expect_string(case_table, "title", f"{benchmark_definition.config_location}.binsec_cases[{index}]"),
                        expect_string(case_table, "sse_script", f"{benchmark_definition.config_location}.binsec_cases[{index}]"),
                        expect_string(case_table, "stats_file", f"{benchmark_definition.config_location}.binsec_cases[{index}]"),
                        expect_string(case_table, "executable", f"{benchmark_definition.config_location}.binsec_cases[{index}]"),
                        *converter_args,
                    )
    return 0


def run_case(
    context: ExperimentContext,
    workspace,
    results_dir: Path,
    args: argparse.Namespace,
    title: str,
    sse_script: str,
    stats_file: str,
    executable: str,
    *converter_args: str,
) -> None:
    executable_path = workspace.resolve_repo_path(executable)
    sse_script_path = workspace.resolve_repo_path(sse_script)
    context.log("=========")
    context.log(title)
    context.log("=========")
    context.run(
        [
            "binsec",
            "-sse",
            "-checkct",
            "-fml-solver",
            args.fml_solver,
            "-smt-solver",
            args.smt_solver,
            "-sse-timeout",
            str(args.max_time_seconds),
            "-sse-jump-enum",
            str(args.jump_enum),
            "-sse-script",
            str(sse_script_path),
            "-sse-depth",
            str(args.sse_depth),
            "-sse-heuristics",
            "nurs",
            "-checkct-features",
            "control-flow,memory-access",
            "-checkct-stats-file",
            str(results_dir / stats_file),
            str(executable_path),
        ],
        cwd=workspace.root,
    )
    stats_path = results_dir / stats_file
    if not stats_path.is_file():
        context.log(f"Warning: missing stats file {stats_path}; skipping JSON conversion")
        return

    out_json = results_dir / f"{Path(stats_file).stem}.json"
    benchmark_definition = definition_for_path(str(executable_path))
    if benchmark_definition is None:
        raise SystemExit(f"Error: cannot infer library for executable '{executable}'")
    code_path = str(workspace.resolve_code_path(benchmark_definition.code_path))
    library = benchmark_definition.library_id

    context.log("-----")
    context.log(f"Converting {stats_path} -> {out_json}")
    context.log("-----")

    secret_inputs: list[str] = []
    public_inputs: list[str] = []
    arg_index = 0
    while arg_index < len(converter_args):
        option_name = converter_args[arg_index]
        if option_name not in ("--secret-input", "--public-input"):
            raise SystemExit(f"Error: unsupported BINSEC converter option '{option_name}'")
        if arg_index + 1 >= len(converter_args):
            raise SystemExit(f"Error: missing value for {option_name}")
        if option_name == "--secret-input":
            secret_inputs.append(converter_args[arg_index + 1])
        else:
            public_inputs.append(converter_args[arg_index + 1])
        arg_index += 2

    replay_path = None
    executable_name = executable_path.name
    # The benchmark config points at the binary BINSEC analyzes. Replay binaries
    # follow the long-standing naming convention derived here so the TOML does
    # not need to repeat both paths for every case.
    if executable_name in ("binsec_fix_pub", "binsec_var_pub"):
        replay_path = executable_path.with_name(f"{executable_name}_replay")
    elif executable_name.startswith("binsec_fix_pub_"):
        replay_path = executable_path.with_name(
            executable_name.replace("binsec_fix_pub_", "binsec_fix_pub_replay_", 1)
        )
    elif executable_name.startswith("binsec_var_pub_"):
        replay_path = executable_path.with_name(
            executable_name.replace("binsec_var_pub_", "binsec_var_pub_replay_", 1)
        )

    if replay_path is not None:
        if replay_path.is_file():
            try:
                convert_binsec_toml(
                    toml_path=str(stats_path),
                    output_log=str(results_dir / "output.log"),
                    executable=str(executable_path),
                    sym_size=args.sym_size,
                    secret_inputs=secret_inputs,
                    public_inputs=public_inputs,
                    replay_executable=str(replay_path),
                    reproduce=True,
                    pin_root=args.pin_root,
                    output_path=str(out_json),
                    code_path=code_path,
                    library=library,
                )
            except (FileNotFoundError, RuntimeError, ValueError) as error:
                raise SystemExit(f"Error: {error}") from error
        else:
            raise SystemExit(f"Error: inferred replay executable is not runnable: {replay_path}")
    else:
        raise SystemExit(f"Error: cannot infer replay executable for '{executable}'")


if __name__ == "__main__":
    raise SystemExit(main())
