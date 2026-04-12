#!/usr/bin/env python3
"""Aggregate merged result CSV columns by experiment group.

This script reads a wide CSV such as all_merged_results.csv and produces:
1. An aggregated CSV where columns belonging to the same experiment group are
    collapsed by taking the row-wise minimum.
2. A summary CSV with one row per experiment group containing the maximum value
    seen in the aggregated CSV and the count of non-null entries.
3. A cactus plot PNG showing cumulative insecure locations found over time for each
    aggregated experiment group.
4. A second cactus plot PNG using a logarithmic time axis.
5. A scatter plot PNG for the summary data with vulnerabilities found on the x
    axis and maximum time on the y axis.
6. A per-tool output directory containing one CSV and one cactus plot per tool,
    comparing that tool's configurations.

By default, experiment groups are aggregated across size variants, so columns
such as klee_cf_4_* and klee_cf_16_* contribute to the same group. An
immediate "sliced" token after the numeric size still forms a distinct group.
Pass --keep-sizes-separate to retain the original per-size grouping.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import importlib
from pathlib import Path

import numpy as np
import pandas as pd


METADATA_COLS = ["library", "file", "line", "column"]
MULTI_TOKEN_TOOL_PREFIXES = ["klee_cf", "klee_eager", "self_comp"]


def extract_experiment_group(
    column_name: str, *, aggregate_across_sizes: bool = True
) -> str:
    parts = column_name.split("_")
    number_index = None
    for idx, part in enumerate(parts):
        if part.isdigit():
            number_index = idx
            break

    if number_index is None:
        return column_name

    has_sliced_suffix = (
        number_index + 1 < len(parts) and parts[number_index + 1] == "sliced"
    )

    if aggregate_across_sizes:
        group_parts = parts[:number_index]
        if has_sliced_suffix:
            group_parts.append("sliced")
        return "_".join(group_parts)

    end_index = number_index + 1 if has_sliced_suffix else number_index
    return "_".join(parts[: end_index + 1])


def build_group_map(
    columns: list[str], *, aggregate_across_sizes: bool = True
) -> OrderedDict[str, list[str]]:
    group_map: OrderedDict[str, list[str]] = OrderedDict()
    for col in columns:
        if col in METADATA_COLS:
            continue
        group = extract_experiment_group(
            col, aggregate_across_sizes=aggregate_across_sizes
        )
        group_map.setdefault(group, []).append(col)
    return group_map


def aggregate_groups(
    df: pd.DataFrame, *, aggregate_across_sizes: bool = True
) -> pd.DataFrame:
    metadata = [col for col in METADATA_COLS if col in df.columns]
    metric_columns = [col for col in df.columns if col not in metadata]
    group_map = build_group_map(
        metric_columns, aggregate_across_sizes=aggregate_across_sizes
    )

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


def make_cactus_plot(
    df: pd.DataFrame, output_path: Path, title: str, *, log_scale: bool = False
) -> None:
    try:
        plt = importlib.import_module("matplotlib.pyplot")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "matplotlib is required to generate the cactus plots"
        ) from exc

    group_columns = [col for col in df.columns if col not in METADATA_COLS]
    if not group_columns:
        raise ValueError("No aggregated experiment groups available to plot")

    group_times: OrderedDict[str, np.ndarray] = OrderedDict()
    for group in group_columns:
        numeric = pd.to_numeric(df[group], errors="coerce").dropna().sort_values()
        group_times[group] = numeric.to_numpy(dtype=float)

    if log_scale:
        non_empty_series = [
            times[times > 0] for times in group_times.values() if np.any(times > 0)
        ]
    else:
        non_empty_series = [times for times in group_times.values() if times.size > 0]

    ordered_groups = sorted(
        group_times.items(), key=lambda item: len(item[1]), reverse=True
    )

    if non_empty_series:
        time_axis = np.unique(np.concatenate(non_empty_series))
    elif log_scale:
        time_axis = np.array([1.0])
    else:
        time_axis = np.array([0.0])

    plt.figure(figsize=(9, 5.5))

    for group, times in ordered_groups:
        if log_scale:
            times = times[times > 0]

        if times.size == 0:
            counts = np.zeros_like(time_axis, dtype=int)
        else:
            counts = np.searchsorted(times, time_axis, side="right")

        plt.plot(
            time_axis,
            counts,
            drawstyle="steps-post",
            linewidth=2,
            label=f"{group} ({len(times)})",
        )

    max_count = max((len(times) for times in group_times.values()), default=0)

    plt.xlabel("Time (seconds)")
    plt.ylabel("Cumulative insecure locations found")
    plt.title(title)

    if log_scale:
        plt.xscale("log")
        plt.xlim(left=float(time_axis[0]))
    else:
        plt.xlim(left=0)

    plt.ylim(bottom=0)
    plt.yticks(range(0, max_count + 1, max(1, max_count // 10 or 1)))
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.legend()
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def make_summary_scatter_plot(summary: pd.DataFrame, output_path: Path, title: str) -> None:
    try:
        plt = importlib.import_module("matplotlib.pyplot")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "matplotlib is required to generate the summary scatter plot"
        ) from exc

    plot_data = summary.copy()
    plot_data["count"] = pd.to_numeric(plot_data["count"], errors="coerce")
    plot_data["max_time"] = pd.to_numeric(plot_data["max_time"], errors="coerce")
    plot_data = plot_data.dropna(subset=["count", "max_time"])

    plt.figure(figsize=(8, 5.5))
    plt.scatter(plot_data["count"], plot_data["max_time"], s=60)

    for _, row in plot_data.iterrows():
        plt.annotate(
            row["group"],
            (row["count"], row["max_time"]),
            textcoords="offset points",
            xytext=(5, 5),
        )

    plt.xlabel("Insecure locations found")
    plt.ylabel("Maximum time (seconds)")
    plt.title(title)
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def extract_tool_and_configuration(column_name: str) -> tuple[str, str]:
    tool = column_name.split("_", 1)[0]
    for prefix in MULTI_TOKEN_TOOL_PREFIXES:
        if column_name == prefix or column_name.startswith(prefix + "_"):
            tool = prefix
            break

    remainder = column_name[len(tool) :].lstrip("_")
    if not remainder:
        return tool, "all"

    parts = remainder.split("_")
    if parts[0] == "sliced":
        config = "_".join(parts[1:]) or "all"
        return f"{tool}_sliced", config

    if len(parts) >= 2 and parts[0].isdigit() and parts[1] == "sliced":
        config = "_".join([parts[0], *parts[2:]]) or parts[0]
        return f"{tool}_sliced", config

    return tool, remainder


def write_by_tool_outputs(df: pd.DataFrame, output_base: str, input_stem: str) -> None:
    metadata = [col for col in METADATA_COLS if col in df.columns]
    metric_columns = [col for col in df.columns if col not in metadata]
    by_tool_dir = Path(f"{output_base}_by_tool")
    by_tool_dir.mkdir(parents=True, exist_ok=True)

    columns_by_tool: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()
    for column in metric_columns:
        tool, config = extract_tool_and_configuration(column)
        columns_by_tool.setdefault(tool, []).append((column, config))

    for tool, columns in columns_by_tool.items():
        selected_columns = [column for column, _ in columns]
        rename_map: dict[str, str] = {}
        seen_configs: dict[str, int] = {}
        for column, config in columns:
            count = seen_configs.get(config, 0) + 1
            seen_configs[config] = count
            rename_map[column] = config if count == 1 else f"{config}_{count}"

        tool_df = df.loc[:, metadata + selected_columns].copy().rename(columns=rename_map)

        tool_csv_path = by_tool_dir / f"{tool}.csv"
        tool_df.to_csv(tool_csv_path, index=False)
        print(f"Wrote: {tool_csv_path}")

        tool_plot_path = by_tool_dir / f"{tool}_cactus.png"
        make_cactus_plot(
            tool_df,
            tool_plot_path,
            title=f"{input_stem} {tool} configurations over time",
            log_scale=True,
        )
        print(f"Wrote: {tool_plot_path}")

    klee_cf_fix_pub_columns = [
        column
        for column in metric_columns
        if column.startswith("klee_cf_")
        and column.endswith("_4_fix_pub")
        and "_sliced_" not in column
    ]
    if klee_cf_fix_pub_columns:
        rename_map = {
            column: column.removeprefix("klee_cf_").removesuffix("_fix_pub")
            for column in klee_cf_fix_pub_columns
        }
        klee_cf_fix_pub_df = (
            df.loc[:, metadata + klee_cf_fix_pub_columns]
            .copy()
            .rename(columns=rename_map)
        )

        klee_cf_fix_pub_plot_path = by_tool_dir / "klee_cf_4_fix_pub_cactus.png"
        make_cactus_plot(
            klee_cf_fix_pub_df,
            klee_cf_fix_pub_plot_path,
            title=f"{input_stem} klee_cf size 4 fix_pub over time",
            log_scale=True,
        )
        print(f"Wrote: {klee_cf_fix_pub_plot_path}")


def output_path(base: str, kind: str) -> Path:
    suffix = {
        "aggregated": "_aggregated.csv",
        "summary": "_summary.csv",
        "summary_scatter": "_summary_scatter.png",
        "cactus": "_cactus.png",
        "cactus_log": "_cactus_log.png",
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
    parser.add_argument(
        "--keep-sizes-separate",
        action="store_true",
        help=(
            "Keep size variants such as klee_cf_4 and klee_cf_16 in separate "
            "groups instead of aggregating them together."
        ),
    )
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_base = args.output

    df = pd.read_csv(input_path)

    aggregated = aggregate_groups(
        df, aggregate_across_sizes=not args.keep_sizes_separate
    )
    aggregated_path = output_path(output_base, "aggregated")
    aggregated_path.parent.mkdir(parents=True, exist_ok=True)
    aggregated.to_csv(aggregated_path, index=False)
    print(f"Wrote: {aggregated_path}")

    summary = summarize_groups(aggregated)
    summary_path = output_path(output_base, "summary")
    summary.to_csv(summary_path, index=False)
    print(f"Wrote: {summary_path}")

    summary_scatter_path = output_path(output_base, "summary_scatter")
    make_summary_scatter_plot(
        summary,
        summary_scatter_path,
        title=f"{input_path.stem} summary scatter",
    )
    print(f"Wrote: {summary_scatter_path}")

    cactus_path = output_path(output_base, "cactus")
    make_cactus_plot(
        aggregated,
        cactus_path,
        title=f"{input_path.stem} insecure locations over time (log scale)",
        log_scale=True,
    )
    print(f"Wrote: {cactus_path}")

    write_by_tool_outputs(df, output_base, input_path.stem)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
