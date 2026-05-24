#!/usr/bin/env python3
"""Convert BINSEC per-case outputs into the shared JSON result schema.

The converter consumes one stats TOML plus the matching worker log and relies
on explicit input-layout metadata from the caller instead of inferring replay
semantics from filenames.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any
import subprocess
import tomllib

from tools.shared.result_schema import (
    KIND_BRANCH,
    KIND_MEMORY,
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
from tools.shared.runtime_limits import configure_int_max_str_digits


configure_int_max_str_digits()


_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))

# Import get_addr_info from repository utility package.
_ADDRINFO_IMPORT_ERROR: str | None = None
try:
    from tools.utilities.addrinfo import get_addr_info  # type: ignore
except Exception as e:  # pragma: no cover
    get_addr_info = None  # type: ignore
    _ADDRINFO_IMPORT_ERROR = str(e)


@dataclass
class LeakInfo:
    leak_type: str  # 'control flow' or 'memory access'
    seconds: float


@dataclass
class InputLayout:
    name: str
    size: int
    model_key: str


_CHECKCT_RE = re.compile(
    r"^\[checkct:result\] Instruction (?P<addr>0x[0-9a-fA-F]+) has (?P<kind>control flow|memory access) leak \((?P<secs>[0-9.]+)s\)\s*$"
)


def _is_sep_line(s: str) -> bool:
    s = s.strip()
    return bool(s) and all(ch == "=" for ch in s)


def parse_output_log(path: str) -> dict[int, LeakInfo]:
    """Parse a per-case BINSEC worker log and return address(int) -> LeakInfo."""

    leaks: dict[int, LeakInfo] = {}

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")

        m = _CHECKCT_RE.match(line.strip())
        if m:
            addr = int(m.group("addr"), 16)
            leaks[addr] = LeakInfo(
                leak_type=m.group("kind"),
                seconds=float(m.group("secs")),
            )
        i += 1

    return leaks


def _as_int(x: Any) -> int | None:
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


def _extract_scalar_list_value(val: Any) -> int | None:
    """BINSEC encodes many things as a TOML list like ["0x123"] or ["42"]."""
    if not isinstance(val, list) or not val:
        return None
    return _as_int(val[0])


def parse_binsec_toml(path: str) -> tuple[list[int], dict[int, dict[str, dict[str, int]]]]:
    """Parse a BINSEC -checkct stats TOML.

    Returns:
      insecure_addrs: list[int]
      models: addr -> { 'secret1': {k->int}, 'secret2': {k->int}, 'public': {k->int} }

    Notes:
      - We only extract scalar-like values stored as a TOML list of 1 quoted int.
      - We ignore memory dumps (tables ending in .memory."@") on purpose.
    """

    with open(path, "rb") as f:
        doc = tomllib.load(f)

    ct_report = doc.get("CT report", {})
    insecure: list[int] = []

    status = ct_report.get("Instructions status", {})
    insecure_list = status.get("insecure", [])
    if isinstance(insecure_list, list):
        for item in insecure_list:
            addr = _as_int(item)
            if addr is not None:
                insecure.append(addr)

    models: dict[int, dict[str, dict[str, int]]] = {}
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


def _build_basename_index(code_root: str) -> dict[str, str]:
    index: dict[str, str] = {}
    for dirpath, _, filenames in os.walk(code_root):
        for fn in filenames:
            if fn not in index:
                index[fn] = os.path.join(dirpath, fn)
    return index


def _normalize_filename_for_json(path: str) -> str:
    # Fallback if we can't relativize.
    return os.path.basename(path)


def _relativize_to_code_root(debug_path: str, code_root: str | None) -> str:
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


def _parse_input_layouts(raw_specs: list[str], defaults: list[tuple[str, int, str]], kind: str) -> list[InputLayout]:
    if not raw_specs:
        return [InputLayout(name=name, size=size, model_key=model_key) for name, size, model_key in defaults]

    layouts: list[InputLayout] = []
    for spec in raw_specs:
        parts = spec.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid {kind} input specification '{spec}', expected name:bytes:model_key")
        name, size_str, model_key = (part.strip() for part in parts)
        if not name or not model_key:
            raise ValueError(f"Invalid {kind} input specification '{spec}', missing name or model key")
        try:
            size = int(size_str, 0)
        except ValueError as exc:
            raise ValueError(f"Invalid byte size in {kind} input specification '{spec}'") from exc
        if size <= 0:
            raise ValueError(f"Byte size must be positive in {kind} input specification '{spec}'")
        layouts.append(InputLayout(name=name, size=size, model_key=model_key))

    return layouts


def _pick_model_counterexamples(
    models: dict[int, dict[str, dict[str, int]]],
    addr: int,
    secret_inputs: list[InputLayout],
    public_inputs: list[InputLayout],
) -> dict[str, int] | None:
    model = models.get(addr)
    if not model:
        return None

    s1 = model.get("secret1", {})
    s2 = model.get("secret2", {})
    pub = model.get("public", {})

    counterexamples: dict[str, int] = {}

    for inp in secret_inputs:
        value = s1.get(inp.model_key) if isinstance(s1, dict) else None
        prime_value = s2.get(inp.model_key) if isinstance(s2, dict) else None
        if value is None or prime_value is None:
            continue
        counterexamples[inp.name] = value
        counterexamples[f"{inp.name}__prime"] = prime_value

    for inp in public_inputs:
        value = pub.get(inp.model_key) if isinstance(pub, dict) else None
        if value is None:
            continue
        counterexamples[inp.name] = value

    return counterexamples or None


_REPRO_LINE_RE = re.compile(r"0x[0-9a-fA-F]+:\s+(?P<file>.+?):(?P<line>[0-9]+):(?P<col>[0-9]+)\s*$")


def _tail_lines(text: str, n: int = 12) -> str:
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])


def _run_reproduce(
    reproduce_module: str,
    replay_executable: str,
    counterexamples: dict[str, int],
    secret_inputs: list[InputLayout],
    public_inputs: list[InputLayout],
    timeout_s: int,
) -> tuple[tuple[str, int, int] | None, int, str]:
    """Run reproduce_positives.py --input and parse the reported divergence location.

    Returns: (location|None, returncode, combined_output)
    """
    secret_parts: list[str] = []
    for inp in secret_inputs:
        value = counterexamples.get(inp.name)
        prime_value = counterexamples.get(f"{inp.name}__prime")
        if value is None or prime_value is None:
            return None, 2, f"missing secret counterexamples for {inp.name}"
        secret_parts.append(f"{inp.name}:{inp.size}={value}/{prime_value}")

    public_parts: list[str] = []
    for inp in public_inputs:
        value = counterexamples.get(inp.name)
        if value is None:
            return None, 2, f"missing public counterexamples for {inp.name}"
        public_parts.append(f"{inp.name}:{inp.size}={value}")

    secret_spec = ",".join(secret_parts)
    public_spec = ",".join(public_parts)

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
    if public_spec:
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
    insecure_addrs: list[int],
    models: dict[int, dict[str, dict[str, int]]],
    leaks: dict[int, LeakInfo],
    addr_executable: str,
    code_root: str | None,
    library: str,
    secret_inputs: list[InputLayout],
    public_inputs: list[InputLayout],
    reproduce_module: str | None,
    replay_executable: str | None,
    reproduce_timeout_s: int,
) -> list[dict[str, Any]]:
    code_index: dict[str, str] | None = None
    if code_root:
        code_index = _build_basename_index(code_root)
    source_library = library

    rows: list[dict[str, Any]] = []

    for addr in insecure_addrs:
        info: tuple[str, int, int] | None = None
        if get_addr_info is not None:
            try:
                info = get_addr_info(addr_executable, addr)
            except Exception:
                info = None

        filename: str | None = None
        line_no: int | None = None
        col_no: int | None = None
        debug_path: str | None = None

        if info is not None:
            debug_path, l, c = info
            filename = _relativize_to_code_root(debug_path, code_root)
            line_no = int(l) if l is not None else None
            col_no = int(c) if c is not None else None

        leak = leaks.get(addr)
        non_ct_time = leak.seconds if leak is not None else None

        counterexamples = _pick_model_counterexamples(models, addr, secret_inputs, public_inputs)

        code: str | None = None
        if filename and line_no and code_root and code_index is not None:
            candidate = None
            if debug_path and os.path.isfile(debug_path):
                candidate = debug_path
            else:
                candidate = code_index.get(filename)
            if candidate:
                code = get_source_line(source_library, candidate, line_no)

        reproduced_status: str | None = None
        if (
            reproduce_module
            and replay_executable
            and counterexamples is not None
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
                counterexamples=counterexamples,
                secret_inputs=secret_inputs,
                public_inputs=public_inputs,
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

        row: dict[str, Any] = {
            "filename": filename,
            "line": line_no,
            "column": col_no,
        }
        if non_ct_time is not None:
            row["non_ct_time"] = non_ct_time
        if leak is not None:
            row["kind"] = KIND_BRANCH if leak.leak_type == "control flow" else KIND_MEMORY
        if code is not None:
            row["code"] = code
        if counterexamples is not None:
            row["counterexamples"] = counterexamples
        if reproduced_status is not None:
            row["reproduced_status"] = reproduced_status
        rows.append(row)

    return rows

def convert_binsec_toml(
    *,
    toml_path: str,
    output_log: str,
    executable: str,
    secret_inputs: list[str] | None = None,
    public_inputs: list[str] | None = None,
    replay_executable: str | None = None,
    reproduce: bool = False,
    reproduce_module: str | None = None,
    reproduce_timeout: int = 1200,
    output_path: str | None = None,
    code_path: str | None = None,
    library: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Convert one BINSEC case using explicit replay layouts and per-case worker output."""
    secret_layouts = _parse_input_layouts(secret_inputs or [], [], "secret")
    public_layouts = _parse_input_layouts(public_inputs or [], [], "public")

    reproduce_module = reproduce_module or ("tools.postprocess.reproduce_positives" if reproduce else None)
    if reproduce and not replay_executable:
        raise ValueError("replay_executable is required when reproduce=True")
    if reproduce and not secret_layouts:
        raise ValueError("secret_inputs are required when reproduce=True")

    insecure_addrs, models = parse_binsec_toml(toml_path)
    leaks = parse_output_log(output_log)
    rows = build_rows(
        insecure_addrs=insecure_addrs,
        models=models,
        leaks=leaks,
        addr_executable=executable,
        code_root=code_path,
        library=library,
        secret_inputs=secret_layouts,
        public_inputs=public_layouts,
        reproduce_module=reproduce_module if reproduce else None,
        replay_executable=replay_executable if reproduce else None,
        reproduce_timeout_s=reproduce_timeout,
    )

    validated_rows: list[dict[str, Any]] = []
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
                library=row.get("library") if isinstance(row.get("library"), str) and row.get("library").strip() else library,
                optional_fields=optional,
            )
        )

    payload = build_payload(
        validated_rows,
        optional_dtypes={
            "column": "Int64",
            "code": "object",
            "kind": "object",
        },
        metadata=metadata,
    )

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    return payload


def main(argv: list[str]) -> int:
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
        "--secret-input",
        action="append",
        default=[],
        help="Replay/model mapping name:bytes:model_key (repeatable).",
    )
    p.add_argument(
        "--public-input",
        action="append",
        default=[],
        help="Replay/model mapping name:bytes:model_key (repeatable).",
    )
    p.add_argument(
        "--replay-executable",
        default=None,
        help="Path to the REPLAY executable used by reproduce_positives.py (e.g., benchmarks/libgcrypt-and-libgpg-error/artifacts/klee/modexp/fix_pub_replay).",
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
        default=1200,
        help="Timeout seconds for each reproduction attempt (default: 1200).",
    )
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument(
        "--code-path",
        default=None,
        help="Optional source tree root used to fill the 'code' field by basename lookup.",
    )
    p.add_argument(
        "--library",
        required=True,
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "unknown"],
        help="Library identifier for this dataset.",
    )

    args = p.parse_args(argv)

    if get_addr_info is None:
        print(
            "Warning: failed to import addrinfo.get_addr_info; filename/line/column will be null. "
            f"Import error: {_ADDRINFO_IMPORT_ERROR}",
            file=sys.stderr,
        )

    try:
        convert_binsec_toml(
            toml_path=args.toml,
            output_log=args.output_log,
            executable=args.executable,
            secret_inputs=args.secret_input,
            public_inputs=args.public_input,
            replay_executable=args.replay_executable,
            reproduce=args.reproduce,
            reproduce_module=args.reproduce_module,
            reproduce_timeout=args.reproduce_timeout,
            output_path=args.out,
            code_path=args.code_path,
            library=args.library,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
