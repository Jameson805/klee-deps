#!/usr/bin/env python3

import argparse
import json
import math
import os
import re
import sys
from glob import glob
from typing import Any, Dict, List, Optional, Sequence, Tuple


FINAL_COLUMN_ORDER = [
    "filename",
    "line",
    "column",
    "visit_count",
    "non_ct_count",
    "visit_time",
    "non_ct_time",
    "code",
    "counterexamples",
]


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _natural_key(text: str) -> List[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def _basename_only(path_value: str) -> str:
    # Normalize both Unix and Windows-style separators, then keep only the last path part.
    return os.path.basename(path_value.replace("\\", "/"))


def _geometric_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    cleaned = [value for value in values if math.isfinite(value) and value >= 0.0]
    if len(cleaned) != len(values):
        return None
    if any(value == 0.0 for value in cleaned):
        return 0.0
    return math.exp(sum(math.log(value) for value in cleaned) / len(cleaned))


def _read_rows(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        return []

    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    return []


def _group_input_files(dst_dir: str) -> Dict[str, List[str]]:
    pattern = os.path.join(dst_dir, "*", "*.json")
    grouped: Dict[str, List[str]] = {}
    for path in glob(pattern):
        base = os.path.basename(path)
        grouped.setdefault(base, []).append(path)

    for base in grouped:
        grouped[base] = sorted(grouped[base], key=lambda p: _natural_key(os.path.basename(os.path.dirname(p))))
    return grouped


def _merge_single_experiment(paths: Sequence[str]) -> List[Dict[str, Any]]:
    by_location: Dict[Tuple[str, int, Optional[int]], Dict[str, Any]] = {}

    for path in paths:
        rows = _read_rows(path)
        for row in rows:
            if "reproduced" in row and not _is_true(row.get("reproduced")):
                continue

            filename = row.get("filename")
            line = _to_int(row.get("line"))
            column = _to_int(row.get("column"))
            visit_count = _to_float(row.get("visit_count"))
            non_ct_count = _to_float(row.get("non_ct_count"))
            visit_time = _to_float(row.get("visit_time"))
            non_ct_time = _to_float(row.get("non_ct_time"))

            if not isinstance(filename, str) or filename == "":
                continue
            filename = _basename_only(filename)
            if filename == "":
                continue
            if line is None:
                continue
            if non_ct_time is None:
                continue

            key = (filename, line, column)
            slot = by_location.setdefault(
                key,
                {
                    "visit_count_values": [],
                    "non_ct_count_values": [],
                    "visit_time_values": [],
                    "non_ct_time_values": [],
                    "code": None,
                    "counterexamples": None,
                },
            )

            if visit_count is not None:
                slot["visit_count_values"].append(visit_count)
            if non_ct_count is not None:
                slot["non_ct_count_values"].append(non_ct_count)
            if visit_time is not None:
                slot["visit_time_values"].append(visit_time)
            slot["non_ct_time_values"].append(non_ct_time)

            if slot["code"] is None and row.get("code") is not None:
                slot["code"] = row.get("code")
            if slot["counterexamples"] is None and row.get("counterexamples") is not None:
                slot["counterexamples"] = row.get("counterexamples")

    merged_rows: List[Dict[str, Any]] = []
    for (filename, line, column), slot in sorted(
        by_location.items(),
        key=lambda item: (item[0][0], item[0][1], -1 if item[0][2] is None else item[0][2]),
    ):
        visit_count = _geometric_mean(slot["visit_count_values"])
        non_ct_count = _geometric_mean(slot["non_ct_count_values"])
        visit_time = _geometric_mean(slot["visit_time_values"])
        non_ct_time = _geometric_mean(slot["non_ct_time_values"])

        if non_ct_time is None:
            continue

        row = {
            "filename": filename,
            "line": line,
            "non_ct_time": non_ct_time,
            "code": slot["code"],
            "counterexamples": slot["counterexamples"],
        }
        if column is not None:
            row["column"] = column
        if visit_count is not None:
            row["visit_count"] = visit_count
        if non_ct_count is not None:
            row["non_ct_count"] = non_ct_count
        if visit_time is not None:
            row["visit_time"] = visit_time
        merged_rows.append(row)

    return merged_rows


def merge_all(dst_dir: str) -> int:
    grouped = _group_input_files(dst_dir)
    written = 0

    for base, paths in sorted(grouped.items(), key=lambda kv: _natural_key(kv[0])):
        merged_rows = _merge_single_experiment(paths)
        out_path = os.path.join(dst_dir, base)

        if merged_rows:
            observed = set()
            for row in merged_rows:
                observed.update(row.keys())
            final_columns = [c for c in FINAL_COLUMN_ORDER if c in observed]
        else:
            final_columns = ["filename", "line", "non_ct_time", "code", "counterexamples"]

        payload = {
            "columns": final_columns,
            "data": merged_rows,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        print(f"wrote {out_path} ({len(merged_rows)} row(s), from {len(paths)} run file(s))")
        written += 1

    return written


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge per-run JSON results by experiment name from dst/*/*.json into dst/<experiment>.json. "
            "Rows are keyed by (filename,line,column), filtered to non-null non_ct_time and (if present) reproduced=true, "
            "then aggregated by geometric mean (optional metrics remain null when unavailable)."
        )
    )
    parser.add_argument("dst_dir", help="Destination root containing per-run subdirectories (e.g., dst/0, dst/1, ...)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.dst_dir):
        raise SystemExit(f"'{args.dst_dir}' is not a directory")

    total = merge_all(args.dst_dir)
    print(f"merged {total} experiment file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

