#!/usr/bin/env python3
"""Merge bounded-verification timing payloads into campaign tables."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from scripts.experiments.common import expand_benchmark_cases
from tools.postprocess.csv_to_latex_table import escape_latex
from tools.postprocess.selection_helpers import default_display_label
from tools.shared.configuration_metadata import build_column_metadata, load_run_metadata
from tools.shared.experiment_registry import _BENCHMARK_DEFINITIONS, canonical_case_id
from tools.shared.verification_timing import TIMING_DIR_NAME


LONG_COLUMNS = [
    "source_column",
    "configuration_label",
    "comparison_tool",
    "tool_family",
    "library",
    "variant",
    "target",
    "benchmark",
    "program_status",
    "verification_time_seconds",
    "total_repetitions",
    "completed_repetitions",
    "timeout_repetitions",
    "failed_repetitions",
    "timeout_seconds",
    "status_counts",
]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        output = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(output):
        return None
    return output


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _geometric_mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    cleaned = [value for value in values if math.isfinite(value) and value >= 0.0]
    if len(cleaned) != len(values):
        return None
    if any(value == 0.0 for value in cleaned):
        return 0.0
    return math.exp(sum(math.log(value) for value in cleaned) / len(cleaned))


@lru_cache(maxsize=1)
def _case_identity_by_result_stem() -> dict[str, tuple[str, str, str]]:
    mapping: dict[str, tuple[str, str, str]] = {}
    for benchmark_definition in _BENCHMARK_DEFINITIONS:
        for tool_id in benchmark_definition.tools:
            for expanded_case in expand_benchmark_cases(benchmark_definition, tool_id):
                result_stem = canonical_case_id(
                    benchmark_definition.library_id,
                    benchmark_definition.target_id,
                    expanded_case.config_id,
                )
                mapping.setdefault(
                    result_stem,
                    (
                        benchmark_definition.library_id,
                        benchmark_definition.target_id,
                        expanded_case.target_id,
                    ),
                )
    return mapping


def _benchmark_label(library: str, variant: str) -> str:
    if not variant:
        return library
    return f"{library}:{variant}"


def _eligible_for_best_selection(row: Mapping[str, Any]) -> bool:
    return str(row.get("public_mode", "")) == "var_pub"


def _is_klee_family(*, comparison_tool: str, tool_family: str) -> bool:
    return comparison_tool.startswith("klee") or tool_family.startswith("klee")


def _result_json_has_positives(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    if not isinstance(payload, dict):
        return False
    data = payload.get("data")
    return isinstance(data, list) and bool(data)


def _klee_partially_completed_paths(klee_output_dir: Path) -> int | None:
    info_path = klee_output_dir / "info"
    try:
        text = info_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"^KLEE: done: partially completed paths = (\d+)\s*$", text, flags=re.MULTILINE)
    if match is None:
        return None
    return int(match.group(1))


def _klee_program_status(repetition_dir: Path, case_id: str) -> str:
    if _result_json_has_positives(repetition_dir / f"{case_id}.json"):
        return "insecure"
    if _klee_partially_completed_paths(repetition_dir / case_id) == 0:
        return "secure"
    return "unknown"


def _binsec_program_status(repetition_dir: Path, case_id: str) -> str:
    log_path = repetition_dir / "_worker_logs" / f"{case_id}.log"
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "unknown"
    matches = re.findall(r"^\[checkct:result\] Program status is : (secure|insecure|unknown)\b", text, flags=re.MULTILINE)
    if not matches:
        return "unknown"
    return matches[-1]


def _program_status_for_repetition(
    timing_path: Path,
    *,
    case_id: str,
    comparison_tool: str,
    tool_family: str,
) -> str:
    repetition_dir = timing_path.parent.parent
    if _is_klee_family(comparison_tool=comparison_tool, tool_family=tool_family):
        return _klee_program_status(repetition_dir, case_id)
    if comparison_tool == "binsec" or tool_family == "binsec":
        return _binsec_program_status(repetition_dir, case_id)
    if comparison_tool == "abacus" or tool_family == "abacus":
        if _result_json_has_positives(repetition_dir / f"{case_id}.json"):
            return "insecure"
    return "unknown"


def _merge_program_statuses(statuses: Sequence[str]) -> str:
    if any(status == "insecure" for status in statuses):
        return "insecure"
    if statuses and all(status == "secure" for status in statuses):
        return "secure"
    return "unknown"


def _format_duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _format_timing_cell(row: Mapping[str, Any] | None) -> str:
    if row is None:
        return "-"
    value = _to_float(row.get("verification_time_seconds"))
    total = _to_int(row.get("total_repetitions")) or 0
    timeouts = _to_int(row.get("timeout_repetitions")) or 0
    failures = _to_int(row.get("failed_repetitions")) or 0
    timeout_seconds = _to_int(row.get("timeout_seconds")) or 0
    if total > 0 and timeouts == total and timeout_seconds > 0:
        return f"TO({_format_duration(timeout_seconds)})"
    if value is None:
        return "FAIL" if failures else "-"

    cell = f"{value:.2f}s"
    notes: list[str] = []
    if timeouts:
        notes.append(f"{timeouts}/{total} TO")
    if failures:
        notes.append(f"{failures}/{total} fail")
    if notes:
        cell += " (" + ", ".join(notes) + ")"
    return cell


def _read_timing_payload(path: Path) -> tuple[dict[str, Any], dict[str, Any]] | None:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected a JSON object payload")

    data = payload.get("data")
    metadata = payload.get("metadata")
    if not isinstance(data, list) or not data:
        return None
    if metadata is not None and not isinstance(metadata, dict):
        raise SystemExit(f"{path}: metadata must be a JSON object")
    first_row = data[0]
    if not isinstance(first_row, dict):
        return None
    return dict(first_row), dict(metadata or {})


def _timing_files_by_case(run_dir: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for repetition_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        timing_dir = repetition_dir / TIMING_DIR_NAME
        if not timing_dir.is_dir():
            continue
        for timing_path in sorted(timing_dir.glob("*.json")):
            grouped.setdefault(timing_path.stem, []).append(timing_path)
    return grouped


def _merge_case_timings(
    paths: Sequence[Path],
    *,
    run_metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    values: list[float] = []
    status_counts: dict[str, int] = {}
    case_metadata: dict[str, Any] | None = None
    library = ""
    variant = ""
    target = ""
    timeout_seconds_values: list[int] = []
    case_id = ""
    program_statuses: list[str] = []

    for path in paths:
        loaded = _read_timing_payload(path)
        if loaded is None:
            continue
        row, metadata = loaded
        row_case_id = row.get("case_id")
        if isinstance(row_case_id, str) and row_case_id.strip():
            case_id = row_case_id.strip()
        if case_metadata is None:
            case_metadata = metadata
        elif metadata != case_metadata:
            raise SystemExit(f"{path}: timing metadata does not match other repetitions for this case")

        value = _to_float(row.get("verification_time_seconds"))
        if value is None:
            continue
        values.append(value)

        status = str(row.get("status") or "unknown").strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

        row_library = row.get("library")
        if isinstance(row_library, str) and row_library.strip():
            library = row_library.strip()
        row_variant = row.get("variant")
        if isinstance(row_variant, str) and row_variant.strip():
            variant = row_variant.strip()
        row_target = row.get("target")
        if isinstance(row_target, str) and row_target.strip():
            target = row_target.strip()
        timeout_seconds = _to_int(row.get("timeout_seconds"))
        if timeout_seconds is not None:
            timeout_seconds_values.append(timeout_seconds)

    merged_time = _geometric_mean(values)
    if merged_time is None or case_metadata is None:
        return None

    column_metadata = build_column_metadata(run_metadata, case_metadata)
    comparison_tool = str(column_metadata["comparison_tool"])
    tool_family = str(column_metadata["tool_family"])
    if case_id:
        program_statuses = [
            _program_status_for_repetition(
                path,
                case_id=case_id,
                comparison_tool=comparison_tool,
                tool_family=tool_family,
            )
            for path in paths
        ]
    public_mode_value = case_metadata.get("config")
    public_mode = public_mode_value.strip() if isinstance(public_mode_value, str) else ""
    if not library:
        library_value = case_metadata.get("library")
        library = library_value.strip() if isinstance(library_value, str) else ""
    if not target:
        target_value = case_metadata.get("target")
        target = target_value.strip() if isinstance(target_value, str) else ""
    if not variant and target:
        variant = target
    if (not variant or not target) and case_id:
        fallback_identity = _case_identity_by_result_stem().get(case_id)
        if fallback_identity is not None:
            fallback_library, fallback_variant, fallback_target = fallback_identity
            if not library:
                library = fallback_library
            if not variant:
                variant = fallback_variant
            if not target:
                target = fallback_target

    total = len(values)
    return {
        "source_column": column_metadata["source_column"],
        "configuration_label": column_metadata["configuration_label"],
        "comparison_tool": comparison_tool,
        "tool_family": tool_family,
        "library": library,
        "variant": variant,
        "target": target,
        "benchmark": _benchmark_label(library, variant),
        "program_status": _merge_program_statuses(program_statuses),
        "public_mode": public_mode,
        "verification_time_seconds": merged_time,
        "total_repetitions": total,
        "completed_repetitions": status_counts.get("completed", 0),
        "timeout_repetitions": status_counts.get("timeout", 0),
        "failed_repetitions": status_counts.get("failed", 0),
        "timeout_seconds": max(timeout_seconds_values) if timeout_seconds_values else "",
        "status_counts": json.dumps(dict(sorted(status_counts.items())), sort_keys=True),
    }


def collect_timing_rows(root_dir: Path) -> list[dict[str, Any]]:
    """Return one geometric-mean timing row per run configuration and benchmark target."""
    run_metadata_by_name = load_run_metadata(root_dir)
    rows: list[dict[str, Any]] = []

    for run_name in sorted(run_metadata_by_name):
        run_dir = root_dir / run_name
        if not run_dir.is_dir():
            raise SystemExit(f"{root_dir}: run metadata references missing run directory {run_name!r}")
        for _case_id, paths in sorted(_timing_files_by_case(run_dir).items()):
            merged = _merge_case_timings(paths, run_metadata=run_metadata_by_name[run_name])
            if merged is not None:
                rows.append(merged)

    return sorted(
        rows,
        key=lambda row: (
            str(row["comparison_tool"]),
            str(row["source_column"]),
            str(row["library"]),
            str(row["target"]),
        ),
    )


def write_long_csv(rows: Sequence[Mapping[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LONG_COLUMNS)
        writer.writeheader()
        for row in rows:
            output_row = dict(row)
            value = _to_float(output_row.get("verification_time_seconds"))
            if value is not None:
                output_row["verification_time_seconds"] = f"{value:.6f}"
            writer.writerow({column: output_row.get(column, "") for column in LONG_COLUMNS})
    return output_path


def select_best_configurations(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Choose one source column per comparison tool by minimizing max target time."""
    benchmarks_by_tool: dict[str, set[str]] = {}
    by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not _eligible_for_best_selection(row):
            continue
        source_column = str(row["source_column"])
        comparison_tool = str(row["comparison_tool"])
        benchmark = str(row["benchmark"])
        benchmarks_by_tool.setdefault(comparison_tool, set()).add(benchmark)
        value = _to_float(row.get("verification_time_seconds"))
        if value is None:
            continue
        slot = by_source.setdefault(
            source_column,
            {
                "source_column": source_column,
                "comparison_tool": comparison_tool,
                "tool_family": str(row["tool_family"]),
                "max_time": float("-inf"),
                "benchmarks": set(),
            },
        )
        slot["max_time"] = max(float(slot["max_time"]), value)
        slot["benchmarks"].add(benchmark)

    best_by_tool: dict[str, dict[str, Any]] = {}
    for candidate in by_source.values():
        comparison_tool = str(candidate["comparison_tool"])
        expected_benchmarks = benchmarks_by_tool.get(comparison_tool, set())
        observed_benchmarks = candidate.get("benchmarks")
        observed_count = len(observed_benchmarks) if isinstance(observed_benchmarks, set) else 0
        missing_count = max(0, len(expected_benchmarks) - observed_count)
        candidate["missing_benchmark_targets"] = missing_count
        previous = best_by_tool.get(comparison_tool)
        if previous is None:
            best_by_tool[comparison_tool] = dict(candidate)
            continue
        candidate_key = (missing_count, float(candidate["max_time"]), str(candidate["source_column"]))
        previous_key = (
            int(previous.get("missing_benchmark_targets", 0)),
            float(previous["max_time"]),
            str(previous["source_column"]),
        )
        if candidate_key < previous_key:
            best_by_tool[comparison_tool] = dict(candidate)

    selected = []
    for row in best_by_tool.values():
        cleaned = dict(row)
        cleaned.pop("benchmarks", None)
        selected.append(cleaned)
    return sorted(selected, key=lambda row: _tool_order(row))


def _tool_order(row: Mapping[str, Any]) -> tuple[int, str]:
    comparison_tool = str(row.get("comparison_tool", ""))
    tool_family = str(row.get("tool_family", ""))
    if comparison_tool == "klee_cf":
        group = 0
    elif comparison_tool.startswith("klee") or tool_family.startswith("klee"):
        group = 1
    else:
        group = 2
    return group, comparison_tool


def build_best_table_rows(
    rows: Sequence[Mapping[str, Any]],
    selected_configurations: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, str]]]:
    label_by_source: dict[str, str] = {}
    label_counts: dict[str, int] = {}
    for row in selected_configurations:
        source_column = str(row["source_column"])
        label = default_display_label(str(row["comparison_tool"]))
        count = label_counts.get(label, 0) + 1
        label_counts[label] = count
        label_by_source[source_column] = label if count == 1 else f"{label} ({count})"
    selected_sources = [str(row["source_column"]) for row in selected_configurations]
    lookup: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    statuses_by_key: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        source_column = str(row["source_column"])
        if source_column not in selected_sources:
            continue
        key = (source_column, str(row["library"]), str(row["variant"]))
        statuses_by_key.setdefault(key, []).append(str(row.get("program_status", "unknown")))
        previous = lookup.get(key)
        if previous is None or float(row["verification_time_seconds"]) > float(previous["verification_time_seconds"]):
            lookup[key] = row
    benchmarks = sorted(
        {
            (str(row["library"]), str(row["variant"]), str(row["benchmark"]))
            for row in rows
            if str(row["source_column"]) in selected_sources
        }
    )

    fieldnames = ["benchmark"]
    for source_column in selected_sources:
        label = label_by_source[source_column]
        fieldnames.extend([label, f"{label} status"])
    table_rows: list[dict[str, str]] = []
    for library, variant, benchmark in benchmarks:
        output_row = {"benchmark": benchmark}
        for source_column in selected_sources:
            key = (source_column, library, variant)
            output_row[label_by_source[source_column]] = _format_timing_cell(
                lookup.get(key)
            )
            output_row[f"{label_by_source[source_column]} status"] = _merge_program_statuses(
                statuses_by_key.get(key, [])
            ) if key in statuses_by_key else "-"
        table_rows.append(output_row)
    return fieldnames, table_rows


def write_best_csv(fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({fieldname: row.get(fieldname, "") for fieldname in fieldnames})
    return output_path


def _best_rows_to_latex(fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> str:
    alignment = "l" + "r" * (len(fieldnames) - 1)
    lines = [
        rf"\begin{{NiceTabular}}{{{alignment}}}",
        r"    \toprule",
        "    " + " & ".join(escape_latex(name) for name in fieldnames) + r" \\",
        r"    \midrule",
    ]
    for row in rows:
        cells = [escape_latex(str(row.get(fieldname, ""))) for fieldname in fieldnames]
        lines.append("    " + " & ".join(cells) + r" \\")
    lines.extend([r"    \bottomrule", r"\end{NiceTabular}"])
    return "\n".join(lines) + "\n"


def write_best_latex(fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_best_rows_to_latex(fieldnames, rows), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge per-case backend timing JSON into campaign timing tables.")
    parser.add_argument("root_dir", help="Campaign output root containing _run_metadata.json and run subdirectories")
    parser.add_argument("-o", "--output", required=True, help="Long-form merged timing CSV path")
    parser.add_argument("--best-output", required=True, help="Benchmark-target by selected-tool timing CSV path")
    parser.add_argument("--best-latex-output", help="Optional LaTeX path for the selected-tool timing table")
    args = parser.parse_args(argv)

    root_dir = Path(args.root_dir)
    rows = collect_timing_rows(root_dir)
    write_long_csv(rows, Path(args.output))
    selected = select_best_configurations(rows)
    fieldnames, best_rows = build_best_table_rows(rows, selected)
    write_best_csv(fieldnames, best_rows, Path(args.best_output))
    if args.best_latex_output:
        write_best_latex(fieldnames, best_rows, Path(args.best_latex_output))
    print(f"Wrote {args.output} with {len(rows)} timing row(s).")
    print(f"Wrote {args.best_output} with {len(best_rows)} benchmark row(s).")
    if args.best_latex_output:
        print(f"Wrote {args.best_latex_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())