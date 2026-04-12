#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import subprocess

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


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))


try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore


# Import get_addr_info from repository utility package.
_ADDRINFO_IMPORT_ERROR: Optional[str] = None
try:
    from tools.utilities.addrinfo import get_addr_info  # type: ignore
except Exception as e:  # pragma: no cover
    get_addr_info = None  # type: ignore
    _ADDRINFO_IMPORT_ERROR = str(e)


@dataclass
class LeakInfo:
    leak_type: str  # 'control flow' or 'memory access'
    seconds: float


_CHECKCT_RE = re.compile(
    r"^\[checkct:result\] Instruction (?P<addr>0x[0-9a-fA-F]+) has (?P<kind>control flow|memory access) leak \((?P<secs>[0-9.]+)s\)\s*$"
)


def _is_sep_line(s: str) -> bool:
    s = s.strip()
    return bool(s) and all(ch == "=" for ch in s)


def parse_output_log(path: str, title: Optional[str]) -> Dict[int, LeakInfo]:
    """Parse BINSEC output.log and return map: address(int) -> LeakInfo.

    If title is provided, only parses leak lines within the section labeled:
        =======
        <title>
        =======
    """

    leaks: Dict[int, LeakInfo] = {}
    current_title: Optional[str] = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")

        # Detect section headers emitted by run_binsec.sh
        if _is_sep_line(line) and i + 2 < len(lines):
            maybe_title = lines[i + 1].rstrip("\n").strip()
            maybe_sep2 = lines[i + 2].rstrip("\n")
            if _is_sep_line(maybe_sep2):
                current_title = maybe_title
                i += 3
                continue

        m = _CHECKCT_RE.match(line.strip())
        if m:
            if title is None or current_title == title:
                addr = int(m.group("addr"), 16)
                leaks[addr] = LeakInfo(
                    leak_type=m.group("kind"),
                    seconds=float(m.group("secs")),
                )
        i += 1

    return leaks


def _as_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, int):
        return int(x)
    if isinstance(x, str):
        try:
            return int(x, 0)
        except Exception:
            return None
    return None


def _extract_scalar_list_value(val: Any) -> Optional[int]:
    """BINSEC encodes many things as a TOML list like ["0x123"] or ["42"]."""
    if not isinstance(val, list) or not val:
        return None
    return _as_int(val[0])


def parse_binsec_toml(path: str) -> Tuple[List[int], Dict[int, Dict[str, Dict[str, int]]]]:
    """Parse a BINSEC -checkct stats TOML.

    Returns:
      insecure_addrs: list[int]
      models: addr -> { 'secret1': {k->int}, 'secret2': {k->int}, 'public': {k->int} }

    Notes:
      - We only extract scalar-like values stored as a TOML list of 1 quoted int.
      - We ignore memory dumps (tables ending in .memory."@") on purpose.
    """

    if tomllib is None:
        raise RuntimeError(
            "tomllib is not available. Use Python 3.11+ (or install a TOML parser and adapt this script)."
        )

    with open(path, "rb") as f:
        doc = tomllib.load(f)

    ct_report = doc.get("CT report", {})
    insecure: List[int] = []

    status = ct_report.get("Instructions status", {})
    insecure_list = status.get("insecure", [])
    if isinstance(insecure_list, list):
        for item in insecure_list:
            addr = _as_int(item)
            if addr is not None:
                insecure.append(addr)

    models: Dict[int, Dict[str, Dict[str, int]]] = {}
    insec_models = ct_report.get("Insecurity models", {})
    if isinstance(insec_models, dict):
        for addr_key, payload in insec_models.items():
            addr = _as_int(addr_key)
            if addr is None or not isinstance(payload, dict):
                continue
            for section in ("secret1", "secret2", "public"):
                sec = payload.get(section, {})
                if not isinstance(sec, dict):
                    continue
                for k, v in sec.items():
                    scalar = _extract_scalar_list_value(v)
                    if scalar is None:
                        continue
                    models.setdefault(addr, {}).setdefault(section, {})[str(k)] = scalar

    # If 'insecure' is missing, fall back to whatever models we saw.
    if not insecure:
        insecure = sorted(models.keys())

    return insecure, models


def _build_basename_index(code_root: str) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for dirpath, _, filenames in os.walk(code_root):
        for fn in filenames:
            if fn not in index:
                index[fn] = os.path.join(dirpath, fn)
    return index


def _normalize_filename_for_json(path: str) -> str:
    # Fallback if we can't relativize.
    return os.path.basename(path)


def _relativize_to_code_root(debug_path: str, code_root: Optional[str]) -> str:
    if not code_root:
        return _normalize_filename_for_json(debug_path)
    try:
        code_root_abs = os.path.abspath(code_root)
        debug_abs = os.path.abspath(debug_path)
        common = os.path.commonpath([code_root_abs, debug_abs])
        if common == code_root_abs:
            rel = os.path.relpath(debug_abs, code_root_abs)
            return rel
    except Exception:
        pass
    return _normalize_filename_for_json(debug_path)


def _pick_model_values(models: Dict[int, Dict[str, Dict[str, int]]], addr: int) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Return (exp, exp_prime, base, mod) if present for this addr."""
    model = models.get(addr)
    if not model:
        return None, None, None, None

    s1 = model.get("secret1", {})
    s2 = model.get("secret2", {})
    pub = model.get("public", {})

    # BINSEC stats use *_buf keys; interpret them as the big-endian integer value of the buffer.
    exp = s1.get("exp_buf") if isinstance(s1, dict) else None
    exp_p = s2.get("exp_buf") if isinstance(s2, dict) else None
    base = pub.get("base_buf") if isinstance(pub, dict) else None
    mod = pub.get("mod_buf") if isinstance(pub, dict) else None
    return exp, exp_p, base, mod


_REPRO_LINE_RE = re.compile(r"0x[0-9a-fA-F]+:\s+(?P<file>.+?):(?P<line>[0-9]+):(?P<col>[0-9]+)\s*$")


def _tail_lines(text: str, n: int = 12) -> str:
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])


def _run_reproduce(
    reproduce_module: str,
    replay_executable: str,
    sym_size: int,
    exp: int,
    exp_prime: int,
    base: Optional[int],
    mod: Optional[int],
    needs_publics: bool,
    timeout_s: int,
) -> Tuple[Optional[Tuple[str, int, int]], int, str]:
    """Run reproduce_positives.py --input and parse the reported divergence location.

    Returns: (location|None, returncode, combined_output)
    """
    secret_spec = f"exp:{sym_size}={exp}/{exp_prime}"
    public_spec = ""
    if needs_publics:
        if base is None or mod is None:
            return None, 2, "missing public counterexamples for var_pub reproduction"
        public_spec = f"base:{sym_size}={base},mod:{sym_size}={mod}"

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
    if needs_publics:
        cmd += ["--public", public_spec]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        return None, proc.returncode, out

    for line in out.splitlines():
        m = _REPRO_LINE_RE.search(line.strip())
        if m:
            return (m.group("file"), int(m.group("line")), int(m.group("col"))), proc.returncode, out
    return None, proc.returncode, out


def build_rows(
    insecure_addrs: List[int],
    models: Dict[int, Dict[str, Dict[str, int]]],
    leaks: Dict[int, LeakInfo],
    addr_executable: str,
    code_root: Optional[str],
    library: str,
    sym_size: int,
    reproduce_module: Optional[str],
    replay_executable: Optional[str],
    needs_publics: bool,
    reproduce_timeout_s: int,
) -> List[Dict[str, Any]]:
    code_index: Optional[Dict[str, str]] = None
    if code_root:
        code_index = _build_basename_index(code_root)
    source_library = library

    rows: List[Dict[str, Any]] = []

    for addr in insecure_addrs:
        info: Optional[Tuple[str, int, int]] = None
        if get_addr_info is not None:
            try:
                info = get_addr_info(addr_executable, addr)
            except Exception:
                info = None

        filename: Optional[str] = None
        line_no: Optional[int] = None
        col_no: Optional[int] = None
        debug_path: Optional[str] = None

        if info is not None:
            debug_path, l, c = info
            filename = _relativize_to_code_root(debug_path, code_root)
            line_no = int(l) if l is not None else None
            col_no = int(c) if c is not None else None

        leak = leaks.get(addr)
        non_ct_time = leak.seconds if leak is not None else None

        exp, exp_p, base, mod = _pick_model_values(models, addr)
        counterexamples: Optional[Dict[str, int]] = None
        if exp is not None and exp_p is not None:
            counterexamples = {"exp": exp, "exp__prime": exp_p}
            # Include publics if available; useful for var_pub reproduction.
            if base is not None:
                counterexamples["base"] = base
            if mod is not None:
                counterexamples["mod"] = mod

        code: Optional[str] = None
        if filename and line_no and code_root and code_index is not None:
            candidate = None
            if debug_path and os.path.isfile(debug_path):
                candidate = debug_path
            else:
                candidate = code_index.get(filename)
            if candidate:
                code = get_source_line(source_library, candidate, line_no)

        reproduced_status: Optional[str] = None
        if (
            reproduce_module
            and replay_executable
            and exp is not None
            and exp_p is not None
            and filename is not None
            and line_no is not None
            and col_no is not None
        ):
            reported_loc = format_location(filename, line_no, col_no)
            print(
                f"[reproduce] addr=0x{addr:x} reported={reported_loc}",
                file=sys.stderr,
                flush=True,
            )

            loc, rc, repro_out = _run_reproduce(
                reproduce_module=reproduce_module,
                replay_executable=replay_executable,
                sym_size=sym_size,
                exp=exp,
                exp_prime=exp_p,
                base=base,
                mod=mod,
                needs_publics=needs_publics,
                timeout_s=reproduce_timeout_s,
            )
            if loc is None:
                if rc == 124:
                    reproduced_status = STATUS_TIMEOUT
                elif rc == 1:
                    reproduced_status = STATUS_IDENTICAL_TRACE
                elif rc in (0, 3):
                    reproduced_status = STATUS_LOCATION_MISMATCH
                else:
                    print(
                        f"[reproduce] addr=0x{addr:x} FAILED: reproduce_positives.py rc={rc}\n{_tail_lines(repro_out)}",
                        file=sys.stderr,
                        flush=True,
                    )
                    raise RuntimeError(f"reproduce_positives.py failed with rc={rc} for addr=0x{addr:x}")
                print(
                    f"[reproduce] addr=0x{addr:x} {reproduced_status.upper()}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                rep_file, rep_line, rep_col = loc
                repro_loc = format_location(rep_file, rep_line, rep_col)
                is_success = (os.path.basename(rep_file) == os.path.basename(filename)) and (rep_line == line_no) and (rep_col == col_no)
                reproduced_status = STATUS_SUCCESS if is_success else STATUS_LOCATION_MISMATCH
                if is_success:
                    print(
                        f"[reproduce] addr=0x{addr:x} SUCCESS divergence={repro_loc}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    print(
                        f"[reproduce] addr=0x{addr:x} FAIL divergence={repro_loc} (reported={reported_loc})",
                        file=sys.stderr,
                        flush=True,
                    )

        row: Dict[str, Any] = {
            "filename": filename,
            "line": line_no,
            "column": col_no,
        }
        if non_ct_time is not None:
            row["non_ct_time"] = non_ct_time
        if code is not None:
            row["code"] = code
        if counterexamples is not None:
            row["counterexamples"] = counterexamples
        if reproduced_status is not None:
            row["reproduced_status"] = reproduced_status
        rows.append(row)

    return rows


def default_title_for_toml_name(toml_path: str) -> Optional[str]:
    name = os.path.basename(toml_path)
    mapping = {
        "mbedtls_fix_pub.toml": "Mbed TLS 3.2.1 (Fix Pub)",
        "mbedtls_var_pub.toml": "Mbed TLS 3.2.1 (Var Pub)",
        "libgcrypt_fix_pub.toml": "Libgcrypt 1.10.1 (Fix Pub)",
        "libgcrypt_var_pub.toml": "Libgcrypt 1.10.1 (Var Pub)",
    }
    if name in mapping:
        return mapping[name]

    m = re.match(r"openssl_(?P<algo>[a-z0-9_]+)_(?P<kind>fix_pub|var_pub)\.toml$", name)
    if m:
        algo = m.group("algo")
        kind = "Fix Pub" if m.group("kind") == "fix_pub" else "Var Pub"
        return f"OpenSSL 1.1.1q {algo} ({kind})"

    return None


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Convert BINSEC -checkct stats TOML + output.log into a KLEE-like combined JSON "
            "(best-effort filename/line/col via addrinfo.py)."
        )
    )
    p.add_argument(
        "--toml",
        required=True,
        help="Path to BINSEC stats TOML (e.g., results/binsec_results/libgcrypt_fix_pub.toml)",
    )
    p.add_argument(
        "--output-log",
        required=True,
        help="Path to shared console output log (e.g., results/binsec_results/output.log)",
    )
    p.add_argument(
        "--executable",
        required=True,
        help="Path to the analyzed BINSEC executable (used for addr->source) (e.g., benchmarks/libgcrypt-and-libgpg-error/binsec_fix_pub)",
    )
    p.add_argument(
        "--sym-size",
        type=int,
        default=4,
        help="Symbol size in bytes (SYM_SIZE), used for reproduction input encoding (default: 4).",
    )
    p.add_argument(
        "--replay-executable",
        default=None,
        help="Path to the REPLAY executable used by reproduce_positives.py (e.g., benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay).",
    )
    p.add_argument(
        "--reproduce",
        action="store_true",
        help="If set, run reproduce_positives.py --input per row and add 'reproduced_status' field.",
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
        help="Timeout seconds for each reproduction attempt (default: 180).",
    )
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument(
        "--title",
        default=None,
        help=(
            "Section title inside output.log to scope timing extraction (e.g., 'Libgcrypt 1.10.1 (Fix Pub)'). "
            "If omitted, uses a heuristic based on --toml filename, else scans entire log."
        ),
    )
    p.add_argument(
        "--code-path",
        default=None,
        help="Optional source tree root used to fill the 'code' field by basename lookup.",
    )
    p.add_argument(
        "--library",
        required=True,
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "constantine", "unknown"],
        help="Library identifier for this dataset.",
    )

    args = p.parse_args(argv)

    if tomllib is None:
        print("Error: tomllib not available; use Python 3.11+", file=sys.stderr)
        return 2

    if get_addr_info is None:
        print(
            "Warning: failed to import addrinfo.get_addr_info; filename/line/column will be null. "
            f"Import error: {_ADDRINFO_IMPORT_ERROR}",
            file=sys.stderr,
        )

    title = args.title or default_title_for_toml_name(args.toml)

    needs_publics = bool(re.search(r"_var_pub\.toml$", os.path.basename(args.toml)))

    reproduce_module = args.reproduce_module
    if args.reproduce and reproduce_module is None:
        reproduce_module = "tools.postprocess.reproduce_positives"

    if args.reproduce:
        if not reproduce_module:
            print("Error: missing reproduction module", file=sys.stderr)
            return 2
        if not args.replay_executable:
            print("Error: --replay-executable is required when --reproduce is set", file=sys.stderr)
            return 2

    insecure_addrs, models = parse_binsec_toml(args.toml)
    leaks = parse_output_log(args.output_log, title=title)

    try:
        rows = build_rows(
            insecure_addrs=insecure_addrs,
            models=models,
            leaks=leaks,
            addr_executable=args.executable,
            code_root=args.code_path,
            library=args.library,
            sym_size=args.sym_size,
            reproduce_module=reproduce_module if args.reproduce else None,
            replay_executable=args.replay_executable if args.reproduce else None,
            needs_publics=needs_publics,
            reproduce_timeout_s=args.reproduce_timeout,
        )
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

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
                library=row.get("library") if isinstance(row.get("library"), str) and row.get("library").strip() else args.library,
                optional_fields=optional,
            )
        )
    rows = validated_rows

    out_obj = build_payload(
        rows,
        optional_dtypes={
            "column": "Int64",
            "code": "object",
        },
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, indent=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
