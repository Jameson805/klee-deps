#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parse an Abacus per-case log and emit combined JSON with source location, code line, "
            "and (A,B) counterexamples. Optional replay-based reproduction is supported."
        )
    )
    p.add_argument("--log", required=True, help="Path to Abacus per-case log")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument("--sym-size", type=int, default=4, help="SYM_SIZE bytes (default: 4)")
    p.add_argument(
        "--code-root",
        default=None,
        help="Optional source root to relativize filename and fill code line",
    )
    p.add_argument(
        "--reproduce",
        action="store_true",
        help="Run reproduce_positives.py --input for each row and add 'reproduced'",
    )
    p.add_argument(
        "--replay-executable",
        default=None,
        help="Replay executable path (required with --reproduce)",
    )
    p.add_argument(
        "--reproduce-script",
        default=None,
        help="Path to reproduce_positives.py (defaults to tools/postprocess/reproduce_positives.py)",
    )
    p.add_argument(
        "--reproduce-timeout",
        type=int,
        default=180,
        help="Timeout seconds for each reproduction attempt (default: 180)",
    )
    p.add_argument(
        "--reproduce-debug",
        action="store_true",
        help="Forward --debug to reproduce_positives.py and print the exact replay command on failure.",
    )
    args = p.parse_args(argv)

    if not os.path.isfile(args.log):
        print(f"Error: log not found: {args.log}", file=sys.stderr)
        return 2

    ref_secret_by_size = {
        1: 241,
        2: 65519,
        4: 4294967279,
        8: 18446744073709551533,
        16: ((1 << 64) - 1) << 64 | 18446744073709551443,
    }
    if args.sym_size not in ref_secret_by_size:
        print("Error: --sym-size must be one of 1,2,4,8,16", file=sys.stderr)
        return 2
    ref_secret = ref_secret_by_size[args.sym_size]

    reproduce_script = args.reproduce_script
    if args.reproduce and not reproduce_script:
        here = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.normpath(os.path.join(here, "..", ".."))
        reproduce_script = os.path.join(repo_root, "tools", "postprocess", "reproduce_positives.py")
    if args.reproduce:
        if not args.replay_executable:
            print("Error: --replay-executable is required with --reproduce", file=sys.stderr)
            return 2
        if not reproduce_script or not os.path.isfile(reproduce_script):
            print(f"Error: reproduce_positives.py not found: {reproduce_script}", file=sys.stderr)
            return 2

    with open(args.log, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    divergent: Dict[int, int] = {}
    locations: Dict[int, Dict[str, Any]] = {}
    se_time: Optional[float] = None
    qif_time: Optional[float] = None

    source_cache: Dict[str, List[str]] = {}
    i = 0
    while i < len(lines):
        s = lines[i].rstrip("\n")

        m_se = re.match(r"^Time taken by SE:\s*([0-9]+(?:\.[0-9]+)?)\s+seconds\s*$", s)
        if m_se:
            se_time = float(m_se.group(1))
            i += 1
            continue

        m_qif = re.match(r"^Time taken by QIF:\s*([0-9]+(?:\.[0-9]+)?)\s+seconds\s*$", s)
        if m_qif:
            qif_time = float(m_qif.group(1))
            i += 1
            continue

        m_div = re.match(r"^\[Divergent Input\]\s+0x([0-9a-fA-F]+):\s*$", s)
        if m_div:
            addr = int(m_div.group(1), 16)
            bvals: List[int] = []
            i += 1
            while i < len(lines):
                t = lines[i].rstrip("\n")
                km = re.match(r"^\s*Key(\d+)\s*=\s*([0-9]+)\s*$", t)
                if not km:
                    break
                bvals.append(int(km.group(2)))
                i += 1
            if bvals:
                b_int = 0
                for b in bvals:
                    if b < 0 or b > 255:
                        b_int = -1
                        break
                    b_int = (b_int << 8) | b
                if b_int >= 0:
                    divergent[addr] = b_int
            continue

        m_addr = re.match(r"^Address:\s*([0-9a-fA-F]+)\b", s)
        if m_addr:
            addr = int(m_addr.group(1), 16)
            j = i + 1
            while j < len(lines):
                src_line = lines[j].rstrip("\n")
                m_src = re.match(
                    r"^Source code:\s+[^:]+:\s+(.+?)\s+line number:\s*([0-9]+)(?:\s+column number:\s*[0-9]+)?\s*$",
                    src_line,
                )
                if m_src:
                    src_path = m_src.group(1)
                    line_no = int(m_src.group(2))
                    filename = os.path.basename(src_path)
                    if args.code_root:
                        try:
                            root_abs = os.path.abspath(args.code_root)
                            src_abs = os.path.abspath(src_path)
                            if os.path.commonpath([root_abs, src_abs]) == root_abs:
                                filename = os.path.relpath(src_abs, root_abs)
                        except Exception:
                            pass

                    entry: Dict[str, Any] = {
                        "filename": filename,
                        "line": line_no,
                    }

                    if args.code_root:
                        source_path = os.path.join(args.code_root, filename)
                        if os.path.isfile(source_path):
                            content = source_cache.get(source_path)
                            if content is None:
                                try:
                                    with open(source_path, "r", encoding="utf-8", errors="replace") as sf:
                                        content = sf.read().splitlines()
                                except OSError:
                                    content = []
                                source_cache[source_path] = content
                            if 1 <= line_no <= len(content):
                                entry["code"] = content[line_no - 1]

                    locations[addr] = entry
                    break
                if re.match(r"^Address:\s*([0-9a-fA-F]+)\b", src_line):
                    break
                j += 1
            i = j
            continue

        i += 1

    rows: List[Dict[str, Any]] = []
    non_ct_time = (se_time + qif_time) if se_time is not None and qif_time is not None else None
    for addr in sorted(set(divergent.keys()) | set(locations.keys())):
        row: Dict[str, Any] = {
            "filename": None,
            "line": None,
            "counterexamples": None,
        }
        if non_ct_time is not None:
            row["non_ct_time"] = non_ct_time
        if addr in locations:
            row.update(locations[addr])
        if addr in divergent:
            row["counterexamples"] = {
                "exp": ref_secret,
                "exp__prime": divergent[addr],
            }

        rows.append(row)

    observed_keys = set()
    for row in rows:
        observed_keys.update(row.keys())

    dtypes: Dict[str, str] = {}
    if "filename" in observed_keys:
        dtypes["filename"] = "object"
    if "line" in observed_keys:
        dtypes["line"] = "Int64"
    if "column" in observed_keys:
        dtypes["column"] = "Int64"
    if "non_ct_time" in observed_keys:
        dtypes["non_ct_time"] = "float64"
    if "code" in observed_keys:
        dtypes["code"] = "object"
    if "counterexamples" in observed_keys:
        dtypes["counterexamples"] = "object"
    if "reproduced" in observed_keys:
        dtypes["reproduced"] = "object"

    payload = {
        "data": rows,
        "dtypes": dtypes,
        "notes": {
            "abacus_reference_secret": {
                "source": "Hard-coded from include/common.h ABACUS branch (second-closest prime constants)",
                "sym_size": args.sym_size,
                "exp": ref_secret,
            }
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    if args.reproduce:
        cmd = [
            sys.executable,
            str(reproduce_script),
            "--abacus-json",
            str(args.out),
            "--output",
            str(args.out),
            "--executable",
            str(args.replay_executable),
            "--sym-size",
            str(args.sym_size),
            "--timeout",
            str(args.reproduce_timeout),
        ]
        if args.reproduce_debug:
            cmd.append("--debug")
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            print(f"[reproduce] batch reproduction failed with rc={proc.returncode}", file=sys.stderr)
            return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
