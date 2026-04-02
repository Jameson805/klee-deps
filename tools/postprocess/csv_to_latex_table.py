#!/usr/bin/env python3
"""Convert merged benchmark CSV results into a LaTex NiceTabular table.

Features:
- Uses first 4 columns as metadata and the remaining columns as numeric result columns.
- Replaces empty cells with '-'.
- Bolds values that are row-wise minima or within 0.1 of the row-wise minimum.
- Escapes LaTeX-sensitive characters in text/header cells.
- Adds vertical separators between different experiment groups in column alignment.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def format_value(raw: str, bold: bool) -> str:
    cell = raw.strip()
    if not cell:
        return "-"
    escaped = escape_latex(cell)
    return rf"\textbf{{{escaped}}}" if bold else escaped


def parse_float(raw: str) -> float | None:
    cell = raw.strip()
    if not cell:
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def should_bold(value: float, minimum: float, epsilon: float = 1e-12) -> bool:
    return value <= (minimum + 0.1 + epsilon)


def extract_experiment_group(column_name: str) -> str:
    """Extract experiment group as technique_bytesize_[sliced] from a metric column name."""
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


def build_alignment(fieldnames: list[str]) -> str:
    # Metadata columns: library/file as text (left), line/column as numbers (right).
    if len(fieldnames) < 4:
        raise ValueError("CSV must contain at least 4 columns: library,file,line,column")

    alignment = "llrr"
    metric_columns = fieldnames[4:]
    if not metric_columns:
        return alignment

    previous_group: str | None = None
    for col in metric_columns:
        group = extract_experiment_group(col)
        if previous_group is None or group != previous_group:
            alignment += "|"
        alignment += "r"
        previous_group = group

    return alignment


def csv_to_nicetabular(input_path: Path) -> str:
    with input_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        fieldnames = reader.fieldnames
        rows = list(reader)

    alignment = build_alignment(fieldnames)
    escaped_headers = [escape_latex(h) for h in fieldnames]

    lines: list[str] = []
    lines.append(rf"\begin{{NiceTabular}}{{{alignment}}}")
    lines.append(r"    \toprule")
    lines.append("    " + " & ".join(escaped_headers) + r" \\")
    lines.append(r"    \midrule")

    metric_columns = fieldnames[4:]
    library_column = fieldnames[0]
    previous_library: str | None = None

    for row in rows:
        current_library = row.get(library_column, "").strip()
        if previous_library is not None and current_library != previous_library:
            lines.append(r"    \midrule")

        numeric_values: list[float] = []
        parsed_metrics: dict[str, float | None] = {}
        for col in metric_columns:
            value = parse_float(row.get(col, ""))
            parsed_metrics[col] = value
            if value is not None:
                numeric_values.append(value)

        row_min = min(numeric_values) if numeric_values else None

        out_cells: list[str] = []
        for i, col in enumerate(fieldnames):
            raw = row.get(col, "")
            if i < 4:
                out_cells.append("-" if not raw.strip() else escape_latex(raw.strip()))
                continue

            value = parsed_metrics[col]
            bold = row_min is not None and value is not None and should_bold(value, row_min)
            out_cells.append(format_value(raw, bold))

        lines.append("    " + " & ".join(out_cells) + r" \\")
        previous_library = current_library

    lines.append(r"    \bottomrule")
    lines.append(r"\end{NiceTabular}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert benchmark CSV into a LaTeX NiceTabular table."
    )
    parser.add_argument("input_csv", type=Path, help="Path to input CSV file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .tex file path (default: print to stdout)",
    )
    args = parser.parse_args()

    table = csv_to_nicetabular(args.input_csv)
    if args.output is None:
        print(table, end="")
    else:
        args.output.write_text(table, encoding="utf-8")


if __name__ == "__main__":
    main()
