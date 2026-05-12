from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


RUN_METADATA_FILENAME = "_run_metadata.json"
MODE_SUFFIXES = (
    "var_pub_lim_loop_break",
    "var_pub",
    "fix_pub",
)
KLEE_LIKE_TOOLS = {"klee_cf", "klee_eager", "self_comp"}


def column_metadata_path(csv_path: str | Path) -> Path:
    return Path(csv_path).with_suffix(".metadata.json")


def normalize_searcher(raw_searcher: str | None, *, tool_name: str) -> str:
    if tool_name not in KLEE_LIKE_TOOLS:
        return "default"
    if not raw_searcher or raw_searcher == "random-path,nurs:covnew":
        return "default"
    if raw_searcher == "dfs":
        return "dfs"
    if raw_searcher == "random-path,dfs":
        return "rand_path_dfs"
    return raw_searcher.replace(":", "_").replace(",", "_").replace("-", "_")


def _option_value(args: Sequence[str], option_name: str) -> str | None:
    for index, token in enumerate(args):
        if token == option_name and index + 1 < len(args):
            return args[index + 1]
    return None


def derive_run_configuration(
    tool_name: str,
    destination_name: str,
    args_template: Sequence[str],
) -> dict[str, Any]:
    sym_size = _option_value(args_template, "--sym-size") or "all"
    concretization_policy = "default"
    if tool_name == "klee_cf" and _option_value(args_template, "--concretize-on-solver-timeout") == "false":
        concretization_policy = "no_conc"
    return {
        "source_column_prefix": destination_name,
        "tool_family": tool_name,
        "searcher": normalize_searcher(_option_value(args_template, "--search"), tool_name=tool_name),
        "sym_size": str(sym_size),
        "concretization_policy": concretization_policy,
    }


def _candidate_case_names(case_table: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("source_column_suffix", "result_name", "json_name", "stats_file", "outfile"):
        value = case_table.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(Path(value).stem)
    return candidates


def _derive_suffix_from_name(name: str) -> str | None:
    cleaned = name.replace("_self_comp", "").replace("_sliced", "")
    for suffix in MODE_SUFFIXES:
        tail = f"_{suffix}"
        if cleaned == suffix or cleaned.endswith(tail):
            return suffix
    return None


def case_output_metadata(case_table: Mapping[str, Any]) -> dict[str, Any]:
    explicit_suffix = case_table.get("source_column_suffix")
    explicit_public_mode = case_table.get("public_mode")
    explicit_sliced = case_table.get("sliced")

    if explicit_sliced is not None and not isinstance(explicit_sliced, bool):
        raise ValueError("case metadata field 'sliced' must be a boolean")

    candidate_names = _candidate_case_names(case_table)
    sliced = bool(explicit_sliced)
    for candidate in candidate_names:
        if "_sliced" in candidate:
            sliced = True

    if isinstance(explicit_suffix, str) and explicit_suffix.strip():
        source_column_suffix = explicit_suffix.strip()
    else:
        source_column_suffix = None
        for candidate in candidate_names:
            source_column_suffix = _derive_suffix_from_name(candidate)
            if source_column_suffix is not None:
                break

    if isinstance(explicit_public_mode, str) and explicit_public_mode.strip():
        public_mode = explicit_public_mode.strip()
    else:
        public_mode = source_column_suffix

    if source_column_suffix is None or public_mode is None:
        raise ValueError(
            "case metadata must define source_column_suffix/public_mode explicitly or via result_name/json_name/stats_file/outfile"
        )

    return {
        "source_column_suffix": source_column_suffix,
        "public_mode": public_mode,
        "sliced": sliced,
    }


def configuration_label(metadata: Mapping[str, Any]) -> str:
    tool_family = str(metadata["tool_family"])
    searcher = str(metadata["searcher"])
    sym_size = str(metadata["sym_size"])
    public_mode = str(metadata["public_mode"])
    concretization_policy = str(metadata["concretization_policy"])

    label_parts: list[str] = []
    if tool_family in KLEE_LIKE_TOOLS:
        label_parts.append(f"search={searcher}")
    if sym_size != "all":
        label_parts.append(f"sym={sym_size}")
    if public_mode != "all":
        label_parts.append(f"mode={public_mode}")
    if concretization_policy != "default":
        label_parts.append(f"conc={concretization_policy}")
    return ", ".join(label_parts) or "default"


def build_source_column(run_metadata: Mapping[str, Any], case_metadata: Mapping[str, Any]) -> str:
    prefix = str(run_metadata["source_column_prefix"])
    suffix = str(case_metadata["source_column_suffix"])
    if bool(case_metadata.get("sliced")):
        return f"{prefix}_sliced_{suffix}"
    return f"{prefix}_{suffix}"


def build_column_metadata(
    run_metadata: Mapping[str, Any],
    case_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    tool_family = str(run_metadata["tool_family"])
    sliced = bool(case_metadata.get("sliced"))
    metadata = {
        "source_column": build_source_column(run_metadata, case_metadata),
        "tool_family": tool_family,
        "comparison_tool": f"{tool_family}_sliced" if sliced else tool_family,
        "sliced": sliced,
        "searcher": str(run_metadata["searcher"]),
        "sym_size": str(run_metadata["sym_size"]),
        "public_mode": str(case_metadata["public_mode"]),
        "concretization_policy": str(run_metadata["concretization_policy"]),
        "raw_suffix": str(case_metadata["source_column_suffix"]),
        "normalized_suffix": str(case_metadata["public_mode"]),
    }
    metadata["configuration_label"] = configuration_label(metadata)
    return metadata


def write_run_metadata(root_dir: str | Path, by_run: Mapping[str, Mapping[str, Any]]) -> Path:
    output_path = Path(root_dir) / RUN_METADATA_FILENAME
    output_path.write_text(json.dumps({"runs": by_run}, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_run_metadata(root_dir: str | Path) -> dict[str, dict[str, Any]]:
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
    output_path = column_metadata_path(csv_path)
    payload = {
        "columns": list(ordered_columns),
        "by_column": {column: dict(by_column[column]) for column in ordered_columns},
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path


def load_column_metadata_bundle(csv_path: str | Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    input_path = column_metadata_path(csv_path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    columns = payload.get("columns")
    by_column = payload.get("by_column")
    if not isinstance(columns, list) or not isinstance(by_column, dict):
        raise SystemExit(f"{input_path}: expected 'columns' list and 'by_column' table")
    return [str(column) for column in columns], {str(key): dict(value) for key, value in by_column.items()}


def copy_column_metadata(input_csv: str | Path, output_csv: str | Path) -> Path:
    if not column_metadata_path(input_csv).is_file():
        return column_metadata_path(output_csv)
    ordered_columns, by_column = load_column_metadata_bundle(input_csv)
    return write_column_metadata(output_csv, ordered_columns, by_column)


def merge_column_metadata(output_csv: str | Path, input_csvs: Sequence[str | Path]) -> Path:
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