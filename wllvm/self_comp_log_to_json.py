#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple


_NON_CT_RE = re.compile(
    r"^\[(?P<ts>[0-9]+(?:\.[0-9]+)?)\]\s+\[NON-CT BRANCH\]\s+(?P<file>.+?):(?P<line>[0-9]+):(?P<col>[0-9]+)\s*$"
)
_ANY_TS_RE = re.compile(r"^\[(?P<ts>[0-9]+(?:\.[0-9]+)?)\]")


def parse_log_rows(log_path: str, code_root: Optional[str]) -> List[Dict[str, object]]:
    start_ts: Optional[float] = None
    first_hit_by_loc: Dict[Tuple[str, int, int], float] = {}

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if start_ts is None:
                m_any = _ANY_TS_RE.match(line)
                if m_any:
                    start_ts = float(m_any.group("ts"))

            m = _NON_CT_RE.match(line)
            if not m:
                continue

            ts = float(m.group("ts"))
            filename = m.group("file")
            line_no = int(m.group("line"))
            col_no = int(m.group("col"))
            key = (filename, line_no, col_no)
            hit = ts if start_ts is None else ts - start_ts
            prev = first_hit_by_loc.get(key)
            if prev is None or hit < prev:
                first_hit_by_loc[key] = hit

    if start_ts is None:
        return []

    source_cache: Dict[str, List[str]] = {}
    out: List[Dict[str, object]] = []
    ordered_rows = sorted(
        ((delta, filename, line_no, col_no) for (filename, line_no, col_no), delta in first_hit_by_loc.items()),
        key=lambda item: (item[0], item[1], item[2], item[3]),
    )

    for non_ct_time, filename, line_no, col_no in ordered_rows:
        row: Dict[str, object] = {
            "filename": filename,
            "line": line_no,
            "column": col_no,
            "non_ct_time": non_ct_time,
        }

        if code_root and line_no > 0:
            source_path = os.path.join(code_root, filename)
            if os.path.isfile(source_path):
                lines = source_cache.get(source_path)
                if lines is None:
                    try:
                        with open(source_path, "r", encoding="utf-8", errors="replace") as sf:
                            lines = sf.read().splitlines()
                    except OSError:
                        lines = []
                    source_cache[source_path] = lines
                if line_no <= len(lines):
                    row["code"] = lines[line_no - 1]

        out.append(row)

    return out


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parse self-composition KLEE log output and emit JSON rows with "
            "filename/line/column/non_ct_time/code."
        )
    )
    p.add_argument("--log", required=True, help="Path to per-case KLEE log")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument(
        "--code-root",
        default=None,
        help="Optional source tree root used to fill code lines (e.g., wllvm/mbedtls-3.2.1)",
    )
    args = p.parse_args(argv)

    if not os.path.isfile(args.log):
        print(f"Error: log not found: {args.log}", file=sys.stderr)
        return 2

    code_root = os.path.abspath(args.code_root) if args.code_root else None
    data = parse_log_rows(args.log, code_root)

    payload: Dict[str, object] = {
        "data": data,
        "dtypes": {
            "filename": "object",
            "line": "Int64",
            "column": "Int64",
            "non_ct_time": "float64",
            "code": "object",
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

