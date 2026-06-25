#!/usr/bin/env python3

import argparse
import sys

from tools.shared.configuration_metadata import merge_column_metadata

try:
    import pandas as pd
except Exception as e:
    pd = None  # type: ignore
    _PANDAS_IMPORT_ERROR = str(e)


REQUIRED_KEYS = ["library", "file", "line", "column"]
OPTIONAL_KEYS = ["target", "kind"]


def merge_on_location(left_path: str, right_path: str, output_path: str) -> int:
    if pd is None:
        raise SystemExit(
            "pandas is required for this script. "
            f"Import error: {_PANDAS_IMPORT_ERROR}. "
            "Install with: pip install pandas"
        )

    left = pd.read_csv(left_path)
    right = pd.read_csv(right_path)

    for k in REQUIRED_KEYS:
        if k not in left.columns or k not in right.columns:
            raise SystemExit(f"Missing required key column '{k}' in one or both CSVs")

    keys = [*REQUIRED_KEYS]
    for optional_key in OPTIONAL_KEYS:
        if optional_key == "kind" or optional_key in left.columns or optional_key in right.columns:
            if optional_key not in left.columns:
                left[optional_key] = ""
            if optional_key not in right.columns:
                right[optional_key] = ""
            keys.append(optional_key)

    # Normalize key types so merges behave as expected.
    left["library"] = left["library"].astype(str).str.strip()
    left["file"] = left["file"].astype(str).str.strip()
    right["library"] = right["library"].astype(str).str.strip()
    right["file"] = right["file"].astype(str).str.strip()
    for optional_key in OPTIONAL_KEYS:
        if optional_key in keys:
            left[optional_key] = left[optional_key].fillna("").astype(str).str.strip()
            right[optional_key] = right[optional_key].fillna("").astype(str).str.strip()

    left["line"] = pd.to_numeric(left["line"], errors="coerce").astype("Int64")
    left["column"] = pd.to_numeric(left["column"], errors="coerce").astype("Int64")
    right["line"] = pd.to_numeric(right["line"], errors="coerce").astype("Int64")
    right["column"] = pd.to_numeric(right["column"], errors="coerce").astype("Int64")

    # Drop rows with invalid/missing key fields.
    left = left.dropna(subset=REQUIRED_KEYS)
    right = right.dropna(subset=REQUIRED_KEYS)

    merged = left.merge(right, on=keys, how="outer", suffixes=("", "_right"))

    # Make the output stable/readable.
    merged = merged.sort_values(keys, kind="stable")
    merged.to_csv(output_path, index=False)
    merge_column_metadata(output_path, [left_path, right_path])
    return int(len(merged))


def main(argv: list[str] | None = None) -> int:

    p = argparse.ArgumentParser(
        description="Merge two KLEE CSV files on location metadata into one CSV (outer merge)."
    )
    p.add_argument("left", help="Left CSV path (e.g., utils/klee.csv)")
    p.add_argument("right", help="Right CSV path (e.g., utils/klee_sliced_line_column_aligned.csv)")
    p.add_argument("-o", "--output", default="merged.csv", help="Output CSV path (default: merged.csv)")
    args = p.parse_args(argv)

    count = merge_on_location(args.left, args.right, args.output)
    print(f"Wrote {count} row(s) to {args.output}")
    return 0


if __name__ == "__main__":

    sys.exit(main())
