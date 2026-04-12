#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable


FILTER_REQUIRED_COLUMNS = {"library", "file", "line_start", "line_end"}
INPUT_REQUIRED_COLUMNS = {"library", "file", "line"}


def _normalize_text(value: object) -> str:
    return str(value).strip()


def _normalize_file(value: object) -> str:
    return Path(_normalize_text(value)).name


def _normalize_int(value: object, field_name: str) -> int:
    text = _normalize_text(value)
    if text == "":
        raise ValueError(f"Empty integer field: {field_name}")
    return int(text)


def _validate_columns(fieldnames: Iterable[str] | None, required: set[str], csv_path: Path) -> None:
    if fieldnames is None:
        raise SystemExit(f"{csv_path} has no header row")

    missing = sorted(required.difference(fieldnames))
    if missing:
        raise SystemExit(f"{csv_path} is missing required column(s): {', '.join(missing)}")


def load_filters(filter_path: Path) -> dict[tuple[str, str], list[tuple[int, int]]]:
    filters: dict[tuple[str, str], list[tuple[int, int]]] = {}

    with filter_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_columns(reader.fieldnames, FILTER_REQUIRED_COLUMNS, filter_path)

        for row_number, row in enumerate(reader, start=2):
            try:
                key = (_normalize_text(row["library"]), _normalize_file(row["file"]))
                line_start = _normalize_int(row["line_start"], "line_start")
                line_end = _normalize_int(row["line_end"], "line_end")
            except Exception as exc:
                raise SystemExit(f"Invalid row in {filter_path} at line {row_number}: {exc}") from exc

            if line_start > line_end:
                raise SystemExit(
                    f"Invalid row in {filter_path} at line {row_number}: "
                    f"line_start {line_start} is greater than line_end {line_end}"
                )

            filters.setdefault(key, []).append((line_start, line_end))

    return filters


def row_matches(filters: dict[tuple[str, str], list[tuple[int, int]]], row: dict[str, str]) -> bool:
    key = (_normalize_text(row["library"]), _normalize_file(row["file"]))
    ranges = filters.get(key)
    if not ranges:
        return False

    line = _normalize_int(row["line"], "line")
    return any(line_start <= line <= line_end for line_start, line_end in ranges)


def filter_csv(input_path: Path, filter_path: Path, output_path: Path) -> tuple[int, int]:
    filters = load_filters(filter_path)
    kept_rows = 0
    total_rows = 0

    with input_path.open(newline="") as in_handle:
        reader = csv.DictReader(in_handle)
        _validate_columns(reader.fieldnames, INPUT_REQUIRED_COLUMNS, input_path)

        fieldnames = list(reader.fieldnames)
        output_rows: list[dict[str, str]] = []

        for row_number, row in enumerate(reader, start=2):
            total_rows += 1
            try:
                if row_matches(filters, row):
                    output_rows.append(row)
                    kept_rows += 1
            except Exception as exc:
                raise SystemExit(f"Invalid row in {input_path} at line {row_number}: {exc}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return kept_rows, total_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Filter a merged-results CSV by keeping only rows whose "
            "(library, file, line) match any configured inclusive line range."
        )
    )
    parser.add_argument("input_csv", help="Input merged-results CSV path")
    parser.add_argument("-f", "--filter", dest="filter_csv", required=True, help="Filter CSV path")
    parser.add_argument("-o", "--output", required=True, help="Output filtered CSV path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input_csv)
    filter_path = Path(args.filter_csv)
    output_path = Path(args.output)

    kept_rows, total_rows = filter_csv(input_path, filter_path, output_path)
    print(f"Wrote {output_path} with {kept_rows} kept row(s) out of {total_rows} total row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())