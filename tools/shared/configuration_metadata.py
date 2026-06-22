"""Shared metadata helpers for campaign-generated outputs.

This module records raw configuration values rather than tool-specific display
labels. Downstream reporting can decide how to present those values, while the
stored metadata remains stable and lossless across tools.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any


RUN_METADATA_FILENAME = "_run_metadata.json"
LABEL_FIELDS = (
    "searcher",
    "sym_size",
    "config",
    "cv_model",
)


def column_metadata_path(csv_path: str | Path) -> Path:
    """Return the JSON sidecar path used for per-column metadata."""
    return Path(csv_path).with_suffix(".metadata.json")


def _option_value(args: Sequence[str], option_name: str) -> str | None:
    prefix = option_name + "="
    for index, token in enumerate(args):
        if token.startswith(prefix):
            return token[len(prefix):]
        if token == option_name and index + 1 < len(args):
            return args[index + 1]
    return None


def derive_run_configuration(
    tool_name: str,
    destination_name: str,
    args_template: Sequence[str],
) -> dict[str, Any]:
    """Extract raw run-level metadata from one campaign run definition."""
    return {
        "source_column_prefix": destination_name,
        "tool_family": tool_name,
        "searcher": _option_value(args_template, "--search") or "default",
        "sym_size": _option_value(args_template, "--sym-size") or "all",
        "cv_model": _option_value(args_template, "--use-cv-model") or "all",
    }


def case_output_metadata(case_table: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the case-level metadata required by postprocessing.

    Runners provide the explicit benchmark config id, such as ``fix_pub`` or
    ``var_pub``. The helper keeps older metadata names readable as input only
    for existing tests and generated results.
    """
    explicit_config = case_table.get("config")
    explicit_public_mode = case_table.get("public_mode")
    explicit_suffix = case_table.get("source_column_suffix")
    explicit_sliced = case_table.get("sliced")

    if explicit_sliced is not None and not isinstance(explicit_sliced, bool):
        raise ValueError("case metadata field 'sliced' must be a boolean")

    sliced = bool(explicit_sliced)
    config = (
        explicit_config.strip()
        if isinstance(explicit_config, str) and explicit_config.strip()
        else None
    )
    public_mode = (
        explicit_public_mode.strip()
        if isinstance(explicit_public_mode, str) and explicit_public_mode.strip()
        else None
    )
    source_column_suffix = (
        explicit_suffix.strip()
        if isinstance(explicit_suffix, str) and explicit_suffix.strip()
        else None
    )

    if config is None:
        config = public_mode or source_column_suffix

    if config is None:
        raise ValueError("case metadata must define config explicitly")

    return {
        "config": config,
        "sliced": sliced,
    }


def configuration_label(metadata: Mapping[str, Any]) -> str:
    """Build a generic label from stored raw metadata fields."""
    label_parts: list[str] = []
    for field_name in LABEL_FIELDS:
        field_value = str(metadata.get(field_name, "")).strip()
        if field_value and field_value != "all":
            label_parts.append(f"{field_name}={field_value}")
    return ", ".join(label_parts) or "all"


def build_source_column(run_metadata: Mapping[str, Any], case_metadata: Mapping[str, Any]) -> str:
    """Build the merged-CSV source column for one run/case combination."""
    prefix = str(run_metadata["source_column_prefix"])
    suffix = str(case_metadata["config"])
    if bool(case_metadata.get("sliced")):
        return f"{prefix}_sliced_{suffix}"
    return f"{prefix}_{suffix}"


def build_column_metadata(
    run_metadata: Mapping[str, Any],
    case_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine run metadata and case metadata into one column record."""
    normalized_case_metadata = case_output_metadata(case_metadata)
    tool_family = str(run_metadata["tool_family"])
    sliced = bool(normalized_case_metadata.get("sliced"))
    metadata = {
        "source_column": build_source_column(run_metadata, normalized_case_metadata),
        "tool_family": tool_family,
        "comparison_tool": f"{tool_family}_sliced" if sliced else tool_family,
        "sliced": sliced,
        "searcher": str(run_metadata["searcher"]),
        "sym_size": str(run_metadata["sym_size"]),
        "config": str(normalized_case_metadata["config"]),
        "cv_model": str(run_metadata["cv_model"]),
    }
    metadata["configuration_label"] = configuration_label(metadata)
    return metadata


def write_run_metadata(root_dir: str | Path, by_run: Mapping[str, Mapping[str, Any]]) -> Path:
    """Write ``_run_metadata.json`` into a campaign output root."""
    output_path = Path(root_dir) / RUN_METADATA_FILENAME
    output_path.write_text(json.dumps({"runs": by_run}, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_run_metadata(root_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load the campaign run metadata written by :func:`write_run_metadata`."""
    input_path = Path(root_dir) / RUN_METADATA_FILENAME
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), dict):
        raise SystemExit(f"{input_path}: expected a JSON object with a 'runs' table")
    return {str(name): dict(metadata) for name, metadata in payload["runs"].items()}


def write_column_metadata(
    csv_path: str | Path,
    ordered_columns: Sequence[str],
    by_column: Mapping[str, Mapping[str, Any]],
) -> Path:
    """Write the metadata sidecar for one merged CSV."""
    output_path = column_metadata_path(csv_path)
    payload = {
        "columns": list(ordered_columns),
        "by_column": {column: dict(by_column[column]) for column in ordered_columns},
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_column_metadata_bundle(csv_path: str | Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Load column order and metadata from a CSV sidecar."""
    input_path = column_metadata_path(csv_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    columns = payload.get("columns")
    by_column = payload.get("by_column")
    if not isinstance(columns, list) or not isinstance(by_column, dict):
        raise SystemExit(f"{input_path}: expected 'columns' list and 'by_column' table")
    return [str(column) for column in columns], {str(key): dict(value) for key, value in by_column.items()}


def copy_column_metadata(input_csv: str | Path, output_csv: str | Path) -> Path:
    """Copy metadata to a new CSV path when the input already has a sidecar."""
    if not column_metadata_path(input_csv).is_file():
        return column_metadata_path(output_csv)
    ordered_columns, by_column = load_column_metadata_bundle(input_csv)
    return write_column_metadata(output_csv, ordered_columns, by_column)


def merge_column_metadata(output_csv: str | Path, input_csvs: Sequence[str | Path]) -> Path:
    """Merge multiple metadata sidecars into one output sidecar.

    Conflicting definitions for the same column are treated as a hard error so
    downstream reports never silently combine columns with different meaning.
    """
    ordered_columns: list[str] = []
    by_column: dict[str, dict[str, Any]] = {}
    for input_csv in input_csvs:
        if not column_metadata_path(input_csv).is_file():
            continue
        input_columns, input_metadata = load_column_metadata_bundle(input_csv)
        for column in input_columns:
            metadata = input_metadata[column]
            existing = by_column.get(column)
            if existing is not None and existing != metadata:
                raise SystemExit(
                    f"conflicting metadata for column {column!r} while merging column metadata"
                )
            if column not in by_column:
                ordered_columns.append(column)
                by_column[column] = metadata
    if not ordered_columns:
        return column_metadata_path(output_csv)
    return write_column_metadata(output_csv, ordered_columns, by_column)
