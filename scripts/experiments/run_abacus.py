#!/usr/bin/env python3
"""Run the ABACUS prototype across the configured benchmark cases.

Each benchmark case follows the same three-stage flow: build the benchmark,
invoke the Pin-based ABACUS trace collection, and convert the resulting log
into the repository's shared JSON schema for later merging.
"""

from __future__ import annotations

import argparse
from pathlib import Path
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
from tools.converters.abacus_log_to_json import convert_abacus_log
from tools.shared.experiment_registry import build_for_tool, definition, definition_for_path, selected_benchmarks


CAMPAIGN_TOOL = CampaignTool(tool_id="abacus", module_name=__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ABACUS prototype over the configured benchmark set.")
    parser.add_argument("abacus_root", help="Path to the ABACUS checkout")
    parser.add_argument("--sym-size", type=int, default=4, help="Symbol size in bytes")
    parser.add_argument("--tmp-dir", default="/tmp", help="Parent directory for temporary benchmark workspaces")
    parser.add_argument("--results-dir", default="results/abacus_results", help="Directory where run outputs are written")
    parser.add_argument(
        "--benchmarks",
        help=f"Comma-separated benchmark groups to run. Valid: {','.join(selected_benchmarks('abacus', None))}",
    )
    args = parser.parse_args(argv)

    if args.sym_size < 0:
        raise SystemExit(f"Invalid --sym-size value: {args.sym_size}")

    try:
        benchmarks = selected_benchmarks("abacus", args.benchmarks)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    abacus_root = resolve_repo_path(args.abacus_root).resolve()
    if not abacus_root.is_dir():
        raise SystemExit(f"ABACUS root does not exist: {abacus_root}")

    results_dir = resolve_repo_path(args.results_dir)
    shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "output.log").open("a", encoding="utf-8") as output_handle:
        context = ExperimentContext(output_handle)
        context.log("##########")
        context.log("Args:")
        context.log(f"abacus_root={abacus_root}")
        context.log(f"sym_size={args.sym_size}")
        context.log(f"tmp_dir={Path(args.tmp_dir).expanduser().resolve()}")
        context.log(f"results_dir={results_dir}")
        context.log(f"benchmarks={','.join(benchmarks)}")
        context.log("##########")
        for benchmark in benchmarks:
            benchmark_definition = definition(benchmark)
            build = build_for_tool(benchmark, "abacus")
            context.log("##########")
            context.log(f"Begin experiments for {benchmark_definition.display_name}")
            context.log("##########")
            with prepare_benchmark_workspace(benchmark_definition.code_path, args.tmp_dir) as workspace:
                context.log(f"temporary_workspace={workspace.root}")
                build_command = [build.script, build.tool_flag]
                if build.preset:
                    build_command.extend(["--preset", build.preset.format(sym_size=args.sym_size)])
                context.run(build_command, cwd=workspace.root)
                raw_cases = benchmark_definition.extra_config.get("abacus_cases")
                if raw_cases is None:
                    continue
                if "abacus" not in benchmark_definition.tools:
                    raise ValueError(f"{benchmark_definition.config_location}.abacus_cases requires 'abacus' in tools")
                for index, raw_case in enumerate(expect_array(raw_cases, f"{benchmark_definition.config_location}.abacus_cases")):
                    case_table = expect_table(raw_case, f"{benchmark_definition.config_location}.abacus_cases[{index}]")
                    run_case(
                        context,
                        workspace,
                        abacus_root,
                        results_dir,
                        args.sym_size,
                        expect_string(case_table, "executable", f"{benchmark_definition.config_location}.abacus_cases[{index}]"),
                        expect_string(case_table, "outfile", f"{benchmark_definition.config_location}.abacus_cases[{index}]"),
                        runner_config=(
                            str(resolve_repo_path(runner_config))
                            if (runner_config := optional_string(case_table, "runner_config", f"{benchmark_definition.config_location}.abacus_cases[{index}]"))
                            else None
                        ),
                        preset_name=optional_string(case_table, "preset_name", f"{benchmark_definition.config_location}.abacus_cases[{index}]"),
                    )
    return 0


def run_case(
    context: ExperimentContext,
    workspace,
    abacus_root: Path,
    results_dir: Path,
    sym_size: int,
    executable: str,
    outfile: str,
    runner_config: str | None = None,
    preset_name: str | None = None,
) -> None:
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
            output_path=str(case_json),
            sym_size=sym_size,
            runner_config=runner_config,
            preset_name=preset_name,
            code_root=str(workspace.resolve_code_path(benchmark_definition.code_path)),
            library=library,
        )
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())
