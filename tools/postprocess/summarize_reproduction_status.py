#!/usr/bin/env python3
"""Summarize reproduction outcomes across merged campaign outputs.

The tables produced here collapse many raw positives into status counts per
exact configuration, with optional best-of and by-library reporting layers.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.postprocess.apply_sliced_map import load_sliced_map
from tools.postprocess.csv_to_latex_table import escape_latex
from tools.postprocess.filter_merged_results import load_filters, location_matches
from tools.postprocess.selection_helpers import load_selected_configurations
from tools.shared.configuration_metadata import build_column_metadata, load_run_metadata
from tools.shared.result_schema import (
    KIND_BRANCH,
    KIND_MEMORY,
    REPRODUCED_STATUSES,
    STATUS_IDENTICAL_TRACE,
    STATUS_LOCATION_MISMATCH,
    STATUS_NOT_REPRODUCED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    normalize_result_kind,
)


INCONSISTENT_STATUS = "inconsistent_across_repetitions"
TOTAL_COLUMN = "total"
STATUS_COLUMNS = [
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_IDENTICAL_TRACE,
    STATUS_LOCATION_MISMATCH,
    STATUS_NOT_REPRODUCED,
    INCONSISTENT_STATUS,
]
OUTPUT_COLUMNS = [
    "configuration",
    "configuration_label",
    "comparison_tool",
    "tool_family",
    "sliced",
    "searcher",
    "sym_size",
    "public_mode",
    "concretization_policy",
    *STATUS_COLUMNS,
    "total_filtered_positives",
]

SIDE_CHANNEL_BRANCH = KIND_BRANCH
SIDE_CHANNEL_MEMORY = KIND_MEMORY
SIDE_CHANNEL_COLUMNS = [SIDE_CHANNEL_BRANCH, SIDE_CHANNEL_MEMORY]


def _empty_status_counts() -> dict[str, int]:
    return {status_name: 0 for status_name in STATUS_COLUMNS}


def _empty_side_channel_status_counts() -> dict[str, dict[str, int]]:
    return {
        side_channel_kind: _empty_status_counts()
        for side_channel_kind in SIDE_CHANNEL_COLUMNS
    }


def _selected_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_best_of.csv")


def _selected_latex_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_best_of.tex")


def _by_library_output_prefix(output_path: Path) -> Path:
    selected_output_path = _selected_output_path(output_path)
    return selected_output_path.with_name(
        f"{selected_output_path.stem}_by_library"
    ).with_suffix("")


def _basename_only(path_value: str) -> str:
    return os.path.basename(path_value.replace("\\", "/"))


def _read_payload(json_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        rows = payload.get("data")
        if isinstance(rows, list):
            metadata = payload.get("metadata")
            if metadata is not None and not isinstance(metadata, dict):
                raise SystemExit(f"{json_path}: expected metadata to be a JSON object")
            return [row for row in rows if isinstance(row, dict)], dict(metadata or {})
        raise SystemExit(f"{json_path}: expected a top-level 'data' list")

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)], {}

    raise SystemExit(f"{json_path}: expected a JSON object or list")


def _location_context(
    *,
    json_path: Path,
    row_number: int,
    library: str,
    filename: str,
    line: int,
    column: int | None,
) -> str:
    column_text = "?" if column is None else str(column)
    return f"{json_path} data[{row_number}] ({library}, {filename}, {line}, {column_text})"


def _normalize_status_name(status_name: Any, *, context: str) -> str:
    if not isinstance(status_name, str):
        raise SystemExit(f"{context}: reproduced_status keys must be strings")

    normalized = status_name.strip().lower()
    if normalized not in REPRODUCED_STATUSES:
        raise SystemExit(
            f"{context}: unknown reproduced_status {status_name!r}; expected one of {sorted(REPRODUCED_STATUSES)}"
        )
    return normalized


def _resolve_status_bucket(status_payload: Any, *, context: str) -> str:
    if isinstance(status_payload, str):
        return _normalize_status_name(status_payload, context=context)

    if not isinstance(status_payload, dict) or not status_payload:
        raise SystemExit(f"{context}: reproduced_status must be a non-empty dict or string")

    positive_statuses: set[str] = set()
    for raw_status, raw_count in status_payload.items():
        normalized_status = _normalize_status_name(raw_status, context=context)
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            raise SystemExit(
                f"{context}: reproduced_status count for {normalized_status!r} must be an integer"
            ) from None

        if count < 0:
            raise SystemExit(
                f"{context}: reproduced_status count for {normalized_status!r} must be non-negative"
            )
        if count > 0:
            positive_statuses.add(normalized_status)

    if not positive_statuses:
        raise SystemExit(f"{context}: reproduced_status map has no positive counts")
    if len(positive_statuses) == 1:
        return next(iter(positive_statuses))
    return INCONSISTENT_STATUS


def _resolve_location(
    row: dict[str, Any],
    *,
    library_hint: str,
    sliced: bool,
    sliced_map: Mapping[tuple[str, str, int, int], tuple[str, int, int]] | None,
    keep_unmapped: bool,
    json_path: Path,
    row_number: int,
) -> tuple[str, str, int, int | None, str]:
    filename = row.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        raise SystemExit(f"{json_path} data[{row_number}]: missing filename")

    try:
        line = int(row.get("line"))
    except (TypeError, ValueError):
        raise SystemExit(f"{json_path} data[{row_number}]: invalid line {row.get('line')!r}") from None

    column_value = row.get("column")
    column: int | None
    if column_value is None or column_value == "":
        column = None
    else:
        try:
            column = int(column_value)
        except (TypeError, ValueError):
            raise SystemExit(
                f"{json_path} data[{row_number}]: invalid column {column_value!r}"
            ) from None

    # Keep library keys consistent with merge_results: the JSON filename encodes
    # the benchmark identifier, while row-level `library` values may be only a
    # coarse family label such as "unknown".
    library = library_hint

    filename = _basename_only(filename)
    if not filename:
        raise SystemExit(f"{json_path} data[{row_number}]: missing filename basename")

    if sliced:
        if sliced_map is None:
            raise SystemExit(
                f"{json_path}: encountered sliced results but no --sliced-map was provided"
            )
        if column is None:
            raise SystemExit(
                f"{json_path} data[{row_number}]: sliced rows require a concrete column for relabeling"
            )

        target = sliced_map.get((library, filename, line, column))
        if target is None:
            context = _location_context(
                json_path=json_path,
                row_number=row_number,
                library=library,
                filename=filename,
                line=line,
                column=column,
            )
            if not keep_unmapped:
                raise SystemExit(f"{context}: no sliced-map entry found")
        else:
            filename, line, column = target

    context = _location_context(
        json_path=json_path,
        row_number=row_number,
        library=library,
        filename=filename,
        line=line,
        column=column,
    )
    return library, filename, line, column, context


def _resolve_side_channel_kind(row: Mapping[str, Any], json_path: Path) -> str:
    raw_kind = row.get("kind")
    if raw_kind is None:
        raise SystemExit(f"{json_path}: missing required row field 'kind'")
    try:
        return normalize_result_kind(raw_kind)
    except (TypeError, ValueError) as error:
        raise SystemExit(f"{json_path}: invalid row field 'kind': {error}") from error


def collect_reproduction_status_counts(
    root_dir: Path,
    *,
    filter_path: Path,
    sliced_map_path: Path | None,
    keep_unmapped: bool,
) -> tuple[
    list[str],
    dict[str, dict[str, int]],
    dict[str, dict[str, dict[str, int]]],
    dict[str, dict[str, dict[str, dict[str, int]]]],
    dict[str, dict[str, Any]],
]:
    """Collect reproduction-status counts for each exact configuration column."""
    if not root_dir.is_dir():
        raise SystemExit(f"Input '{root_dir}' is not a directory")

    filters = load_filters(filter_path)
    sliced_map = load_sliced_map(sliced_map_path) if sliced_map_path else None

    ordered_configurations: list[str] = []
    counts_by_configuration: dict[str, dict[str, int]] = {}
    counts_by_configuration_and_library: dict[str, dict[str, dict[str, int]]] = {}
    counts_by_configuration_library_and_kind: dict[
        str,
        dict[str, dict[str, dict[str, int]]],
    ] = {}
    configuration_metadata: dict[str, dict[str, Any]] = {}
    run_metadata_by_name = load_run_metadata(root_dir)

    run_names = sorted(run_metadata_by_name)
    for run_name in run_names:
        run_dir = root_dir / run_name
        if not run_dir.is_dir():
            raise SystemExit(f"{root_dir}: run metadata references missing run directory {run_name!r}")
        run_metadata = run_metadata_by_name[run_name]
        for entry in sorted(run_dir.iterdir(), key=lambda path: path.name):
            if not entry.is_file() or entry.suffix.lower() != ".json":
                continue

            rows, case_metadata = _read_payload(entry)
            if not case_metadata:
                raise SystemExit(f"{entry}: missing required payload metadata")
            metadata = build_column_metadata(run_metadata, case_metadata)
            configuration = str(metadata["source_column"])
            library_hint = case_metadata.get("library_key")
            if not isinstance(library_hint, str) or not library_hint:
                raise SystemExit(f"{entry}: payload metadata is missing non-empty library_key")
            if configuration not in counts_by_configuration:
                ordered_configurations.append(configuration)
                counts_by_configuration[configuration] = _empty_status_counts()
                counts_by_configuration_and_library[configuration] = {}
                counts_by_configuration_library_and_kind[configuration] = {}
                configuration_metadata[configuration] = metadata

            for row_number, row in enumerate(rows, start=1):
                library, filename, line, column, context = _resolve_location(
                    row,
                    library_hint=library_hint,
                    sliced=bool(case_metadata.get("sliced")),
                    sliced_map=sliced_map,
                    keep_unmapped=keep_unmapped,
                    json_path=entry,
                    row_number=row_number,
                )
                if not location_matches(filters, library=library, file=filename, line=line):
                    continue

                library_counts = counts_by_configuration_and_library[configuration].setdefault(
                    library,
                    _empty_status_counts(),
                )
                kind_counts = counts_by_configuration_library_and_kind[configuration].setdefault(
                    library,
                    _empty_side_channel_status_counts(),
                )
                bucket = _resolve_status_bucket(row.get("reproduced_status"), context=context)
                side_channel_kind = _resolve_side_channel_kind(row, entry)
                counts_by_configuration[configuration][bucket] += 1
                library_counts[bucket] += 1
                kind_counts[side_channel_kind][bucket] += 1

    if not ordered_configurations:
        raise SystemExit(f"No top-level result JSON files found under '{root_dir}'")

    return (
        ordered_configurations,
        counts_by_configuration,
        counts_by_configuration_and_library,
        counts_by_configuration_library_and_kind,
        configuration_metadata,
    )


def _build_summary_rows(
    ordered_configurations: Sequence[str],
    counts_by_configuration: Mapping[str, Mapping[str, int]],
    configuration_metadata: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output_rows: list[dict[str, Any]] = []
    for configuration in ordered_configurations:
        metadata = configuration_metadata[configuration]
        counts = counts_by_configuration[configuration]
        output_rows.append(
            {
                "configuration": configuration,
                "configuration_label": metadata["configuration_label"],
                "comparison_tool": metadata["comparison_tool"],
                "tool_family": metadata["tool_family"],
                "sliced": metadata["sliced"],
                "searcher": metadata["searcher"],
                "sym_size": metadata["sym_size"],
                "public_mode": metadata["public_mode"],
                "concretization_policy": metadata["concretization_policy"],
                **{status_name: counts[status_name] for status_name in STATUS_COLUMNS},
                "total_filtered_positives": sum(counts.values()),
            }
        )

    return output_rows


def _write_summary_csv(output_rows: Sequence[Mapping[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    return output_path


def summarize_reproduction_statuses(
    root_dir: Path,
    *,
    filter_path: Path,
    output_path: Path,
    sliced_map_path: Path | None,
    keep_unmapped: bool,
) -> tuple[int, int]:
    """Write the main reproduction-status summary CSV."""
    (
        ordered_configurations,
        counts_by_configuration,
        _,
        _,
        configuration_metadata,
    ) = collect_reproduction_status_counts(
        root_dir,
        filter_path=filter_path,
        sliced_map_path=sliced_map_path,
        keep_unmapped=keep_unmapped,
    )

    output_rows = _build_summary_rows(
        ordered_configurations,
        counts_by_configuration,
        configuration_metadata,
    )
    _write_summary_csv(output_rows, output_path)

    return len(output_rows), sum(row["total_filtered_positives"] for row in output_rows)


def _load_selected_configurations(
    selection_csv: Path,
    summary_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    lookup = {
        str(row["configuration"]).strip(): dict(row)
        for row in summary_rows
    }
    selected_rows = load_selected_configurations(
        selection_csv,
        lookup,
        missing_context="Skipping selection rows whose source_column was not present in the summary",
        empty_context="No selected configurations matched the summary; skipping selected summary outputs.",
    )
    for selected_row in selected_rows:
        for status_name in STATUS_COLUMNS:
            selected_row[status_name] = int(selected_row[status_name])
        selected_row["summary_row"] = dict(selected_row)
    return selected_rows


def _load_selection_rows(
    selection_csv: Path,
    summary_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    selected_configurations = _load_selected_configurations(selection_csv, summary_rows)
    return [
        {
            "configuration": str(selected_configuration["display_label"]),
            **{
                status_name: int(selected_configuration[status_name])
                for status_name in STATUS_COLUMNS
            },
            TOTAL_COLUMN: sum(
                int(selected_configuration[status_name])
                for status_name in STATUS_COLUMNS
            ),
        }
        for selected_configuration in selected_configurations
    ]


def _nonzero_status_columns(selected_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        status_name
        for status_name in STATUS_COLUMNS
        if any(int(row[status_name]) != 0 for row in selected_rows)
    ]


def _write_selected_csv(selected_rows: Sequence[Mapping[str, Any]], output_path: Path) -> Path:
    kept_status_columns = _nonzero_status_columns(selected_rows)
    fieldnames = ["configuration", *kept_status_columns, TOTAL_COLUMN]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in selected_rows:
            writer.writerow({field: row[field] for field in fieldnames})

    return output_path


def _selected_rows_to_latex(selected_rows: Sequence[Mapping[str, Any]]) -> str:
    kept_status_columns = _nonzero_status_columns(selected_rows)
    fieldnames = ["configuration", *kept_status_columns, TOTAL_COLUMN]
    alignment = "l" + "r" * (len(kept_status_columns) + 1)

    lines = [
        rf"\begin{{NiceTabular}}{{{alignment}}}",
        r"    \toprule",
        "    " + " & ".join(escape_latex(name) for name in fieldnames) + r" \\",
        r"    \midrule",
    ]
    for row in selected_rows:
        cells = [escape_latex(str(row["configuration"]))]
        cells.extend(escape_latex(str(int(row[status_name]))) for status_name in kept_status_columns)
        cells.append(escape_latex(str(int(row[TOTAL_COLUMN]))))
        lines.append("    " + " & ".join(cells) + r" \\")
    lines.extend([
        r"    \bottomrule",
        r"\end{NiceTabular}",
    ])
    return "\n".join(lines) + "\n"


def _write_selected_latex(selected_rows: Sequence[Mapping[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_selected_rows_to_latex(selected_rows), encoding="utf-8")
    return output_path


def write_selected_outputs(
    selection_csv: Path,
    summary_rows: Sequence[Mapping[str, Any]],
    *,
    selected_output_path: Path,
    selected_latex_output_path: Path,
) -> tuple[Path, Path]:
    """Write CSV and LaTeX outputs for one selected configuration per tool."""
    selected_rows = _load_selection_rows(selection_csv, summary_rows)
    csv_path = _write_selected_csv(selected_rows, selected_output_path)
    latex_path = _write_selected_latex(selected_rows, selected_latex_output_path)
    return csv_path, latex_path


def _build_unique_display_labels(
    selected_configurations: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    rename_map: dict[str, str] = {}
    label_counts: dict[str, int] = {}
    for selected_configuration in selected_configurations:
        source_column = str(selected_configuration["source_column"])
        label = str(selected_configuration["display_label"])
        count = label_counts.get(label, 0) + 1
        label_counts[label] = count
        rename_map[source_column] = label if count == 1 else f"{label} ({count})"

    return rename_map


def _selected_configuration_group_order(
    selected_configurations: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[int]]:
    grouped_rows: dict[str, list[dict[str, Any]]] = {
        "klee_cf": [],
        "internal": [],
        "external": [],
        "other": [],
    }

    for selected_configuration in selected_configurations:
        comparison_tool = str(selected_configuration.get("comparison_tool", "")).strip()
        normalized_groups = str(selected_configuration.get("plot_groups", "")).strip()
        groups = set(normalized_groups.split("|")) if normalized_groups else set()

        if comparison_tool == "klee_cf":
            group_name = "klee_cf"
        elif "internal" in groups:
            group_name = "internal"
        elif "external" in groups:
            group_name = "external"
        else:
            group_name = "other"

        grouped_rows[group_name].append(dict(selected_configuration))

    ordered_group_names = ["klee_cf", "internal", "external", "other"]
    ordered_rows = [
        row
        for group_name in ordered_group_names
        for row in grouped_rows[group_name]
    ]
    group_sizes = [len(grouped_rows[group_name]) for group_name in ordered_group_names]
    return ordered_rows, group_sizes


def _selected_by_library_rows(
    selected_configurations: Sequence[Mapping[str, Any]],
    counts_by_configuration_library_and_kind: Mapping[
        str,
        Mapping[str, Mapping[str, Mapping[str, int]]],
    ],
) -> tuple[list[str], list[str], list[dict[str, str]], list[int]] | None:
    if not selected_configurations:
        raise SystemExit("Selection CSV is empty")

    ordered_configurations, group_sizes = _selected_configuration_group_order(
        selected_configurations
    )
    label_map = _build_unique_display_labels(selected_configurations)
    libraries = sorted(
        {
            library
            for selected_configuration in ordered_configurations
            for library in counts_by_configuration_library_and_kind.get(
                str(selected_configuration["source_column"]),
                {},
            )
        }
    )
    if not libraries:
        return None

    csv_fieldnames = [
        "library",
        *[
            fieldname
            for selected_configuration in ordered_configurations
            for fieldname in (
                f"{label_map[str(selected_configuration['source_column'])]}_control_flow",
                f"{label_map[str(selected_configuration['source_column'])]}_memory",
            )
        ],
    ]
    latex_fieldnames = [
        "library",
        *[
            label_map[str(selected_configuration["source_column"])]
            for selected_configuration in ordered_configurations
        ],
    ]
    rows: list[dict[str, str]] = []
    for library in libraries:
        row: dict[str, str] = {"library": library}
        for selected_configuration in ordered_configurations:
            source_column = str(selected_configuration["source_column"])
            label = label_map[source_column]
            library_counts = counts_by_configuration_library_and_kind.get(source_column, {}).get(
                library,
                {},
            )
            branch_successes = int(
                library_counts.get(SIDE_CHANNEL_BRANCH, {}).get(STATUS_SUCCESS, 0)
            )
            memory_successes = int(
                library_counts.get(SIDE_CHANNEL_MEMORY, {}).get(STATUS_SUCCESS, 0)
            )
            row[f"{label}_control_flow"] = str(branch_successes)
            row[f"{label}_memory"] = str(memory_successes)
            row[label] = f"{branch_successes}/{memory_successes}"
        rows.append(row)

    return csv_fieldnames, latex_fieldnames, rows, group_sizes


def _selected_by_library_alignment(group_sizes: Sequence[int]) -> str:
    alignment = ["l"]
    nonzero_group_sizes = [group_size for group_size in group_sizes if group_size > 0]
    for index, group_size in enumerate(nonzero_group_sizes):
        alignment.append("r" * group_size)
        if index != len(nonzero_group_sizes) - 1:
            alignment.append("|")
    return "".join(alignment)


def _write_selected_by_library_csv(
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({fieldname: row[fieldname] for fieldname in fieldnames})

    return output_path


def _selected_by_library_rows_to_latex(
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    group_sizes: Sequence[int],
) -> str:
    alignment = _selected_by_library_alignment(group_sizes)
    lines = [
        rf"\begin{{NiceTabular}}{{{alignment}}}",
        r"    \toprule",
        "    " + " & ".join(escape_latex(name) for name in fieldnames) + r" \\",
        r"    \midrule",
    ]
    for row in rows:
        cells = [escape_latex(str(row["library"]))]
        cells.extend(escape_latex(str(row[fieldname])) for fieldname in fieldnames[1:])
        lines.append("    " + " & ".join(cells) + r" \\")
    lines.extend([
        r"    \bottomrule",
        r"\end{NiceTabular}",
    ])
    return "\n".join(lines) + "\n"


def _write_selected_by_library_latex(
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, str]],
    group_sizes: Sequence[int],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _selected_by_library_rows_to_latex(fieldnames, rows, group_sizes),
        encoding="utf-8",
    )
    return output_path


def write_selected_by_library_outputs(
    selected_configurations: Sequence[Mapping[str, Any]],
    counts_by_configuration_library_and_kind: Mapping[
        str,
        Mapping[str, Mapping[str, Mapping[str, int]]],
    ],
    *,
    output_prefix: Path,
) -> tuple[Path, Path] | None:
    selected_rows = _selected_by_library_rows(
        selected_configurations,
        counts_by_configuration_library_and_kind,
    )
    if selected_rows is None:
        return None
    csv_fieldnames, latex_fieldnames, rows, group_sizes = selected_rows
    csv_path = _write_selected_by_library_csv(
        csv_fieldnames,
        rows,
        output_prefix.with_suffix(".csv"),
    )
    latex_path = _write_selected_by_library_latex(
        latex_fieldnames,
        rows,
        group_sizes,
        output_prefix.with_suffix(".tex"),
    )
    return csv_path, latex_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize merged reproduced_status JSON payloads into one filtered count row per configuration."
        )
    )
    parser.add_argument(
        "root_dir",
        help=(
            "Directory containing configuration subdirectories with top-level merged JSON files "
            "(for example the experiment output root)."
        ),
    )
    parser.add_argument(
        "-f",
        "--filter",
        dest="filter_csv",
        required=True,
        help="Filter CSV path with library/file/line_start/line_end columns",
    )
    parser.add_argument(
        "-s",
        "--sliced-map",
        dest="sliced_map_csv",
        help="Optional sliced_map.csv path; required when sliced JSON inputs are present",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output CSV path",
    )
    parser.add_argument(
        "--keep-unmapped",
        action="store_true",
        help="Keep sliced rows without a map entry on their sliced coordinates instead of failing",
    )
    parser.add_argument(
        "--selection-csv",
        help=(
            "Optional best-of selection CSV with comparison_tool, source_column, and optional display_label; "
            "writes reduced CSV and LaTeX outputs."
        ),
    )
    parser.add_argument(
        "--selected-output",
        help="Optional output CSV path for the best-of selection table",
    )
    parser.add_argument(
        "--selected-latex-output",
        help="Optional output .tex path for the best-of selection table",
    )
    parser.add_argument(
        "--by-library-selection-tables",
        action="store_true",
        help=(
            "Write one per-library success-count CSV and LaTeX table for the selected configurations, "
            "ordered as KLEE-CF, other internal KLEE-based tools, then external tools. "
            "Requires --selection-csv."
        ),
    )
    parser.add_argument(
        "--by-library-output-prefix",
        help=(
            "Optional output prefix for the per-library selection table; writes PREFIX.csv and PREFIX.tex."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.by_library_selection_tables and not args.selection_csv:
        parser.error("--by-library-selection-tables requires --selection-csv")

    output_path = Path(args.output)
    (
        ordered_configurations,
        counts_by_configuration,
        counts_by_configuration_and_library,
        counts_by_configuration_library_and_kind,
        configuration_metadata,
    ) = collect_reproduction_status_counts(
        Path(args.root_dir),
        filter_path=Path(args.filter_csv),
        sliced_map_path=Path(args.sliced_map_csv) if args.sliced_map_csv else None,
        keep_unmapped=args.keep_unmapped,
    )
    summary_rows = _build_summary_rows(
        ordered_configurations,
        counts_by_configuration,
        configuration_metadata,
    )
    _write_summary_csv(summary_rows, output_path)
    row_count = len(summary_rows)
    total_count = sum(row["total_filtered_positives"] for row in summary_rows)
    print(
        f"Wrote {args.output} with {row_count} configuration row(s) "
        f"covering {total_count} filtered positive(s)."
    )

    if args.selection_csv:
        selected_configurations = _load_selected_configurations(
            Path(args.selection_csv),
            summary_rows,
        )
        if selected_configurations:
            selected_rows = [
                {
                    "configuration": str(selected_configuration["display_label"]),
                    **{
                        status_name: int(selected_configuration[status_name])
                        for status_name in STATUS_COLUMNS
                    },
                    TOTAL_COLUMN: sum(
                        int(selected_configuration[status_name])
                        for status_name in STATUS_COLUMNS
                    ),
                }
                for selected_configuration in selected_configurations
            ]
            selected_output_path = (
                Path(args.selected_output)
                if args.selected_output
                else _selected_output_path(output_path)
            )
            selected_latex_output_path = (
                Path(args.selected_latex_output)
                if args.selected_latex_output
                else _selected_latex_output_path(output_path)
            )
            csv_path = _write_selected_csv(selected_rows, selected_output_path)
            latex_path = _write_selected_latex(selected_rows, selected_latex_output_path)
            print(f"Wrote {csv_path}")
            print(f"Wrote {latex_path}")

            if args.by_library_selection_tables:
                by_library_output_prefix = (
                    Path(args.by_library_output_prefix)
                    if args.by_library_output_prefix
                    else _by_library_output_prefix(output_path)
                )
                selected_by_library_outputs = write_selected_by_library_outputs(
                    selected_configurations,
                    counts_by_configuration_library_and_kind,
                    output_prefix=by_library_output_prefix,
                )
                if selected_by_library_outputs is None:
                    print("Skipping by-library selection tables: selected configurations have no filtered library counts")
                else:
                    grouped_csv_path, grouped_latex_path = selected_by_library_outputs
                    print(f"Wrote {grouped_csv_path}")
                    print(f"Wrote {grouped_latex_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
