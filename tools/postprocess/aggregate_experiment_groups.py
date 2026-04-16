#!/usr/bin/env python3
"""Explore exact experiment configurations and compare manually selected winners.

This script reads one or more wide CSV files keyed by (library, file, line,
column) and produces:
1. A configuration metadata CSV with one row per result column.
2. A configuration summary CSV with per-config counts and timing statistics.
3. A log-scale cactus-plot exploration directory with one subdirectory per
   comparison tool. Each subdirectory contains a stable curve mapping CSV plus
   one plot per varying configuration dimension.
4. An optional log-scale cactus plot and CSV comparing one manually selected
    configuration per tool, plus optional grouped comparison plots.

Unlike the older aggregation workflow, this script never takes the row-wise
minimum across multiple configurations. Every output is based on exact input
columns so that final tool comparisons remain fair.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import asdict, dataclass
import importlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


METADATA_COLS = ["library", "file", "line", "column"]
MULTI_TOKEN_TOOL_PREFIXES = ["klee_cf", "klee_eager", "self_comp"]
KLEE_LIKE_TOOLS = {"klee_cf", "klee_eager", "self_comp"}
LINESTYLES = ("-", ":", "--")
CURVE_ID_LABEL_PLOT_EXTENSION = 1.14
CURVE_ID_LABEL_X_OFFSET_POINTS = 30.0
CURVE_ID_LABEL_MIN_GAP_POINTS = 10.0
CURVE_ID_LABEL_MARGIN_POINTS = 6.0
CURVE_ID_LABEL_FIGURE_RIGHT_FRACTION = 0.70
COLLISION_LANE_HALF_HEIGHT = 0.045
COLLISION_LANE_HEIGHT = 2.0 * COLLISION_LANE_HALF_HEIGHT
COUNT_BAND_PADDING = 0.0
PLOT_DIMENSIONS: OrderedDict[str, str] = OrderedDict(
    [
        ("searcher", "searcher"),
        ("sym_size", "symbolic input size"),
        ("public_mode", "public input mode"),
        ("concretization_policy", "public-input concretization"),
    ]
)
FIELD_VALUE_ORDER: dict[str, list[str]] = {
    "searcher": ["default", "dfs", "rand_path_dfs"],
    "sym_size": ["4", "8", "16", "all"],
    "public_mode": ["fix_pub", "var_pub", "var_pub_lim_loop_break", "all"],
    "concretization_policy": ["default", "no_conc", "all"],
}
STYLE_CHANNELS_BY_FOCAL_FIELD: dict[str, dict[str, str]] = {
    "searcher": {
        "color": "searcher",
        "linestyle": "public_mode",
        "brightness": "sym_size",
        "linewidth": "concretization_policy",
    },
    "sym_size": {
        "color": "sym_size",
        "linestyle": "searcher",
        "brightness": "public_mode",
        "linewidth": "concretization_policy",
    },
    "public_mode": {
        "color": "public_mode",
        "linestyle": "searcher",
        "brightness": "sym_size",
        "linewidth": "concretization_policy",
    },
    "concretization_policy": {
        "color": "concretization_policy",
        "linestyle": "public_mode",
        "brightness": "sym_size",
        "linewidth": "searcher",
    },
}


@dataclass(frozen=True)
class ColumnConfiguration:
    source_column: str
    tool_family: str
    comparison_tool: str
    sliced: bool
    searcher: str
    sym_size: str
    public_mode: str
    concretization_policy: str
    raw_suffix: str
    normalized_suffix: str
    configuration_label: str


def metric_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in df.columns if column not in METADATA_COLS]


def normalize_location_keys(df: pd.DataFrame) -> pd.DataFrame:
    for key in METADATA_COLS:
        if key not in df.columns:
            raise ValueError(f"Missing required key column {key!r}")

    normalized = df.copy()
    normalized["library"] = normalized["library"].astype(str).str.strip()
    normalized["file"] = normalized["file"].astype(str).str.strip()
    normalized["line"] = pd.to_numeric(normalized["line"], errors="coerce").astype(
        "Int64"
    )
    normalized["column"] = pd.to_numeric(
        normalized["column"], errors="coerce"
    ).astype("Int64")
    normalized = normalized.dropna(subset=METADATA_COLS)
    return normalized.sort_values(METADATA_COLS, kind="stable").reset_index(
        drop=True
    )


def load_input_dataframe(input_csv: Path, extra_input_csvs: list[Path]) -> pd.DataFrame:
    combined = normalize_location_keys(pd.read_csv(input_csv))

    for extra_input_csv in extra_input_csvs:
        extra_df = normalize_location_keys(pd.read_csv(extra_input_csv))
        overlapping_columns = sorted(
            set(metric_columns(combined)).intersection(metric_columns(extra_df))
        )
        if overlapping_columns:
            joined = ", ".join(overlapping_columns)
            raise ValueError(
                "Input CSVs contain duplicate metric columns, cannot merge: "
                f"{joined}"
            )

        combined = combined.merge(extra_df, on=METADATA_COLS, how="outer", sort=False)

    return combined.sort_values(METADATA_COLS, kind="stable").reset_index(drop=True)


def extract_tool_prefix(column_name: str) -> str:
    for prefix in MULTI_TOKEN_TOOL_PREFIXES:
        if column_name == prefix or column_name.startswith(prefix + "_"):
            return prefix
    return column_name.split("_", 1)[0]


def normalize_suffix(raw_suffix: str) -> str:
    if not raw_suffix or raw_suffix == "all":
        return "all"

    cleaned_parts = [
        part for part in raw_suffix.split("_") if part and part != "sliced"
    ]
    return "_".join(cleaned_parts) or "all"


def parse_column_configuration(column_name: str) -> ColumnConfiguration:
    tool_family = extract_tool_prefix(column_name)
    remainder = column_name[len(tool_family) :].lstrip("_")
    parts = remainder.split("_") if remainder else []

    number_index = next((idx for idx, part in enumerate(parts) if part.isdigit()), None)
    if number_index is None:
        run_parts = parts
        sym_size = "all"
        suffix_parts: list[str] = []
    else:
        run_parts = parts[:number_index]
        sym_size = parts[number_index]
        suffix_parts = parts[number_index + 1 :]

    sliced = False
    if suffix_parts and suffix_parts[0] == "sliced":
        sliced = True
        suffix_parts = suffix_parts[1:]

    concretization_policy = "default"
    normalized_run_parts: list[str] = []
    idx = 0
    while idx < len(run_parts):
        if run_parts[idx : idx + 2] == ["no", "conc"]:
            concretization_policy = "no_conc"
            idx += 2
            continue
        normalized_run_parts.append(run_parts[idx])
        idx += 1

    if tool_family in KLEE_LIKE_TOOLS:
        searcher = "_".join(normalized_run_parts) or "default"
    else:
        searcher = "default"

    raw_suffix = "_".join(suffix_parts) or "all"
    normalized_suffix = normalize_suffix(raw_suffix)
    comparison_tool = f"{tool_family}_sliced" if sliced else tool_family

    label_parts: list[str] = []
    if tool_family in KLEE_LIKE_TOOLS:
        label_parts.append(f"search={searcher}")
    if sym_size != "all":
        label_parts.append(f"sym={sym_size}")
    if normalized_suffix != "all":
        label_parts.append(f"mode={normalized_suffix}")
    if concretization_policy != "default":
        label_parts.append(f"conc={concretization_policy}")

    return ColumnConfiguration(
        source_column=column_name,
        tool_family=tool_family,
        comparison_tool=comparison_tool,
        sliced=sliced,
        searcher=searcher,
        sym_size=sym_size,
        public_mode=normalized_suffix,
        concretization_policy=concretization_policy,
        raw_suffix=raw_suffix,
        normalized_suffix=normalized_suffix,
        configuration_label=", ".join(label_parts) or "default",
    )


def summarize_configurations(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in metric_columns(df):
        config = parse_column_configuration(column)
        numeric = pd.to_numeric(df[column], errors="coerce").dropna()
        rows.append(
            {
                **asdict(config),
                "insecure_locations_found": int(numeric.shape[0]),
                "min_time": float(numeric.min()) if not numeric.empty else np.nan,
                "median_time": float(numeric.median()) if not numeric.empty else np.nan,
                "max_time": float(numeric.max()) if not numeric.empty else np.nan,
            }
        )

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary

    summary = summary.sort_values(
        ["comparison_tool", "insecure_locations_found", "max_time", "source_column"],
        ascending=[True, False, True, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
    summary["rank_within_tool"] = summary.groupby("comparison_tool").cumcount() + 1
    summary["curve_id"] = summary["rank_within_tool"].map(lambda value: f"C{value:02d}")

    ordered_columns = [
        "curve_id",
        "rank_within_tool",
        "source_column",
        "configuration_label",
        "tool_family",
        "comparison_tool",
        "sliced",
        "searcher",
        "sym_size",
        "public_mode",
        "concretization_policy",
        "raw_suffix",
        "normalized_suffix",
        "insecure_locations_found",
        "min_time",
        "median_time",
        "max_time",
    ]
    return summary.loc[:, ordered_columns]


def configuration_metadata(summary: pd.DataFrame) -> pd.DataFrame:
    metadata_columns = [
        "curve_id",
        "rank_within_tool",
        "source_column",
        "configuration_label",
        "tool_family",
        "comparison_tool",
        "sliced",
        "searcher",
        "sym_size",
        "public_mode",
        "concretization_policy",
        "raw_suffix",
        "normalized_suffix",
    ]
    return summary.loc[:, metadata_columns].copy()


def load_plot_modules():
    try:
        plt = importlib.import_module("matplotlib.pyplot")
        lines = importlib.import_module("matplotlib.lines")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "matplotlib is required to generate the cactus plots"
        ) from exc
    return plt, lines.Line2D


def lighten_color(color: Any, amount: float) -> tuple[float, float, float]:
    rgb = np.array(color[:3], dtype=float)
    mixed = rgb + (1.0 - rgb) * amount
    return tuple(float(channel) for channel in mixed)


def to_positive_sorted_times(series: pd.Series) -> np.ndarray:
    numeric = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
    if numeric.size == 0:
        return np.array([], dtype=float)

    positive = numeric[numeric > 0]
    if positive.size == numeric.size:
        return np.sort(numeric)

    if positive.size == 0:
        return np.full(numeric.shape[0], 1e-9, dtype=float)

    epsilon = float(positive.min()) / 10.0
    adjusted = np.where(numeric > 0, numeric, epsilon)
    return np.sort(adjusted)


def format_dimension_value(field: str, value: Any) -> str:
    text = str(value)
    if field == "sym_size" and text != "all":
        return f"{text} bytes"
    return text


def ordered_dimension_values(field: str, values: list[Any]) -> list[str]:
    unique_values = list(OrderedDict.fromkeys(str(value) for value in values))
    preferred_order = FIELD_VALUE_ORDER.get(field, [])
    preferred_rank = {value: idx for idx, value in enumerate(preferred_order)}

    def sort_key(value: str) -> tuple[int, Any]:
        if field == "sym_size" and value.isdigit():
            return (preferred_rank.get(value, len(preferred_order)), int(value))
        return (preferred_rank.get(value, len(preferred_order)), value)

    return sorted(unique_values, key=sort_key)


def build_color_map(values: list[str]) -> dict[str, Any]:
    plt, _ = load_plot_modules()
    cmap = plt.get_cmap("tab10" if len(values) <= 10 else "tab20")
    return {value: cmap(index % cmap.N) for index, value in enumerate(values)}


def build_linestyle_map(values: list[str]) -> dict[str, str]:
    return {
        value: LINESTYLES[index % len(LINESTYLES)]
        for index, value in enumerate(values)
    }


def build_brightness_map(values: list[str]) -> dict[str, float]:
    if len(values) <= 1:
        return {values[0]: 0.0} if values else {}
    shade_values = np.linspace(0.0, 0.45, num=len(values))
    return {
        value: float(shade_values[index]) for index, value in enumerate(values)
    }


def build_linewidth_map(values: list[str]) -> dict[str, float]:
    if len(values) <= 1:
        return {values[0]: 2.0} if values else {}
    widths = np.linspace(1.5, 2.7, num=len(values))
    return {value: float(widths[index]) for index, value in enumerate(values)}


def build_style_maps(
    tool_summary: pd.DataFrame, focal_field: str
) -> dict[str, dict[str, Any]]:
    channel_fields = STYLE_CHANNELS_BY_FOCAL_FIELD[focal_field]
    style_maps: dict[str, dict[str, Any]] = {}

    for channel_name, field in channel_fields.items():
        values = ordered_dimension_values(field, tool_summary[field].dropna().tolist())
        if not values:
            continue

        if channel_name == "color":
            style_maps[channel_name] = {
                "field": field,
                "values": values,
                "map": build_color_map(values),
            }
        elif channel_name == "linestyle":
            style_maps[channel_name] = {
                "field": field,
                "values": values,
                "map": build_linestyle_map(values),
            }
        elif channel_name == "brightness":
            style_maps[channel_name] = {
                "field": field,
                "values": values,
                "map": build_brightness_map(values),
            }
        elif channel_name == "linewidth":
            style_maps[channel_name] = {
                "field": field,
                "values": values,
                "map": build_linewidth_map(values),
            }

    return style_maps


def build_legend_group(
    channel_name: str, field: str, values: list[str], value_map: dict[str, Any]
) -> dict[str, Any] | None:
    _, line_2d = load_plot_modules()
    if len(values) < 2:
        return None

    handles = []
    for value in values:
        label = format_dimension_value(field, value)
        if channel_name == "color":
            handles.append(
                line_2d([0], [0], color=value_map[value], linewidth=2.3, linestyle="-", label=label)
            )
        elif channel_name == "linestyle":
            handles.append(
                line_2d([0], [0], color="black", linewidth=2.3, linestyle=value_map[value], label=label)
            )
        elif channel_name == "brightness":
            handles.append(
                line_2d(
                    [0],
                    [0],
                    color=lighten_color((0.15, 0.15, 0.15), value_map[value]),
                    linewidth=2.3,
                    linestyle="-",
                    label=label,
                )
            )
        elif channel_name == "linewidth":
            handles.append(
                line_2d([0], [0], color="black", linewidth=value_map[value], linestyle="-", label=label)
            )

    title_prefix = {
        "color": "color",
        "linestyle": "line shape",
        "brightness": "brightness",
        "linewidth": "line width",
    }[channel_name]
    return {"title": f"{title_prefix}: {PLOT_DIMENSIONS[field]}", "handles": handles}


def filter_tool_summary_for_plot(
    tool_summary: pd.DataFrame, focal_field: str
) -> pd.DataFrame:
    if focal_field == "concretization_policy":
        return tool_summary.loc[
            (tool_summary["searcher"] == "default")
            & (tool_summary["sym_size"] == "4")
        ].reset_index(drop=True)

    return tool_summary.loc[
        tool_summary["concretization_policy"] != "no_conc"
    ].reset_index(drop=True)


def centered_lane_centers(level: int, lane_count: int) -> list[float]:
    if lane_count <= 1:
        return [float(level)]

    top_center = float(level) + COLLISION_LANE_HALF_HEIGHT * (lane_count - 1)
    lane_step = COLLISION_LANE_HEIGHT
    return [top_center - lane_step * idx for idx in range(lane_count)]


def build_interval_layouts(
    curves: list[dict[str, Any]], plot_start: float, plot_end: float
) -> tuple[list[dict[str, Any]], int, float]:
    if not curves:
        return [], 0, 0.0

    event_times = sorted(
        {
            float(time_value)
            for curve in curves
            for time_value in curve["times"]
            if float(time_value) > 0.0
        }
    )
    if not event_times:
        return [], 0, 0.0

    interval_starts = event_times
    interval_ends = [*event_times[1:], plot_end]
    interval_layouts: list[dict[str, Any]] = []
    max_count = max((curve["times"].size for curve in curves), default=0)
    max_band_half_height = 0.0

    for x0, x1 in zip(interval_starts, interval_ends):
        active_by_level: OrderedDict[int, list[int]] = OrderedDict()
        for curve_index, curve in enumerate(curves):
            level = int(np.searchsorted(curve["times"], x0, side="right"))
            if level <= 0:
                continue
            active_by_level.setdefault(level, []).append(curve_index)

        curve_y_by_index: dict[int, float] = {}
        band_layout_by_level: dict[int, dict[str, float]] = {}
        for level, curve_indices in active_by_level.items():
            ordered_indices = sorted(
                curve_indices,
                key=lambda idx: (
                    float(curves[idx]["times"][level - 1]),
                    curves[idx]["legend_label"],
                ),
            )
            centers = centered_lane_centers(level, len(ordered_indices))

            for curve_index, center in zip(ordered_indices, centers):
                curve_y_by_index[curve_index] = center

            lane_count = len(ordered_indices)
            # Match guide band height to the total lane stack at this count level.
            band_half_height = 0.5 * lane_count * COLLISION_LANE_HEIGHT + COUNT_BAND_PADDING
            lower = float(level) - band_half_height
            upper = float(level) + band_half_height
            band_layout_by_level[level] = {
                "lower": lower,
                "upper": upper,
                "lane_count": float(lane_count),
            }
            max_band_half_height = max(max_band_half_height, band_half_height)

        interval_layouts.append(
            {
                "x0": float(x0),
                "x1": float(x1),
                "curve_y_by_index": curve_y_by_index,
                "band_layout_by_level": band_layout_by_level,
            }
        )

    return interval_layouts, max_count, max_band_half_height


def draw_count_level_background(
    ax: Any,
    interval_layouts: list[dict[str, Any]],
    max_count: int,
    plot_start: float,
    plot_end: float,
) -> None:
    guide_bounds_by_level: dict[int, tuple[float, float]] = {}
    for layout in interval_layouts:
        for level, band_layout in layout["band_layout_by_level"].items():
            lower = band_layout["lower"]
            upper = band_layout["upper"]
            existing_bounds = guide_bounds_by_level.get(level)
            if existing_bounds is None:
                guide_bounds_by_level[level] = (lower, upper)
                continue

            guide_bounds_by_level[level] = (
                min(existing_bounds[0], lower),
                max(existing_bounds[1], upper),
            )

    for level in range(1, max_count + 1):
        lower, upper = guide_bounds_by_level.get(
            level,
            (
                float(level) - COLLISION_LANE_HALF_HEIGHT - COUNT_BAND_PADDING,
                float(level) + COLLISION_LANE_HALF_HEIGHT + COUNT_BAND_PADDING,
            ),
        )
        ax.fill_between(
            [plot_start, plot_end],
            [lower, lower],
            [upper, upper],
            facecolor="#DADADA",
            alpha=1.0,
            linewidth=0,
            zorder=0.1,
        )
        ax.plot(
            [plot_start, plot_end],
            [level, level],
            color="#B2B2B2",
            linewidth=0.55,
            alpha=1.0,
            zorder=0.15,
        )


def build_dynamic_step_path(
    curve_index: int, interval_layouts: list[dict[str, Any]]
) -> tuple[list[float], list[float], float, float]:
    if not interval_layouts:
        return [], [], 0.0, 0.0

    first_layout = interval_layouts[0]
    current_y = float(first_layout["curve_y_by_index"].get(curve_index, 0.0))
    x_points: list[float] = [first_layout["x0"]]
    y_points: list[float] = [current_y]

    for layout in interval_layouts:
        x0 = float(layout["x0"])
        x1 = float(layout["x1"])
        interval_y = float(layout["curve_y_by_index"].get(curve_index, 0.0))

        if x_points[-1] != x0:
            x_points.append(x0)
            y_points.append(current_y)

        if interval_y != current_y:
            x_points.append(x0)
            y_points.append(interval_y)
            current_y = interval_y

        x_points.append(x1)
        y_points.append(current_y)

    return x_points, y_points, float(interval_layouts[-1]["x1"]), current_y


def build_ordered_curve_id_labels(
    fig: Any,
    ax: Any,
    curve_id_anchors: list[dict[str, Any]],
    max_label_display_x: float | None = None,
) -> list[dict[str, Any]]:
    if not curve_id_anchors:
        return []

    fig.canvas.draw()

    pixels_per_point = fig.dpi / 72.0
    label_margin_px = CURVE_ID_LABEL_MARGIN_POINTS * pixels_per_point
    min_gap_px = CURVE_ID_LABEL_MIN_GAP_POINTS * pixels_per_point
    label_x_offset_px = CURVE_ID_LABEL_X_OFFSET_POINTS * pixels_per_point

    display_anchors: list[dict[str, Any]] = []
    for curve_id_anchor in curve_id_anchors:
        anchor_display_x, anchor_display_y = ax.transData.transform(
            curve_id_anchor["anchor"]
        )
        display_anchors.append(
            {
                **curve_id_anchor,
                "anchor_display_x": float(anchor_display_x),
                "anchor_display_y": float(anchor_display_y),
            }
        )

    display_anchors = sorted(
        display_anchors,
        key=lambda curve_id_anchor: (
            -curve_id_anchor["anchor_display_y"],
            str(curve_id_anchor["curve_id"]),
        ),
    )

    label_display_x = (
        max(anchor["anchor_display_x"] for anchor in display_anchors)
        + label_x_offset_px
    )
    if max_label_display_x is not None:
        label_display_x = min(label_display_x, max_label_display_x - label_margin_px)

    upper_bound = float(ax.bbox.y1) - label_margin_px
    lower_bound = float(ax.bbox.y0) + label_margin_px

    if len(display_anchors) <= 1:
        gap_px = 0.0
    else:
        available_gap_px = (upper_bound - lower_bound) / (len(display_anchors) - 1)
        gap_px = min(min_gap_px, available_gap_px)

    placed_y_values: list[float] = []
    for display_anchor in display_anchors:
        upper_limit = upper_bound if not placed_y_values else placed_y_values[-1] - gap_px
        placed_y_values.append(min(display_anchor["anchor_display_y"], upper_limit))

    if placed_y_values and placed_y_values[-1] < lower_bound:
        placed_y_values[-1] = lower_bound
        for idx in range(len(placed_y_values) - 2, -1, -1):
            placed_y_values[idx] = max(
                placed_y_values[idx], placed_y_values[idx + 1] + gap_px
            )

        top_overflow = placed_y_values[0] - upper_bound
        if top_overflow > 0.0:
            placed_y_values = [value - top_overflow for value in placed_y_values]

    positioned_labels: list[dict[str, Any]] = []
    for display_anchor, label_display_y in zip(display_anchors, placed_y_values):
        label_data_x, label_data_y = ax.transData.inverted().transform(
            (label_display_x, label_display_y)
        )
        positioned_labels.append(
            {
                **display_anchor,
                "label_position": (float(label_data_x), float(label_data_y)),
            }
        )

    return positioned_labels


def make_log_cactus_plot(
    curves: list[dict[str, Any]],
    output_path: Path,
    title: str,
    *,
    legend_groups: list[dict[str, Any]] | None = None,
    show_curve_ids: bool = False,
    show_full_legend: bool = False,
) -> None:
    plt, _ = load_plot_modules()

    if not curves:
        raise ValueError("No configuration curves available to plot")

    non_empty_series = [curve["times"] for curve in curves if curve["times"].size > 0]
    time_axis = (
        np.unique(np.concatenate(non_empty_series))
        if non_empty_series
        else np.array([1.0], dtype=float)
    )
    plot_start = float(time_axis[0])
    plot_end = plot_start * 1.03 if time_axis.size == 1 else float(time_axis[-1]) * 1.03

    fig, ax = plt.subplots(figsize=(12.5, 6.8))
    ordered_curves = sorted(
        curves,
        key=lambda curve: (-curve["times"].size, curve["legend_label"]),
    )
    curve_id_anchors: list[dict[str, Any]] = []
    interval_layouts, max_count, max_band_half_height = build_interval_layouts(
        ordered_curves,
        plot_start,
        plot_end,
    )

    draw_count_level_background(ax, interval_layouts, max_count, plot_start, plot_end)

    for curve_index, curve in enumerate(ordered_curves):
        x_points, y_points, anchor_x, anchor_y = build_dynamic_step_path(
            curve_index,
            interval_layouts,
        )

        ax.plot(
            x_points,
            y_points,
            linewidth=curve.get("linewidth", 1.8),
            linestyle=curve.get("linestyle", "-"),
            color=curve["color"],
            alpha=curve.get("alpha", 1.0),
            label=curve["legend_label"],
        )

        if show_curve_ids and curve.get("curve_id"):
            curve_id_anchors.append(
                {
                    "curve_id": curve["curve_id"],
                    "anchor": (anchor_x, anchor_y),
                    "color": curve["color"],
                }
            )

    tick_step = max(1, max_count // 10) if max_count else 1

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Cumulative insecure locations found")
    ax.set_title(title)
    ax.set_xscale("log")
    ax.set_xlim(
        left=plot_start,
        right=(plot_end * CURVE_ID_LABEL_PLOT_EXTENSION if show_curve_ids else plot_end),
    )
    ax.set_ylim(
        bottom=0,
        top=max_count + max_band_half_height + 0.1,
    )
    ax.set_yticks(range(0, max_count + 1, tick_step))
    ax.grid(True, axis="x", which="both", linestyle="--", linewidth=0.5)

    legend_outside = False
    if show_full_legend:
        fig.legend(
            loc="upper left",
            bbox_to_anchor=(0.71, 0.98),
            bbox_transform=fig.transFigure,
            borderaxespad=0,
        )
        legend_outside = True
    elif legend_groups:
        next_y = 1.0
        for legend_group in legend_groups:
            fig.legend(
                handles=legend_group["handles"],
                title=legend_group["title"],
                loc="upper left",
                bbox_to_anchor=(0.71, next_y),
                bbox_transform=fig.transFigure,
                borderaxespad=0,
            )
            next_y -= 0.08 + 0.045 * len(legend_group["handles"])
        legend_outside = True

    if legend_outside:
        fig.tight_layout(rect=(0, 0, 0.68, 1))
    else:
        fig.tight_layout()

    if show_curve_ids and curve_id_anchors:
        max_label_display_x = None
        if legend_outside:
            max_label_display_x = float(fig.bbox.x0) + (
                float(fig.bbox.width) * CURVE_ID_LABEL_FIGURE_RIGHT_FRACTION
            )

        for curve_id_label in build_ordered_curve_id_labels(
            fig,
            ax,
            curve_id_anchors,
            max_label_display_x=max_label_display_x,
        ):
            ax.annotate(
                str(curve_id_label["curve_id"]),
                curve_id_label["anchor"],
                xytext=curve_id_label["label_position"],
                textcoords="data",
                fontsize=6.5,
                color=curve_id_label["color"],
                ha="left",
                va="center",
                arrowprops={
                    "arrowstyle": "-",
                    "linewidth": 0.55,
                    "color": curve_id_label["color"],
                    "alpha": 0.65,
                    "shrinkA": 0,
                    "shrinkB": 0,
                },
                annotation_clip=False,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def build_exploration_curves(
    df: pd.DataFrame, tool_summary: pd.DataFrame, focal_field: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = tool_summary.to_dict("records")
    style_maps = build_style_maps(tool_summary, focal_field)
    curves: list[dict[str, Any]] = []
    legend_groups: list[dict[str, Any]] = []

    for channel_name in ("color", "linestyle", "brightness", "linewidth"):
        style_spec = style_maps.get(channel_name)
        if not style_spec:
            continue
        legend_group = build_legend_group(
            channel_name,
            style_spec["field"],
            style_spec["values"],
            style_spec["map"],
        )
        if legend_group is not None:
            legend_groups.append(legend_group)

    for row in rows:
        color_field = style_maps["color"]["field"]
        color_value = str(row[color_field])
        base_color = style_maps["color"]["map"][color_value]

        brightness_field = style_maps["brightness"]["field"]
        brightness_value = str(row[brightness_field])
        brightness_amount = style_maps["brightness"]["map"][brightness_value]

        linestyle_field = style_maps["linestyle"]["field"]
        linestyle_value = str(row[linestyle_field])
        line_style = style_maps["linestyle"]["map"][linestyle_value]

        linewidth_field = style_maps["linewidth"]["field"]
        linewidth_value = str(row[linewidth_field])
        line_width = style_maps["linewidth"]["map"][linewidth_value]

        curves.append(
            {
                "curve_id": row["curve_id"],
                "legend_label": row["curve_id"],
                "times": to_positive_sorted_times(df[row["source_column"]]),
                "color": lighten_color(base_color, brightness_amount),
                "linestyle": line_style,
                "linewidth": line_width,
                "alpha": 0.96,
            }
        )

    return curves, legend_groups


def build_simple_comparison_curves(
    df: pd.DataFrame,
    tool_summary: pd.DataFrame,
    *,
    legend_fields: list[str],
    color_field: str,
    linestyle_field: str | None = None,
) -> list[dict[str, Any]]:
    rows = tool_summary.to_dict("records")
    ordered_values_by_field = {
        field: ordered_dimension_values(field, [row[field] for row in rows])
        for field in OrderedDict.fromkeys(
            [*legend_fields, color_field]
            + ([] if linestyle_field is None else [linestyle_field])
        )
    }
    value_ranks_by_field = {
        field: {value: index for index, value in enumerate(values)}
        for field, values in ordered_values_by_field.items()
    }
    rows = sorted(
        rows,
        key=lambda row: tuple(
            value_ranks_by_field[field].get(
                str(row[field]), len(value_ranks_by_field[field])
            )
            for field in legend_fields
        )
        + (str(row["source_column"]),),
    )

    color_map = build_color_map(ordered_values_by_field[color_field])
    linestyle_map = (
        build_linestyle_map(ordered_values_by_field[linestyle_field])
        if linestyle_field is not None
        else None
    )
    curves: list[dict[str, Any]] = []

    for row in rows:
        legend_label = ", ".join(
            format_dimension_value(field, row[field]) for field in legend_fields
        )
        curves.append(
            {
                "curve_id": None,
                "legend_label": legend_label,
                "times": to_positive_sorted_times(df[row["source_column"]]),
                "color": color_map[str(row[color_field])],
                "linestyle": (
                    "-"
                    if linestyle_map is None
                    else linestyle_map[str(row[linestyle_field])]
                ),
                "linewidth": 2.2,
                "alpha": 0.98,
            }
        )

    return curves


def write_klee_cf_simple_outputs(
    df: pd.DataFrame, tool_summary: pd.DataFrame, tool_dir: Path, input_stem: str
) -> None:
    rand_path_summary = tool_summary.loc[
        (tool_summary["searcher"] == "rand_path_dfs")
        & (tool_summary["concretization_policy"] == "default")
        & (tool_summary["public_mode"] != "all")
        & (tool_summary["sym_size"] != "all")
    ].reset_index(drop=True)
    if (
        rand_path_summary["public_mode"].nunique() > 1
        and rand_path_summary["sym_size"].nunique() > 1
    ):
        rand_path_curves = build_simple_comparison_curves(
            df,
            rand_path_summary,
            legend_fields=["public_mode", "sym_size"],
            color_field="public_mode",
            linestyle_field="sym_size",
        )
        rand_path_plot_path = tool_dir / "rand_path_dfs_by_public_mode_and_sym_size.png"
        make_log_cactus_plot(
            rand_path_curves,
            rand_path_plot_path,
            title=(
                f"{input_stem} klee_cf rand_path_dfs by public input mode and "
                "symbolic input size"
            ),
            show_full_legend=True,
        )
        print(f"Wrote: {rand_path_plot_path}")

    searcher_summary = tool_summary.loc[
        (tool_summary["public_mode"] == "fix_pub")
        & (tool_summary["sym_size"] == "4")
        & (tool_summary["concretization_policy"] == "default")
    ].reset_index(drop=True)
    if searcher_summary["searcher"].nunique() > 1:
        searcher_curves = build_simple_comparison_curves(
            df,
            searcher_summary,
            legend_fields=["searcher"],
            color_field="searcher",
        )
        searcher_plot_path = tool_dir / "fix_pub_sym_size_4_by_searcher.png"
        make_log_cactus_plot(
            searcher_curves,
            searcher_plot_path,
            title=f"{input_stem} klee_cf fix_pub, sym_size=4 by searcher",
            show_full_legend=True,
        )
        print(f"Wrote: {searcher_plot_path}")


def write_exploration_outputs(
    df: pd.DataFrame, summary: pd.DataFrame, output_base: str, input_stem: str
) -> None:
    exploration_dir = Path(f"{output_base}_exploration")

    for comparison_tool, tool_summary in summary.groupby("comparison_tool", sort=False):
        tool_dir = exploration_dir / comparison_tool
        tool_dir.mkdir(parents=True, exist_ok=True)

        tool_summary_path = tool_dir / "configurations.csv"
        tool_summary.to_csv(tool_summary_path, index=False)
        print(f"Wrote: {tool_summary_path}")

        for focal_field, dimension_label in PLOT_DIMENSIONS.items():
            plot_summary = filter_tool_summary_for_plot(tool_summary, focal_field)
            if plot_summary.empty:
                continue

            distinct_values = plot_summary[focal_field].dropna().astype(str).unique().tolist()
            if len(distinct_values) < 2:
                continue

            curves, legend_groups = build_exploration_curves(df, plot_summary, focal_field)
            plot_path = tool_dir / f"by_{focal_field}.png"
            make_log_cactus_plot(
                curves,
                plot_path,
                title=(
                    f"{input_stem} {comparison_tool} configurations styled by "
                    f"{dimension_label}"
                ),
                legend_groups=legend_groups,
                show_curve_ids=True,
            )
            print(f"Wrote: {plot_path}")

        if comparison_tool == "klee_cf":
            write_klee_cf_simple_outputs(df, tool_summary, tool_dir, input_stem)


def normalize_plot_groups(plot_groups: Any) -> str:
    if pd.isna(plot_groups):
        return ""

    normalized_groups: list[str] = []
    for raw_group in str(plot_groups).replace(";", "|").split("|"):
        group = raw_group.strip()
        if group and group not in normalized_groups:
            normalized_groups.append(group)

    return "|".join(normalized_groups)


def sanitize_output_token(value: str) -> str:
    token = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    token = token.strip("_")
    while "__" in token:
        token = token.replace("__", "_")
    return token or "group"


def load_selection(selection_csv: Path, summary: pd.DataFrame) -> pd.DataFrame:
    selection = pd.read_csv(selection_csv)
    required_columns = {"comparison_tool", "source_column"}
    missing_columns = required_columns.difference(selection.columns)
    if missing_columns:
        joined = ", ".join(sorted(missing_columns))
        raise ValueError(f"Selection CSV is missing required columns: {joined}")

    selection = selection.copy()
    selection["comparison_tool"] = selection["comparison_tool"].astype(str).str.strip()
    selection["source_column"] = selection["source_column"].astype(str).str.strip()

    if selection["comparison_tool"].duplicated().any():
        duplicates = selection.loc[
            selection["comparison_tool"].duplicated(), "comparison_tool"
        ].tolist()
        joined = ", ".join(sorted(set(duplicates)))
        raise ValueError(
            "Selection CSV must contain at most one row per comparison_tool: "
            f"{joined}"
        )

    lookup = summary.set_index("source_column", drop=False)
    rows: list[dict[str, Any]] = []
    for _, selection_row in selection.iterrows():
        source_column = selection_row["source_column"]
        if source_column not in lookup.index:
            raise ValueError(
                f"Selection source_column {source_column!r} does not exist in the input CSV"
            )

        summary_row = lookup.loc[source_column]
        comparison_tool = selection_row["comparison_tool"]
        if comparison_tool != summary_row["comparison_tool"]:
            raise ValueError(
                "Selection comparison_tool does not match the source column metadata: "
                f"{comparison_tool!r} vs {summary_row['comparison_tool']!r}"
            )

        display_label = source_column
        if "display_label" in selection.columns and pd.notna(selection_row["display_label"]):
            candidate = str(selection_row["display_label"]).strip()
            if candidate:
                display_label = candidate

        plot_groups = ""
        if "plot_groups" in selection.columns:
            plot_groups = normalize_plot_groups(selection_row["plot_groups"])

        rows.append(
            {
                **summary_row.to_dict(),
                "display_label": display_label,
                "plot_groups": plot_groups,
            }
        )

    if not rows:
        raise ValueError("Selection CSV is empty")

    return pd.DataFrame(rows)


def build_selected_label_map(selection_summary: pd.DataFrame) -> dict[str, str]:
    rename_map: dict[str, str] = {}
    label_counts: dict[str, int] = {}
    for _, row in selection_summary.iterrows():
        label = str(row["display_label"])
        count = label_counts.get(label, 0) + 1
        label_counts[label] = count
        rename_map[row["source_column"]] = label if count == 1 else f"{label} ({count})"

    return rename_map


def write_selected_comparison_bundle(
    df: pd.DataFrame,
    selection_summary: pd.DataFrame,
    selected_csv_path: Path,
    plot_path: Path,
    title: str,
) -> None:
    rename_map = build_selected_label_map(selection_summary)
    selected_columns = list(rename_map.keys())
    selected_df = df.loc[:, METADATA_COLS + selected_columns].copy().rename(
        columns=rename_map
    )
    selected_df.to_csv(selected_csv_path, index=False)
    print(f"Wrote: {selected_csv_path}")

    plt, _ = load_plot_modules()
    cmap = plt.get_cmap("tab10" if len(selection_summary) <= 10 else "tab20")
    curves: list[dict[str, Any]] = []
    for curve_index, (_, row) in enumerate(selection_summary.iterrows()):
        plot_label = rename_map[row["source_column"]]
        curves.append(
            {
                "curve_id": None,
                "legend_label": plot_label,
                "times": to_positive_sorted_times(df[row["source_column"]]),
                "color": cmap(curve_index % cmap.N),
                "linestyle": "-",
                "linewidth": 2.3,
                "alpha": 0.98,
            }
        )

    make_log_cactus_plot(
        curves,
        plot_path,
        title=title,
        show_full_legend=True,
    )
    print(f"Wrote: {plot_path}")


def selected_plot_groups(
    selection_summary: pd.DataFrame,
) -> OrderedDict[str, pd.DataFrame]:
    grouped_rows: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for _, row in selection_summary.iterrows():
        normalized_groups = normalize_plot_groups(row.get("plot_groups", ""))
        if not normalized_groups:
            continue

        for group_name in normalized_groups.split("|"):
            grouped_rows.setdefault(group_name, []).append(row.to_dict())

    return OrderedDict(
        (group_name, pd.DataFrame(rows)) for group_name, rows in grouped_rows.items()
    )


def write_selected_comparison_outputs(
    df: pd.DataFrame,
    selection_summary: pd.DataFrame,
    output_base: str,
    input_stem: str,
) -> None:
    selected_summary_path = Path(f"{output_base}_selected_configurations.csv")
    selection_summary.to_csv(selected_summary_path, index=False)
    print(f"Wrote: {selected_summary_path}")

    write_selected_comparison_bundle(
        df,
        selection_summary,
        Path(f"{output_base}_selected_comparison.csv"),
        Path(f"{output_base}_selected_comparison.png"),
        title=f"{input_stem} selected configurations comparison",
    )

    for group_name, group_summary in selected_plot_groups(selection_summary).items():
        if group_summary.shape[0] < 2:
            print(
                f"Skipping grouped comparison {group_name!r}: need at least two selections"
            )
            continue

        group_token = sanitize_output_token(group_name)
        group_summary_path = Path(
            f"{output_base}_{group_token}_selected_configurations.csv"
        )
        group_summary.to_csv(group_summary_path, index=False)
        print(f"Wrote: {group_summary_path}")
        write_selected_comparison_bundle(
            df,
            group_summary,
            Path(f"{output_base}_{group_token}_selected_comparison.csv"),
            Path(f"{output_base}_{group_token}_selected_comparison.png"),
            title=f"{input_stem} {group_name} selected configurations comparison",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explore experiment configurations from merged CSVs without row-wise "
            "aggregation."
        )
    )
    parser.add_argument("input_csv", help="Primary input CSV path")
    parser.add_argument(
        "--extra-input-csv",
        action="append",
        default=[],
        help=(
            "Additional location-keyed merged CSV to outer-merge before plotting. "
            "Useful when some tools, such as ABACUS, were postprocessed separately."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Base output path/name. The script writes BASE_config_metadata.csv, "
            "BASE_configuration_summary.csv, and BASE_exploration/."
        ),
    )
    parser.add_argument(
        "--selection-csv",
        help=(
            "Optional CSV listing one manually selected configuration per tool with "
            "columns comparison_tool, source_column, optional display_label, and "
            "optional plot_groups separated by '|' or ';'."
        ),
    )
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    extra_input_paths = [Path(path) for path in args.extra_input_csv]
    output_base = args.output

    df = load_input_dataframe(input_path, extra_input_paths)
    if not metric_columns(df):
        raise SystemExit("No experiment result columns found in the merged CSV input")

    summary = summarize_configurations(df)
    metadata = configuration_metadata(summary)

    metadata_path = Path(f"{output_base}_config_metadata.csv")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata.to_csv(metadata_path, index=False)
    print(f"Wrote: {metadata_path}")

    summary_path = Path(f"{output_base}_configuration_summary.csv")
    summary.to_csv(summary_path, index=False)
    print(f"Wrote: {summary_path}")

    write_exploration_outputs(df, summary, output_base, input_path.stem)

    if args.selection_csv:
        selection_summary = load_selection(Path(args.selection_csv), summary)
        write_selected_comparison_outputs(
            df,
            selection_summary,
            output_base,
            input_path.stem,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
