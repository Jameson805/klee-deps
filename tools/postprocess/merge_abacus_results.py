#!/usr/bin/env python3
"""Stage ABACUS campaign outputs into an existing experiment campaign.

The normal postprocessing pipeline keys result columns from `_run_metadata.json`.
This wrapper copies one ABACUS bucket into a non-ABACUS campaign, registers it as
an exact configuration, and reruns the same merge/filter/summary steps used by
the main campaign runner.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from tools.shared.configuration_metadata import (
    RUN_METADATA_FILENAME,
    copy_column_metadata,
    load_run_metadata,
    write_run_metadata,
)


DEFAULT_FILTER_CSV = Path("configs/postprocess/filtered_locations.csv")
DEFAULT_SLICED_MAP_CSV = Path("configs/postprocess/sliced_map.csv")


def _allow_large_json_integers() -> None:
    # ABACUS counterexamples can contain very large concrete integer values.
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (_repo_root() / candidate).resolve()


def _has_top_level_result_json(directory: Path) -> bool:
    return any(path.is_file() and path.suffix.lower() == ".json" for path in directory.iterdir())


def _has_repetition_json(directory: Path) -> bool:
    for child in directory.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if any(path.is_file() and path.suffix.lower() == ".json" for path in child.iterdir()):
            return True
    return False


def resolve_abacus_bucket(source_root: Path, bucket: str | None) -> Path:
    """Resolve the ABACUS bucket directory to stage from a campaign output root."""
    if bucket:
        candidate = source_root / bucket
        if not candidate.is_dir():
            raise SystemExit(f"missing ABACUS bucket directory: {candidate}")
        return candidate

    default_bucket = source_root / "abacus_config"
    if default_bucket.is_dir():
        return default_bucket

    abacus_buckets = sorted(
        path for path in source_root.iterdir() if path.is_dir() and path.name.startswith("abacus_")
    )
    if len(abacus_buckets) == 1:
        return abacus_buckets[0]
    if _has_top_level_result_json(source_root) or _has_repetition_json(source_root):
        return source_root
    if not abacus_buckets:
        raise SystemExit(f"{source_root}: no ABACUS result bucket found")
    names = ", ".join(path.name for path in abacus_buckets)
    raise SystemExit(f"{source_root}: multiple ABACUS buckets found ({names}); pass --bucket")


def infer_sym_size(run_name: str) -> str:
    """Infer a run-level symbolic size label from conventional ABACUS bucket names."""
    prefix = "abacus_"
    if run_name.startswith(prefix):
        suffix = run_name[len(prefix):]
        if suffix.isdigit():
            return suffix
    return "all"


def abacus_run_metadata(run_name: str, *, sym_size: str | None = None) -> dict[str, Any]:
    """Build the run metadata used by downstream column metadata helpers."""
    return {
        "source_column_prefix": run_name,
        "tool_family": "abacus",
        "searcher": "default",
        "sym_size": sym_size or infer_sym_size(run_name),
        "cv_model": "all",
    }


def stage_abacus_bucket(
    *,
    source_bucket: Path,
    target_root: Path,
    run_name: str,
    replace: bool,
) -> Path:
    """Copy an ABACUS bucket into the target campaign and ensure merged JSON exists."""
    destination = target_root / run_name
    if source_bucket.resolve() == destination.resolve():
        if not destination.is_dir():
            raise SystemExit(f"missing staged ABACUS directory: {destination}")
    else:
        if destination.exists():
            if not replace:
                raise SystemExit(f"{destination} already exists; pass --replace to overwrite it")
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        shutil.copytree(source_bucket, destination)

    if not _has_top_level_result_json(destination) and _has_repetition_json(destination):
        from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main

        if merge_json_runs_main([str(destination)]) != 0:
            raise SystemExit(1)
    if not _has_top_level_result_json(destination):
        raise SystemExit(
            f"{destination}: no top-level ABACUS result JSON files found after staging"
        )
    return destination


def update_target_run_metadata(
    *,
    target_root: Path,
    run_name: str,
    run_metadata: dict[str, Any],
    replace: bool,
) -> Path:
    """Insert or replace the ABACUS run metadata in the target campaign root."""
    metadata_path = target_root / RUN_METADATA_FILENAME
    if metadata_path.is_file():
        runs = load_run_metadata(target_root)
    else:
        runs = {}

    if run_name in runs and runs[run_name] != run_metadata and not replace:
        raise SystemExit(
            f"{metadata_path}: run {run_name!r} already has different metadata; pass --replace"
        )
    runs[run_name] = run_metadata
    return write_run_metadata(target_root, runs)


def regenerate_merged_outputs(
    *,
    target_root: Path,
    filter_csv: Path,
    sliced_map_csv: Path,
    aggregate_output_prefix: str,
    by_library_output_prefix: str,
    selection_csv: Path | None,
    all_positives: bool,
    skip_aggregate: bool,
    skip_summary: bool,
) -> None:
    """Rerun campaign postprocessing after a new ABACUS run is registered."""
    from tools.postprocess.apply_sliced_map import main as apply_sliced_map_main
    from tools.postprocess.filter_merged_results import main as filter_merged_results_main
    from tools.postprocess.merge_csv_by_location import main as merge_csv_by_location_main
    from tools.postprocess.merge_results import main as merge_results_main

    output_str = str(target_root)
    merge_extra_args = ["--all-positives"] if all_positives else []

    if (
        merge_results_main(
            [output_str, *merge_extra_args, "-o", f"{output_str}/merged_results.csv"]
        )
        != 0
    ):
        raise SystemExit(1)

    sliced_result = 0
    try:
        sliced_result = merge_results_main(
            [
                output_str,
                "--sliced",
                *merge_extra_args,
                "-o",
                f"{output_str}/sliced_merged_results.csv",
            ]
        )
    except SystemExit as error:
        code = error.code
        if isinstance(code, str) and code.startswith("No sliced top-level result JSON files found"):
            sliced_result = 1
        else:
            raise

    if sliced_result != 0:
        merged_results_path = target_root / "merged_results.csv"
        all_merged_results_path = target_root / "all_merged_results.csv"
        shutil.copyfile(merged_results_path, all_merged_results_path)
        copy_column_metadata(merged_results_path, all_merged_results_path)
    else:
        sliced_relabeled = target_root / "sliced_relabeled_merged_results.csv"
        if apply_sliced_map_main(
            [
                f"{output_str}/sliced_merged_results.csv",
                "-m",
                str(sliced_map_csv),
                "-o",
                str(sliced_relabeled),
                "--keep-unmapped",
            ]
        ) != 0:
            raise SystemExit(1)
        if (
            merge_csv_by_location_main(
                [
                    f"{output_str}/merged_results.csv",
                    str(sliced_relabeled),
                    "-o",
                    f"{output_str}/all_merged_results.csv",
                ]
            )
            != 0
        ):
            raise SystemExit(1)

    if filter_merged_results_main(
        [
            f"{output_str}/all_merged_results.csv",
            "--filter",
            str(filter_csv),
            "--output",
            f"{output_str}/filtered_merged_results.csv",
        ]
    ) != 0:
        raise SystemExit(1)

    if not skip_aggregate:
        from tools.postprocess.aggregate_experiment_groups import (
            main as aggregate_experiment_groups_main,
        )

        aggregate_args = [
            f"{output_str}/filtered_merged_results.csv",
            "--output",
            f"{output_str}/{aggregate_output_prefix}",
        ]
        if selection_csv is not None:
            aggregate_args.extend(["--selection-csv", str(selection_csv)])
        if aggregate_experiment_groups_main(aggregate_args) != 0:
            raise SystemExit(1)

    if not skip_summary:
        from tools.postprocess.summarize_reproduction_status import (
            main as summarize_reproduction_status_main,
        )

        summary_args = [
            output_str,
            "--filter",
            str(filter_csv),
            "--sliced-map",
            str(sliced_map_csv),
            "--output",
            f"{output_str}/filtered_reproduction_status_summary.csv",
            "--selected-output",
            f"{output_str}/filtered_reproduction_status_best_of.csv",
            "--selected-latex-output",
            f"{output_str}/filtered_reproduction_status_best_of.tex",
            "--by-library-selection-tables",
            "--by-library-output-prefix",
            f"{output_str}/{by_library_output_prefix}",
        ]
        if selection_csv is not None:
            summary_args.extend(["--selection-csv", str(selection_csv)])
        if summarize_reproduction_status_main(summary_args) != 0:
            raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy an ABACUS result bucket into a non-ABACUS campaign root, register it in "
            "_run_metadata.json, and regenerate merged postprocess outputs."
        )
    )
    parser.add_argument("abacus_root", help="ABACUS campaign output root or one bucket directory")
    parser.add_argument("target_root", help="Existing non-ABACUS campaign output root to update")
    parser.add_argument(
        "--bucket",
        help="ABACUS bucket directory under abacus_root, such as abacus_config or abacus_4",
    )
    parser.add_argument(
        "--run-name", help="Run directory and source-column prefix to use in the target root"
    )
    parser.add_argument(
        "--sym-size",
        help="Run metadata sym_size value; defaults to a numeric suffix in --run-name or 'all'",
    )
    parser.add_argument("--filter", default=str(DEFAULT_FILTER_CSV), help="Filter CSV path")
    parser.add_argument(
        "--sliced-map", default=str(DEFAULT_SLICED_MAP_CSV), help="Sliced map CSV path"
    )
    parser.add_argument(
        "--selection-csv",
        help="Optional selected-configuration CSV for aggregate and summary outputs",
    )
    parser.add_argument(
        "--aggregate-output-prefix",
        default="aggregated",
        help="Aggregate output prefix under target_root",
    )
    parser.add_argument(
        "--by-library-output-prefix",
        default="filtered_reproduction_status_by_library",
        help="By-library summary output prefix under target_root",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing staged run directory or metadata entry",
    )
    parser.add_argument(
        "--stage-only",
        action="store_true",
        help="Only copy/register the ABACUS run; do not regenerate CSV outputs",
    )
    parser.add_argument(
        "--all-positives",
        action="store_true",
        help="Pass --all-positives through to merge_results",
    )
    parser.add_argument(
        "--skip-aggregate",
        action="store_true",
        help="Do not regenerate aggregate configuration outputs",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Do not regenerate reproduction-status summary outputs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _allow_large_json_integers()

    parser = build_parser()
    args = parser.parse_args(argv)

    source_root = _resolve_path(args.abacus_root)
    target_root = _resolve_path(args.target_root)
    filter_csv = _resolve_path(args.filter)
    sliced_map_csv = _resolve_path(args.sliced_map)
    selection_csv = _resolve_path(args.selection_csv) if args.selection_csv else None

    if not source_root.is_dir():
        raise SystemExit(f"missing ABACUS result root: {source_root}")
    if not target_root.is_dir():
        raise SystemExit(f"missing target result root: {target_root}")
    if not filter_csv.is_file():
        raise SystemExit(f"missing filter CSV: {filter_csv}")
    if not sliced_map_csv.is_file():
        raise SystemExit(f"missing sliced map CSV: {sliced_map_csv}")
    if selection_csv is not None and not selection_csv.is_file():
        raise SystemExit(f"missing selection CSV: {selection_csv}")

    source_bucket = resolve_abacus_bucket(source_root, args.bucket)
    run_name = args.run_name or source_bucket.name
    if not run_name or "/" in run_name:
        raise SystemExit("--run-name must be a single non-empty path segment")

    staged_dir = stage_abacus_bucket(
        source_bucket=source_bucket,
        target_root=target_root,
        run_name=run_name,
        replace=args.replace,
    )
    metadata_path = update_target_run_metadata(
        target_root=target_root,
        run_name=run_name,
        run_metadata=abacus_run_metadata(run_name, sym_size=args.sym_size),
        replace=args.replace,
    )
    print(f"Staged ABACUS results: {staged_dir}")
    print(f"Updated run metadata: {metadata_path}")

    if not args.stage_only:
        regenerate_merged_outputs(
            target_root=target_root,
            filter_csv=filter_csv,
            sliced_map_csv=sliced_map_csv,
            aggregate_output_prefix=args.aggregate_output_prefix,
            by_library_output_prefix=args.by_library_output_prefix,
            selection_csv=selection_csv,
            all_positives=args.all_positives,
            skip_aggregate=args.skip_aggregate,
            skip_summary=args.skip_summary,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())