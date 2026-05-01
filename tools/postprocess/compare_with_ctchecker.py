#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

from tools.shared.common import load_combined_json, save_combined_json


def load_ctchecker(ct_type: str, path: str, prefix: str = "") -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    key = "branches" if ct_type == "branch" else "indices"
    dataframe = pd.DataFrame(data.get(key, []))
    if "filename" not in dataframe.columns:
        dataframe = pd.DataFrame(columns=["filename", "line", "column"])
    dataframe["filename"] = dataframe["filename"].apply(lambda value: os.path.join(prefix, value))
    return dataframe


def compare_with_ctchecker(
    *,
    ct_type: str,
    ctchecker_output: str,
    klee_json: str,
    ctchecker_prefix: str = "",
    filename: str = "",
    lines: str = "",
    library: str = "unknown",
) -> pd.DataFrame:
    df_ctchecker = load_ctchecker(ct_type, ctchecker_output, ctchecker_prefix)
    df_klee = load_combined_json(klee_json)

    for column_name in ("filename", "line", "column"):
        if column_name not in df_klee.columns:
            df_klee[column_name] = pd.NA

    df_joined = df_ctchecker.merge(
        df_klee,
        on=["filename", "line", "column"],
        how="left",
        indicator=True,
    )
    df_joined["visit_count"] = pd.to_numeric(df_joined.get("visit_count"), errors="coerce").fillna(0).astype("int64")
    df_joined["non_ct_count"] = pd.to_numeric(df_joined.get("non_ct_count"), errors="coerce").fillna(0).astype("int64")
    df_joined["in_ctchecker"] = df_joined["_merge"].apply(lambda value: value in ["both", "left_only"])
    df_joined = df_joined.drop(columns="_merge")

    non_ct_series = pd.to_numeric(df_klee.get("non_ct_count"), errors="coerce").fillna(0)
    df_klee_only = df_klee[non_ct_series > 0].merge(
        df_ctchecker,
        on=["filename", "line", "column"],
        how="left",
        indicator=True,
    )
    df_klee_only = df_klee_only[df_klee_only["_merge"] == "left_only"].drop(columns="_merge")
    df_klee_only["in_ctchecker"] = False

    dataframe = pd.concat([df_joined, df_klee_only], ignore_index=True)
    if "library" not in dataframe.columns:
        dataframe["library"] = library
    else:
        dataframe["library"] = dataframe["library"].apply(
            lambda value: value if isinstance(value, str) and value.strip() else library
        )

    if lines:
        bounds = lines.split(":", 1)
        if len(bounds) != 2:
            raise ValueError("lines must be in the format start:end")
        start = int(bounds[0])
        end = int(bounds[1])
        dataframe = dataframe[(dataframe["line"] >= start) & (dataframe["line"] <= end)]
    if filename:
        dataframe = dataframe[dataframe["filename"] == filename]

    return dataframe


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare CtChecker findings with a converted KLEE JSON file.")
    parser.add_argument("ct_type", choices=["branch", "memory"])
    parser.add_argument("ctchecker_output", help="Path to CtChecker output file")
    parser.add_argument("klee_json", help="Path to the KLEE combined JSON produced by klee_log_to_json.py")
    parser.add_argument("output_path", help="Path to save the combined dataframe in JSON format")
    parser.add_argument("--filename", default="", help="Filename to filter (for example: main.c)")
    parser.add_argument("--lines", default="", help="Line number range to filter (for example: 100:200)")
    parser.add_argument(
        "--ctchecker-prefix",
        default="",
        help="If set, prepend this prefix to every filename in the CtChecker output.",
    )
    parser.add_argument(
        "--library",
        default="unknown",
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "unknown"],
        help="Fallback library identifier for rows whose JSON is missing it.",
    )
    args = parser.parse_args(argv)

    try:
        dataframe = compare_with_ctchecker(
            ct_type=args.ct_type,
            ctchecker_output=args.ctchecker_output,
            klee_json=args.klee_json,
            ctchecker_prefix=args.ctchecker_prefix,
            filename=args.filename,
            lines=args.lines,
            library=args.library,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    output_dir = os.path.dirname(os.path.abspath(args.output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    save_combined_json(dataframe, args.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
