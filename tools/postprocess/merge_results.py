#!/usr/bin/env python3
"""Merge campaign JSON outputs into a wide CSV keyed by source location.

This script is the bridge between per-run JSON payloads and the wide CSV shape
used by later filtering, summarization, and plotting steps.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections.abc import Sequence
from typing import Any

from tools.shared.configuration_metadata import (
    build_column_metadata,
    load_run_metadata,
    write_column_metadata,
)


Location = tuple[str, str, int, int | None, str | None]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _basename_only(path_value: str) -> str:
    return os.path.basename(path_value.replace("\\", "/"))


def _normalize_kind(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    kind = value.strip()
    return kind or None


def _has_reproduced_success(status: object) -> bool:
    if isinstance(status, str):
        return status.strip() == "success"
    if isinstance(status, dict):
        value = status.get("success")
        try:
            return int(value) > 0
        except (TypeError, ValueError):
            return False
    return False


def _read_payload(path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected a JSON object payload")
    rows = payload.get("data")
    metadata = payload.get("metadata")
    if not isinstance(rows, list):
        return [], {}
    if metadata is not None and not isinstance(metadata, dict):
        raise SystemExit(f"{path}: metadata must be a JSON object")
    return [row for row in rows if isinstance(row, dict)], dict(metadata or {})


def _load_violations_from_json(
    path: str,
    *,
    all_positives: bool = False,
) -> tuple[dict[str, Any], dict[Location, float]]:
    rows, metadata = _read_payload(path)
    if not metadata:
        raise SystemExit(
            f"{path}: payload metadata is missing; this output tree predates the metadata-aware experiment runners. "
            "Regenerate the run outputs with the current campaign runners before running postprocess."
        )
    library_key = metadata.get("library")
    if not isinstance(library_key, str) or not library_key:
        raise SystemExit(
            f"{path}: payload metadata is missing non-empty library; this output tree is stale or incomplete. "
            "Regenerate the run outputs with the current campaign runners before running postprocess."
        )

    out: dict[Location, float] = {}
    for row in rows:
        non_ct_time = _to_float(row.get("non_ct_time"))
        if non_ct_time is None:
            continue
        if not all_positives and not _has_reproduced_success(row.get("reproduced_status")):
            continue

        filename = row.get("filename")
        line = row.get("line")
        column = row.get("column")
        if not isinstance(filename, str) or filename == "":
            continue
        filename = _basename_only(filename)
        if filename == "":
            continue
        try:
            line_i = int(line)
        except (TypeError, ValueError):
            continue

        try:
            col_i = int(column)
        except (TypeError, ValueError):
            col_i = None
        key: Location = (library_key, filename, line_i, col_i, _normalize_kind(row.get("kind")))
        previous = out.get(key)
        out[key] = non_ct_time if previous is None else max(previous, non_ct_time)

    return metadata, out


def merge_runs(
    root_dir: str,
    *,
    sliced_only: bool = False,
    all_positives: bool = False,
) -> tuple[list[str], dict[str, dict[Location, float]], dict[str, dict[str, Any]]]:
    """Merge all run directories under ``root_dir`` into exact result columns."""
    if not os.path.isdir(root_dir):
        raise SystemExit(f"Input '{root_dir}' is not a directory")

    run_metadata_by_name = load_run_metadata(root_dir)
    run_names = sorted(run_metadata_by_name)

    ordered_columns: list[str] = []
    by_col: dict[str, dict[Location, float]] = {}
    column_metadata: dict[str, dict[str, Any]] = {}

    for run_name in run_names:
        run_metadata = run_metadata_by_name[run_name]

        run_dir = os.path.join(root_dir, run_name)
        if not os.path.isdir(run_dir):
            raise SystemExit(f"{root_dir}: run metadata references missing run directory {run_name!r}")
        for file_name in sorted(os.listdir(run_dir)):
            path = os.path.join(run_dir, file_name)
            if not os.path.isfile(path) or not file_name.lower().endswith(".json"):
                continue

            case_metadata, violations = _load_violations_from_json(path, all_positives=all_positives)
            case_sliced = bool(case_metadata.get("sliced"))
            if case_sliced != sliced_only:
                continue

            metadata = build_column_metadata(run_metadata, case_metadata)
            column_name = str(metadata["source_column"])
            existing_metadata = column_metadata.get(column_name)
            if existing_metadata is not None and existing_metadata != metadata:
                raise SystemExit(f"{path}: conflicting metadata for column {column_name!r}")
            if column_name not in by_col:
                ordered_columns.append(column_name)
                by_col[column_name] = {}
                column_metadata[column_name] = metadata

            if not violations:
                continue
            column_values = by_col[column_name]
            for location, time_value in violations.items():
                previous = column_values.get(location)
                column_values[location] = time_value if previous is None else max(previous, time_value)

    return ordered_columns, by_col, column_metadata


def write_csv(
    output_path: str,
    ordered_columns: Sequence[str],
    by_col: dict[str, dict[Location, float]],
    column_metadata: dict[str, dict[str, Any]],
) -> int:
    """Write the merged CSV and its metadata sidecar."""
    all_locations: set[Location] = set()
    wildcard_locations: set[tuple[str, str, int, str | None]] = set()

    for column in ordered_columns:
        for library, filename, line, column_value, kind in by_col.get(column, {}).keys():
            if column_value is None:
                wildcard_locations.add((library, filename, line, kind))
            else:
                all_locations.add((library, filename, line, column_value, kind))

    concrete_lines = {(library, filename, line, kind) for library, filename, line, _, kind in all_locations}
    for library, filename, line, kind in wildcard_locations:
        if (library, filename, line, kind) not in concrete_lines:
            all_locations.add((library, filename, line, 0, kind))

    rows = sorted(
        all_locations,
        key=lambda location: (
            location[0],
            location[1],
            location[2],
            location[3] if location[3] is not None else -1,
            "" if location[4] is None else location[4],
        ),
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["library", "file", "line", "column", "kind", *ordered_columns])
        for library, filename, line, column_value, kind in rows:
            output_row: list[str] = [
                library,
                filename,
                str(line),
                str(column_value if column_value is not None else ""),
                "" if kind is None else kind,
            ]
            for experiment_column in ordered_columns:
                experiment_map = by_col.get(experiment_column, {})
                value = experiment_map.get((library, filename, line, column_value, kind))
                if value is None:
                    value = experiment_map.get((library, filename, line, None, kind))
                output_row.append("" if value is None else f"{value:.2f}")
            writer.writerow(output_row)

    write_column_metadata(output_path, ordered_columns, column_metadata)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for wide-CSV generation from campaign output trees."""
    parser = argparse.ArgumentParser(
        description=(
            "Merge per-run top-level JSON results into a single CSV keyed by (library,file,line,column,kind). "
            "By default, a row is included iff at least one experiment reports non_ct_time != null "
            "and that positive reproduced successfully in at least one repetition."
        )
    )
    parser.add_argument(
        "root_dir",
        help=(
            "Directory containing run subdirectories (for example all/a, all/b, ...). "
            "Each run subdirectory should be a copied tool results folder."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default="merged_results.csv",
        help="Output CSV path (default: merged_results.csv)",
    )
    parser.add_argument(
        "--sliced",
        action="store_true",
        help="If set, merge only sliced results. If not set, merge only non-sliced results.",
    )
    parser.add_argument(
        "--all-positives",
        action="store_true",
        help="Keep positives with non-null non_ct_time even if no repetition reproduced successfully.",
    )
    args = parser.parse_args(argv)

    ordered_columns, by_col, column_metadata = merge_runs(
        args.root_dir,
        sliced_only=args.sliced,
        all_positives=args.all_positives,
    )
    if not ordered_columns:
        mode = "sliced" if args.sliced else "non-sliced"
        raise SystemExit(f"No {mode} top-level result JSON files found under '{args.root_dir}'")

    row_count = write_csv(args.output, ordered_columns, by_col, column_metadata)
    print(f"Wrote {row_count} rows to {args.output}")
    print(f"Experiments: {', '.join(ordered_columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
