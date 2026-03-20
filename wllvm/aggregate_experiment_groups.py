#!/usr/bin/env python3
"""Aggregate merged result CSV columns by experiment group.

This script reads a wide CSV such as all_merged_results.csv and produces:
1. An aggregated CSV where columns belonging to the same experiment group are
   collapsed by taking the row-wise minimum.
2. A summary CSV with one row per experiment group containing the maximum value
   seen in the aggregated CSV and the count of non-null entries.

Experiment groups follow the pattern technique_bytesize_[sliced]. The grouping
key is extracted by taking everything before the first numeric token and also
including an immediate "sliced" token if it appears right after that number.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path

import pandas as pd


METADATA_COLS = ["library", "file", "line", "column"]


def extract_experiment_group(column_name: str) -> str:
    parts = column_name.split("_")
    number_index = None
    for idx, part in enumerate(parts):
        if part.isdigit():
            number_index = idx
            break

    if number_index is None:
        return column_name

    end_index = number_index
    if number_index + 1 < len(parts) and parts[number_index + 1] == "sliced":
        end_index = number_index + 1

    return "_".join(parts[: end_index + 1])


def build_group_map(columns: list[str]) -> OrderedDict[str, list[str]]:
    group_map: OrderedDict[str, list[str]] = OrderedDict()
    for col in columns:
        if col in METADATA_COLS:
            continue
        group = extract_experiment_group(col)
        group_map.setdefault(group, []).append(col)
    return group_map


def aggregate_groups(df: pd.DataFrame) -> pd.DataFrame:
    metadata = [col for col in METADATA_COLS if col in df.columns]
    metric_columns = [col for col in df.columns if col not in metadata]
    group_map = build_group_map(metric_columns)

    aggregated = df.loc[:, metadata].copy()
    for group, cols in group_map.items():
        numeric = df.loc[:, cols].apply(pd.to_numeric, errors="coerce")
        aggregated[group] = numeric.min(axis=1, skipna=True)

    return aggregated


def summarize_groups(df: pd.DataFrame) -> pd.DataFrame:
    metadata = [col for col in METADATA_COLS if col in df.columns]
    group_columns = [col for col in df.columns if col not in metadata]

    rows: list[dict[str, object]] = []
    for group in group_columns:
        numeric = pd.to_numeric(df[group], errors="coerce")
        rows.append(
            {
                "group": group,
                "max_time": numeric.max(skipna=True),
                "count": int(numeric.notna().sum()),
            }
        )

    return pd.DataFrame(rows, columns=["group", "max_time", "count"])


def output_path(base: str, kind: str) -> Path:
    suffix = {
        "aggregated": "_aggregated.csv",
        "summary": "_summary.csv",
    }[kind]
    return Path(f"{base}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate merged result CSV columns by experiment group."
    )
    parser.add_argument("input_csv", help="Input CSV path")
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Base output path/name. The script writes BASE_aggregated.csv and "
            "BASE_summary.csv."
        ),
    )
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_base = args.output

    df = pd.read_csv(input_path)

    aggregated = aggregate_groups(df)
    aggregated_path = output_path(output_base, "aggregated")
    aggregated.to_csv(aggregated_path, index=False)
    print(f"Wrote: {aggregated_path}")

    summary = summarize_groups(aggregated)
    summary_path = output_path(output_base, "summary")
    summary.to_csv(summary_path, index=False)
    print(f"Wrote: {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

