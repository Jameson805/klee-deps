#!/usr/bin/env python3

import os
import sys

import argparse
import json
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from tools.shared.result_schema import (
    STATUS_IDENTICAL_TRACE,
    STATUS_LOCATION_MISMATCH,
    STATUS_NOT_REPRODUCED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    build_payload,
    format_location,
    get_source_line,
    make_result_row,
)


_NON_CT_RE = re.compile(
    r"^\[(?P<ts>[0-9]+(?:\.[0-9]+)?)\]\s+\[NON-CT BRANCH\]\s+(?P<file>.+?):(?P<line>[0-9]+):(?P<col>[0-9]+)(?:\s+.*)?$"
)
_NON_CT_CEX_RE = re.compile(
    r"^\[(?P<ts>[0-9]+(?:\.[0-9]+)?)\]\s+\[NON-CT CEX\]\s+(?P<file>.+?):(?P<line>[0-9]+):(?P<col>[0-9]+)\s+(?P<kv>.+?)\s*$"
)
_ANY_TS_RE = re.compile(r"^\[(?P<ts>[0-9]+(?:\.[0-9]+)?)\]")
_REPRO_LINE_RE = re.compile(r"0x[0-9a-fA-F]+:\s+(?P<file>.+?):(?P<line>[0-9]+):(?P<col>[0-9]+)\s*$")


def _parse_counterexample_tokens(raw: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for token in raw.strip().split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            continue
        try:
            out[k] = int(v, 0)
        except ValueError:
            continue
    return out


def _read_text_auto(path: str) -> str:
    """Read text file with automatic UTF-8-first decoding.

    Tries UTF-8 (including BOM) and falls back to latin-1 when needed.
    """
    with open(path, "rb") as f:
        data = f.read()

    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass

    return data.decode("latin-1")


def parse_log_rows(log_path: str, code_root: Optional[str], library: str) -> List[Dict[str, object]]:
    start_ts: Optional[float] = None
    first_hit_by_loc: Dict[Tuple[str, int, int], float] = {}
    first_cex_by_loc: Dict[Tuple[str, int, int], Dict[str, int]] = {}

    log_text = _read_text_auto(log_path)
    for raw_line in log_text.splitlines():
            line = raw_line.rstrip("\n")
            if start_ts is None:
                m_any = _ANY_TS_RE.match(line)
                if m_any:
                    start_ts = float(m_any.group("ts"))

            m = _NON_CT_RE.match(line)
            if m:
                ts = float(m.group("ts"))
                filename = m.group("file")
                line_no = int(m.group("line"))
                col_no = int(m.group("col"))
                key = (filename, line_no, col_no)
                hit = ts if start_ts is None else ts - start_ts
                prev = first_hit_by_loc.get(key)
                if prev is None or hit < prev:
                    first_hit_by_loc[key] = hit
                continue

            mc = _NON_CT_CEX_RE.match(line)
            if not mc:
                continue

            filename = mc.group("file")
            line_no = int(mc.group("line"))
            col_no = int(mc.group("col"))
            key = (filename, line_no, col_no)
            if key in first_cex_by_loc:
                continue
            cex = _parse_counterexample_tokens(mc.group("kv"))
            if cex:
                first_cex_by_loc[key] = cex

    if start_ts is None:
        return []

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

        cex = first_cex_by_loc.get((filename, line_no, col_no))
        if cex is not None:
            row["counterexamples"] = cex

        if code_root and line_no > 0:
            source_line = get_source_line(library, os.path.join(code_root, filename), line_no)
            if source_line is not None:
                row["code"] = source_line

        out.append(row)

    return out


def _run_reproduce(
    reproduce_module: str,
    replay_executable: str,
    sym_size: int,
    cex: Dict[str, int],
    timeout_s: int,
) -> Tuple[Optional[Tuple[str, int, int]], int, str]:
    exp = cex.get("exp")
    exp_prime = cex.get("exp__prime")
    if exp is None or exp_prime is None:
        return None, 2, "missing exp/exp__prime"

    secret_spec = f"exp:{sym_size}={exp}/{exp_prime}"
    cmd = [
        sys.executable,
        "-m",
        reproduce_module,
        "--input",
        "--executable",
        replay_executable,
        "--secret",
        secret_spec,
        "--timeout",
        str(timeout_s),
    ]

    if "base" in cex and "mod" in cex:
        public_spec = f"base:{sym_size}={cex['base']},mod:{sym_size}={cex['mod']}"
        cmd += ["--public", public_spec]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        return None, proc.returncode, out

    for line in out.splitlines():
        m = _REPRO_LINE_RE.search(line.strip())
        if m:
            return (m.group("file"), int(m.group("line")), int(m.group("col"))), proc.returncode, out
    return None, proc.returncode, out


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parse self-composition KLEE log output and emit JSON rows with "
            "filename/line/column/non_ct_time/code."
        )
    )
    p.add_argument("--log", required=True, help="Path to per-case KLEE log")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument("--sym-size", type=int, default=4, help="Symbol size in bytes (SYM_SIZE), default: 4")
    p.add_argument("--reproduce", action="store_true", help="Run replay reproduction for each row with counterexamples")
    p.add_argument("--replay-executable", default=None, help="Path to replay executable (required with --reproduce)")
    p.add_argument(
        "--reproduce-module",
        dest="reproduce_module",
        default=None,
        help="Python module to run for reproduction (defaults to tools.postprocess.reproduce_positives)",
    )
    p.add_argument("--reproduce-timeout", type=int, default=1200, help="Timeout in seconds per reproduction (default: 1200)")
    p.add_argument(
        "--code-root",
        default=None,
        help="Optional source tree root used to fill code lines (e.g., benchmarks/mbedtls-3.2.1)",
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

    reproduce_module = args.reproduce_module
    if args.reproduce and not reproduce_module:
        reproduce_module = "tools.postprocess.reproduce_positives"

    if args.reproduce:
        if not args.replay_executable:
            print("Error: --replay-executable is required with --reproduce", file=sys.stderr)
            return 2
        if not os.path.isfile(args.replay_executable):
            print(f"Error: replay executable not found: {args.replay_executable}", file=sys.stderr)
            return 2
        if not reproduce_module:
            print("Error: missing reproduction module", file=sys.stderr)
            return 2

    code_root = os.path.abspath(args.code_root) if args.code_root else None
    data = parse_log_rows(args.log, code_root, args.library)

    if args.reproduce:
        for row in data:
            filename = row.get("filename")
            line_no = row.get("line")
            col_no = row.get("column")
            cex = row.get("counterexamples")
            if not isinstance(filename, str) or not isinstance(line_no, int) or not isinstance(col_no, int):
                continue
            if not isinstance(cex, dict):
                row["reproduced_status"] = STATUS_LOCATION_MISMATCH
                print("[reproduce] skipped: missing counterexamples", file=sys.stderr, flush=True)
                continue

            reported_loc = format_location(filename, line_no, col_no)
            print(f"[reproduce] reported={reported_loc}", file=sys.stderr, flush=True)

            loc, rc, _ = _run_reproduce(
                reproduce_module=str(reproduce_module),
                replay_executable=str(args.replay_executable),
                sym_size=int(args.sym_size),
                cex=cex,
                timeout_s=int(args.reproduce_timeout),
            )

            if loc is None:
                if rc == 124:
                    row["reproduced_status"] = STATUS_TIMEOUT
                elif rc == 1:
                    row["reproduced_status"] = STATUS_IDENTICAL_TRACE
                elif rc in (0, 3):
                    row["reproduced_status"] = STATUS_LOCATION_MISMATCH
                else:
                    print(
                        f"[reproduce] operational failure rc={rc}; aborting batch",
                        file=sys.stderr,
                        flush=True,
                    )
                    return rc if rc != 0 else 2
                print(
                    f"[reproduce] {row['reproduced_status']} rc={rc}",
                    file=sys.stderr,
                    flush=True,
                )
                continue

            rep_file, rep_line, rep_col = loc
            reproduced = (
                os.path.basename(rep_file) == os.path.basename(filename)
                and rep_line == line_no
                and rep_col == col_no
            )
            row["reproduced_status"] = STATUS_SUCCESS if reproduced else STATUS_LOCATION_MISMATCH
            print(
                f"[reproduce] {'SUCCESS' if reproduced else 'FAIL'} divergence={format_location(rep_file, rep_line, rep_col)}",
                file=sys.stderr,
                flush=True,
            )

    normalized_data: List[Dict[str, object]] = []
    for row in data:
        optional = {
            k: v
            for k, v in row.items()
            if k not in {"filename", "line", "non_ct_time", "counterexamples", "reproduced_status", "library"}
        }
        counterexamples = row.get("counterexamples")
        normalized_data.append(
            make_result_row(
                filename=row.get("filename"),
                line=row.get("line"),
                non_ct_time=row.get("non_ct_time"),
                counterexamples=counterexamples if isinstance(counterexamples, dict) else {},
                reproduced_status=row.get("reproduced_status") or STATUS_NOT_REPRODUCED,
                library=row.get("library") if isinstance(row.get("library"), str) and row.get("library").strip() else args.library,
                optional_fields=optional,
            )
        )
    data = normalized_data

    payload: Dict[str, object] = build_payload(
        data,
        optional_dtypes={
            "column": "Int64",
            "code": "object",
        },
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
