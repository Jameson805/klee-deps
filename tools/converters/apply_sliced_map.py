#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable


MAP_REQUIRED_COLUMNS = {
    "library",
    "file",
    "line",
    "column",
    "file_sliced",
    "line_sliced",
    "column_sliced",
}

INPUT_REQUIRED_COLUMNS = {"library", "file", "line", "column"}


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


def load_sliced_map(map_path: Path) -> dict[tuple[str, str, int, int], tuple[str, int, int]]:
    mapping: dict[tuple[str, str, int, int], tuple[str, int, int]] = {}

    with map_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_columns(reader.fieldnames, MAP_REQUIRED_COLUMNS, map_path)

        for row_number, row in enumerate(reader, start=2):
            try:
                key = (
                    _normalize_text(row["library"]),
                    _normalize_file(row["file_sliced"]),
                    _normalize_int(row["line_sliced"], "line_sliced"),
                    _normalize_int(row["column_sliced"], "column_sliced"),
                )
                value = (
                    _normalize_file(row["file"]),
                    _normalize_int(row["line"], "line"),
                    _normalize_int(row["column"], "column"),
                )
            except Exception as exc:
                raise SystemExit(f"Invalid row in {map_path} at line {row_number}: {exc}") from exc

            if key in mapping:
                raise SystemExit(
                    "Duplicate sliced mapping key in "
                    f"{map_path} at line {row_number}: {key}"
                )

            mapping[key] = value

    return mapping


def _format_unmapped_rows(
    unmapped_rows: list[tuple[int, tuple[str, str, int, int]]],
    *,
    limit: int = 10,
) -> str:
    preview = "\n".join(
        f"  line {row_number}: {key}"
        for row_number, key in unmapped_rows[:limit]
    )
    more = ""
    if len(unmapped_rows) > limit:
        more = f"\n  ... and {len(unmapped_rows) - limit} more"
    return f"{preview}{more}"


def relabel_csv(
    input_path: Path,
    map_path: Path,
    output_path: Path,
    *,
    keep_unmapped: bool,
) -> tuple[int, int]:
    mapping = load_sliced_map(map_path)
    relabeled_rows = 0
    unmapped_rows: list[tuple[int, tuple[str, str, int, int]]] = []
    output_rows: list[dict[str, str]] = []

    with input_path.open(newline="") as in_handle:
        reader = csv.DictReader(in_handle)
        _validate_columns(reader.fieldnames, INPUT_REQUIRED_COLUMNS, input_path)

        fieldnames = list(reader.fieldnames)

        for row_number, row in enumerate(reader, start=2):
            try:
                key = (
                    _normalize_text(row["library"]),
                    _normalize_file(row["file"]),
                    _normalize_int(row["line"], "line"),
                    _normalize_int(row["column"], "column"),
                )
            except Exception as exc:
                raise SystemExit(f"Invalid row in {input_path} at line {row_number}: {exc}") from exc

            target = mapping.get(key)
            if target is None:
                unmapped_rows.append((row_number, key))
            else:
                row["file"], row["line"], row["column"] = (
                    target[0],
                    str(target[1]),
                    str(target[2]),
                )
                relabeled_rows += 1

            output_rows.append(row)

    if unmapped_rows:
        sys.stderr.write(
            "Unmapped row(s) from input CSV:\n"
            f"{_format_unmapped_rows(unmapped_rows)}\n"
        )

    if unmapped_rows and not keep_unmapped:
        raise SystemExit(
            "Found unmapped row(s) in input CSV. "
            "Re-run with --keep-unmapped to keep them unchanged.\n"
            f"{_format_unmapped_rows(unmapped_rows)}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    return relabeled_rows, len(unmapped_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply sliced_map.csv to a sliced merged-results CSV by rewriting "
            "(file,line,column) from sliced coordinates back to original coordinates."
        )
    )
    parser.add_argument("input_csv", help="Input sliced-results CSV path")
    parser.add_argument("-m", "--map", dest="map_csv", required=True, help="sliced_map.csv path")
    parser.add_argument("-o", "--output", required=True, help="Output relabeled CSV path")
    parser.add_argument(
        "--keep-unmapped",
        action="store_true",
        help="Keep rows that are not present in the map unchanged instead of failing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input_csv)
    map_path = Path(args.map_csv)
    output_path = Path(args.output)

    relabeled_rows, unmapped_count = relabel_csv(
        input_path,
        map_path,
        output_path,
        keep_unmapped=args.keep_unmapped,
    )

    print(
        f"Wrote {output_path} with {relabeled_rows} relabeled row(s)"
        f" and {unmapped_count} unmapped row(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())