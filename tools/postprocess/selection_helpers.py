from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import sys
import tomllib
from typing import Any, Mapping


DISPLAY_LABELS_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "postprocess" / "display_labels.toml"
)


@lru_cache(maxsize=1)
def configured_display_labels() -> dict[str, str]:
    labels: dict[str, str] = {}

    try:
        with DISPLAY_LABELS_CONFIG_PATH.open("rb") as handle:
            payload = tomllib.load(handle)
    except FileNotFoundError:
        return labels
    except tomllib.TOMLDecodeError as error:
        print(
            f"Warning: {DISPLAY_LABELS_CONFIG_PATH}: invalid TOML ({error}); using canonical comparison tool names.",
            file=sys.stderr,
        )
        return labels

    configured_labels = payload.get("comparison_tool_labels")
    if configured_labels is None:
        return labels
    if not isinstance(configured_labels, dict):
        print(
            f"Warning: {DISPLAY_LABELS_CONFIG_PATH}: 'comparison_tool_labels' must be a table; using canonical comparison tool names.",
            file=sys.stderr,
        )
        return labels

    for comparison_tool, label in configured_labels.items():
        normalized_tool = str(comparison_tool).strip()
        normalized_label = str(label).strip()
        if normalized_tool and normalized_label:
            labels[normalized_tool] = normalized_label

    return labels


def default_display_label(comparison_tool: str) -> str:
    label = configured_display_labels().get(comparison_tool)
    if label is not None:
        return label
    return comparison_tool


def normalize_plot_groups(plot_groups: Any) -> str:
    if plot_groups is None:
        return ""

    normalized_groups: list[str] = []
    for raw_group in str(plot_groups).replace(";", "|").split("|"):
        group = raw_group.strip()
        if group and group not in normalized_groups:
            normalized_groups.append(group)
    return "|".join(normalized_groups)


def load_selected_configurations(
    selection_csv: Path,
    lookup_by_source_column: Mapping[str, Mapping[str, Any]],
    *,
    missing_context: str,
    empty_context: str,
) -> list[dict[str, Any]]:
    with selection_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit(f"{selection_csv}: CSV has no header")

        required_columns = {"comparison_tool", "source_column"}
        missing_columns = sorted(required_columns.difference(reader.fieldnames))
        if missing_columns:
            joined = ", ".join(missing_columns)
            raise SystemExit(f"{selection_csv}: missing required column(s): {joined}")

        rows = list(reader)

    selected_rows: list[dict[str, Any]] = []
    seen_comparison_tools: set[str] = set()
    skipped_source_columns: list[str] = []
    for row_number, selection_row in enumerate(rows, start=2):
        comparison_tool = str(selection_row["comparison_tool"]).strip()
        source_column = str(selection_row["source_column"]).strip()
        if not comparison_tool:
            raise SystemExit(f"{selection_csv} line {row_number}: empty comparison_tool")
        if not source_column:
            raise SystemExit(f"{selection_csv} line {row_number}: empty source_column")
        if comparison_tool in seen_comparison_tools:
            raise SystemExit(
                f"{selection_csv} line {row_number}: duplicate comparison_tool {comparison_tool!r}"
            )

        summary_row = lookup_by_source_column.get(source_column)
        if summary_row is None:
            skipped_source_columns.append(source_column)
            continue

        seen_comparison_tools.add(comparison_tool)
        if str(summary_row["comparison_tool"]).strip() != comparison_tool:
            raise SystemExit(
                f"{selection_csv} line {row_number}: comparison_tool {comparison_tool!r} "
                f"does not match summary metadata {summary_row['comparison_tool']!r}"
            )

        display_label = (
            str(selection_row.get("display_label", "")).strip()
            or default_display_label(comparison_tool)
        )
        selected_rows.append(
            {
                **dict(summary_row),
                "source_column": source_column,
                "comparison_tool": comparison_tool,
                "display_label": display_label,
                "plot_groups": normalize_plot_groups(selection_row.get("plot_groups", "")),
            }
        )

    if skipped_source_columns:
        joined = ", ".join(repr(source_column) for source_column in skipped_source_columns)
        print(f"{missing_context}: {joined}")

    if not selected_rows:
        print(empty_context)
        return []

    return selected_rows
