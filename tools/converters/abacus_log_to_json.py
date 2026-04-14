#!/usr/bin/env python3

import ast
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

from tools.shared.result_schema import (
    STATUS_NOT_REPRODUCED,
    build_payload,
    get_source_line,
    make_result_row,
)


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
        help="Run tools.postprocess.reproduce_positives for each row and add 'reproduced_status'",
    )
    p.add_argument(
        "--replay-executable",
        default=None,
        help="Replay executable path (required with --reproduce)",
    )
    p.add_argument(
        "--reproduce-module",
        dest="reproduce_module",
        default=None,
        help="Python module to run for reproduction (defaults to tools.postprocess.reproduce_positives)",
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
    p.add_argument(
        "--library",
        required=True,
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "constantine", "unknown"],
        help="Library identifier for this dataset.",
    )
    args = p.parse_args(argv)

    if not os.path.isfile(args.log):
        print(f"Error: log not found: {args.log}", file=sys.stderr)
        return 2

    runner_config_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "configs",
            "runner",
            "modexp_runner_config.json",
        )
    )
    preset_name = f"size_{args.sym_size}"
    try:
        with open(runner_config_path, "r", encoding="utf-8") as f:
            runner_config = ast.literal_eval(f.read())
        ref_secret_value = runner_config["presets"][preset_name]["abacus_secrets"]["exp_buf"]
    except (OSError, SyntaxError, ValueError, KeyError, TypeError) as exc:
        print(
            "Error: failed to load ABACUS reference secret from "
            f"{runner_config_path} preset {preset_name}: {exc}",
            file=sys.stderr,
        )
        return 2

    if isinstance(ref_secret_value, int):
        ref_secret = ref_secret_value
    elif isinstance(ref_secret_value, list) and ref_secret_value:
        ref_secret = 0
        for byte_value in ref_secret_value:
            if not isinstance(byte_value, int) or byte_value < 0 or byte_value > 0xFF:
                print(
                    "Error: ABACUS reference secret bytes must be integers in [0, 255]",
                    file=sys.stderr,
                )
                return 2
            ref_secret = (ref_secret << 8) | byte_value
    else:
        print(
            f"Error: unsupported ABACUS reference secret format for preset {preset_name}",
            file=sys.stderr,
        )
        return 2

    reproduce_module = args.reproduce_module
    if args.reproduce and not reproduce_module:
        reproduce_module = "tools.postprocess.reproduce_positives"
    if args.reproduce:
        if not args.replay_executable:
            print("Error: --replay-executable is required with --reproduce", file=sys.stderr)
            return 2
        if not reproduce_module:
            print("Error: missing reproduction module", file=sys.stderr)
            return 2

    with open(args.log, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    divergent: Dict[int, int] = {}
    locations: Dict[int, Dict[str, Any]] = {}
    se_time: Optional[float] = None
    qif_time: Optional[float] = None

    default_library = args.library
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
                        source_line = get_source_line(default_library, os.path.join(args.code_root, filename), line_no)
                        if source_line is not None:
                            entry["code"] = source_line

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

    validated_rows: List[Dict[str, Any]] = []
    for row in rows:
        optional = {
            k: v
            for k, v in row.items()
            if k not in {"filename", "line", "non_ct_time", "counterexamples", "reproduced_status", "library"}
        }
        counterexamples = row.get("counterexamples")
        validated_rows.append(
            make_result_row(
                filename=row.get("filename"),
                line=row.get("line"),
                non_ct_time=row.get("non_ct_time"),
                counterexamples=counterexamples if isinstance(counterexamples, dict) else {},
                reproduced_status=row.get("reproduced_status") or STATUS_NOT_REPRODUCED,
                library=row.get("library") if isinstance(row.get("library"), str) and row.get("library").strip() else default_library,
                optional_fields=optional,
            )
        )
    rows = validated_rows

    payload = build_payload(
        rows,
        optional_dtypes={
            "column": "Int64",
            "code": "object",
        },
    )
    payload["notes"] = {
            "abacus_reference_secret": {
                "source": "Loaded from configs/runner/modexp_runner_config.json preset abacus_secrets.exp_buf",
                "preset": preset_name,
                "sym_size": args.sym_size,
                "exp": ref_secret,
            }
        }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    if args.reproduce:
        cmd = [
            sys.executable,
            "-m",
            str(reproduce_module),
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
            "--library",
            str(args.library),
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
