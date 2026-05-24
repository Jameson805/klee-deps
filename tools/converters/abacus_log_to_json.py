#!/usr/bin/env python3
"""Convert one ABACUS worker log into the shared JSON result schema.

This converter stays benchmark-agnostic at the schema layer, but it requires
explicit runner metadata so ABACUS secret layouts and reference seeds come from
the benchmark-owned runner config instead of filename heuristics.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from typing import Any

from tools.shared.result_schema import (
    KIND_BRANCH,
    KIND_MEMORY,
    STATUS_NOT_REPRODUCED,
    build_payload,
    get_source_line,
    make_result_row,
)
from tools.shared.runtime_limits import configure_int_max_str_digits


configure_int_max_str_digits()


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_INSTRUCTION_KIND_CACHE: dict[tuple[str, int], str] = {}


def _classify_instruction_text(text: str) -> str | None:
    # ABACUS logs report only the divergent instruction address, not whether the
    # underlying side channel was control-flow- or memory-driven. We therefore
    # classify the instruction text itself and fail loudly when that heuristic is
    # too ambiguous to support the canonical `kind` field.
    stripped = text.strip()
    if not stripped:
        return None

    parts = stripped.split(None, 1)
    mnemonic = parts[0].lower()
    operands = parts[1] if len(parts) == 2 else ""

    if mnemonic.startswith("j") or mnemonic in {"call", "callq", "jmp", "jmpq", "ret", "retq", "loop", "loope", "loopne"}:
        return KIND_BRANCH
    if mnemonic in {"lea", "leaq", "nop", "nopl", "nopw", "endbr32", "endbr64"}:
        return None
    if "(" in operands or "[" in operands:
        return KIND_MEMORY
    return None


def _instruction_text_for_address(executable_path: str, address: int) -> str:
    objdump = shutil.which("objdump")
    if objdump is None:
        raise RuntimeError("objdump is required to classify ABACUS findings")

    command = [
        objdump,
        "-d",
        f"--start-address=0x{address:x}",
        f"--stop-address=0x{address + 16:x}",
        executable_path,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"objdump failed for {executable_path} at 0x{address:x}: {result.stderr.strip()}"
        )

    for line in result.stdout.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]+):\s*(.*)$", line)
        if not match:
            continue
        if int(match.group(1), 16) != address:
            continue
        fields = line.split("\t")
        if len(fields) >= 3:
            return fields[-1].strip()
        return match.group(2).strip()

    raise RuntimeError(f"objdump did not return an instruction for 0x{address:x} in {executable_path}")


def _instruction_kind_for_address(executable_path: str, address: int) -> str:
    cache_key = (os.path.abspath(executable_path), address)
    cached_kind = _INSTRUCTION_KIND_CACHE.get(cache_key)
    if cached_kind is not None:
        return cached_kind

    # Keep the classification executable-local so repeated ABACUS locations do not
    # pay another objdump call during one conversion run.
    instruction_text = _instruction_text_for_address(cache_key[0], address)
    kind = _classify_instruction_text(instruction_text)
    if kind is None:
        raise RuntimeError(
            f"could not classify instruction at 0x{address:x} in {cache_key[0]} as branch or memory: {instruction_text}"
        )
    _INSTRUCTION_KIND_CACHE[cache_key] = kind
    return kind


def load_runner_config(config_path: str) -> dict[str, Any]:
    try:
        with open(config_path, "rb") as handle:
            config = tomllib.load(handle)
    except OSError as exc:
        raise ValueError(f"failed to load runner config {config_path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"failed to parse runner config {config_path}: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError(f"runner config {config_path} root must be a table")

    return config


def _resolve_input_size(size_spec: Any, macros: dict[str, Any]) -> int:
    if isinstance(size_spec, int):
        if size_spec <= 0:
            raise ValueError(f"input size must be positive (got {size_spec})")
        return size_spec

    if isinstance(size_spec, str):
        value = macros.get(size_spec)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"macro {size_spec!r} is missing or not a positive integer")
        return value

    raise ValueError(f"unsupported input size specification: {size_spec!r}")


def _value_to_bytes(value: Any, size: int) -> list[int]:
    if isinstance(value, int):
        try:
            return list(int(value).to_bytes(size, byteorder="big", signed=False))
        except OverflowError as exc:
            raise ValueError(f"integer seed does not fit in {size} bytes") from exc

    if isinstance(value, list):
        if len(value) != size:
            raise ValueError(f"byte-seed length {len(value)} does not match expected size {size}")
        out: list[int] = []
        for byte_value in value:
            if not isinstance(byte_value, int) or byte_value < 0 or byte_value > 0xFF:
                raise ValueError("ABACUS reference secret bytes must be integers in [0, 255]")
            out.append(byte_value)
        return out

    raise ValueError(f"unsupported ABACUS seed format: {value!r}")


def _bytes_to_int(values: list[int]) -> int:
    result = 0
    for value in values:
        result = (result << 8) | value
    return result


def _load_abacus_secret_layout(runner_config_path: str, preset_name: str) -> list[dict[str, Any]]:
    """Load ABACUS secret ordering, widths, and reference seeds from one preset."""
    try:
        runner_config = load_runner_config(runner_config_path)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    inputs = runner_config.get("inputs")
    mode_policy = runner_config.get("mode_policy")
    presets = runner_config.get("presets")
    if not isinstance(inputs, list) or not isinstance(mode_policy, dict) or not isinstance(presets, dict):
        raise ValueError("runner config is missing inputs/mode_policy/presets")

    preset = presets.get(preset_name)
    if not isinstance(preset, dict):
        raise ValueError(f"unknown preset {preset_name!r}")

    macros = preset.get("macros", {})
    abacus_secrets = preset.get("abacus_secrets", {})
    abacus_policy = mode_policy.get("abacus", {})
    secret_ids = abacus_policy.get("secret_inputs")
    if not isinstance(macros, dict) or not isinstance(abacus_secrets, dict) or not isinstance(secret_ids, list):
        raise ValueError("runner config abacus policy is incomplete")

    input_by_id = {}
    for entry in inputs:
        if not isinstance(entry, dict):
            continue
        input_id = entry.get("id")
        if isinstance(input_id, str):
            input_by_id[input_id] = entry

    layout: list[dict[str, Any]] = []
    for input_id in secret_ids:
        if input_id not in input_by_id:
            raise ValueError(f"abacus secret input {input_id!r} is missing from inputs")
        entry = input_by_id[input_id]
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"abacus secret input {input_id!r} is missing a replay name")
        if input_id not in abacus_secrets:
            raise ValueError(f"preset {preset_name!r} is missing abacus seed for {input_id!r}")
        size = _resolve_input_size(entry.get("size"), macros)
        seed_bytes = _value_to_bytes(abacus_secrets[input_id], size)
        layout.append(
            {
                "id": input_id,
                "name": name,
                "size": size,
                "seed_bytes": seed_bytes,
                "seed_value": _bytes_to_int(seed_bytes),
            }
        )

    return layout


def _build_counterexamples(secret_layout: list[dict[str, Any]], divergent_bytes: list[int]) -> dict[str, int]:
    total_size = sum(int(entry["size"]) for entry in secret_layout)
    if len(divergent_bytes) != total_size:
        raise ValueError(
            f"divergent input length {len(divergent_bytes)} does not match configured secret length {total_size}"
        )

    counterexamples: dict[str, int] = {}
    offset = 0
    for entry in secret_layout:
        size = int(entry["size"])
        name = str(entry["name"])
        counterexamples[name] = int(entry["seed_value"])
        counterexamples[f"{name}__prime"] = _bytes_to_int(divergent_bytes[offset:offset + size])
        offset += size

    return counterexamples


def convert_abacus_log(
    *,
    log_path: str,
    executable_path: str,
    output_path: str | None = None,
    runner_config: str | None = None,
    preset_name: str | None = None,
    code_root: str | None = None,
    library: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one ABACUS log using explicit runner metadata for secret layout recovery."""
    if not os.path.isfile(log_path):
        raise FileNotFoundError(f"log not found: {log_path}")

    if not runner_config:
        raise ValueError("runner_config is required")
    if not preset_name:
        raise ValueError("preset_name is required")

    runner_config_path = os.path.abspath(runner_config)
    secret_layout = _load_abacus_secret_layout(runner_config_path, preset_name)

    with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()

    divergent: dict[int, list[int]] = {}
    locations: dict[int, dict[str, Any]] = {}
    se_time: float | None = None
    qif_time: float | None = None
    code_root_abs = os.path.abspath(code_root) if code_root else None

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
            bvals: list[int] = []
            i += 1
            while i < len(lines):
                t = lines[i].rstrip("\n")
                km = re.match(r"^\s*Key(\d+)\s*=\s*([0-9]+)\s*$", t)
                if not km:
                    break
                bvals.append(int(km.group(2)))
                i += 1
            if bvals and all(0 <= value <= 255 for value in bvals):
                divergent[addr] = bvals
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
                    if code_root_abs:
                        try:
                            src_abs = os.path.abspath(src_path)
                            if os.path.commonpath([code_root_abs, src_abs]) == code_root_abs:
                                filename = os.path.relpath(src_abs, code_root_abs)
                        except Exception:
                            pass

                    entry: dict[str, Any] = {
                        "filename": filename,
                        "line": line_no,
                    }

                    if code_root_abs:
                        source_line = get_source_line(library, os.path.join(code_root_abs, filename), line_no)
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

    rows: list[dict[str, Any]] = []
    non_ct_time = (se_time + qif_time) if se_time is not None and qif_time is not None else None
    for addr in sorted(set(divergent.keys()) | set(locations.keys())):
        row: dict[str, Any] = {
            "filename": None,
            "line": None,
            "counterexamples": None,
            # ABACUS kind is inferred from the divergent instruction because the raw
            # log format does not carry an explicit branch-vs-memory label.
            "kind": _instruction_kind_for_address(executable_path, addr),
        }
        if non_ct_time is not None:
            row["non_ct_time"] = non_ct_time
        if addr in locations:
            row.update(locations[addr])
        if addr in divergent:
            row["counterexamples"] = _build_counterexamples(secret_layout, divergent[addr])
        rows.append(row)

    validated_rows: list[dict[str, Any]] = []
    for row in rows:
        optional = {
            key: value
            for key, value in row.items()
            if key not in {"filename", "line", "non_ct_time", "counterexamples", "reproduced_status", "library"}
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
            "kind": "object",
            "column": "Int64",
            "code": "object",
        },
        metadata=metadata,
    )
    payload["notes"] = {
        "runner_config": runner_config_path,
        "preset": preset_name,
        "secret_layout": [
            {
                "name": entry["name"],
                "size": entry["size"],
            }
            for entry in secret_layout
        ],
        "public_layout": [],
        "abacus_reference_secrets": {
            entry["name"]: entry["seed_value"]
            for entry in secret_layout
        },
    }

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")

    return payload


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Parse an Abacus per-case log and emit combined JSON with source location, code line, "
            "and (A,B) counterexamples. Optional replay-based reproduction is supported."
        )
    )
    p.add_argument("--log", required=True, help="Path to Abacus per-case log")
    p.add_argument("--executable", required=True, help="Path to the analyzed executable")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument(
        "--sym-size",
        type=int,
        default=4,
        help="Symbol byte size passed to reproduce_positives.py when --reproduce is enabled (default: 4)",
    )
    p.add_argument(
        "--runner-config",
        required=True,
        help="Runner config path used to recover ABACUS secret layouts and reference seeds",
    )
    p.add_argument(
        "--preset-name",
        required=True,
        help="Preset name inside --runner-config used to recover ABACUS secret layouts and reference seeds",
    )
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
        default=1200,
        help="Timeout seconds for each reproduction attempt (default: 1200)",
    )
    p.add_argument(
        "--reproduce-debug",
        action="store_true",
        help="Forward --debug to reproduce_positives.py and print the exact replay command on failure.",
    )
    p.add_argument(
        "--pin-root",
        default=None,
        help="Path to the external Intel Pin kit (defaults to PIN_ROOT)",
    )
    p.add_argument(
        "--library",
        required=True,
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "unknown"],
        help="Library identifier for this dataset.",
    )
    args = p.parse_args(argv)

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

    try:
        convert_abacus_log(
            log_path=args.log,
            executable_path=args.executable,
            output_path=args.out,
            runner_config=args.runner_config,
            preset_name=args.preset_name,
            code_root=args.code_root,
            library=args.library,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

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
        if args.pin_root:
            cmd += ["--pin-root", str(args.pin_root)]
        proc = subprocess.run(cmd, check=False, cwd=_REPO_ROOT)
        if proc.returncode != 0:
            print(f"[reproduce] batch reproduction failed with rc={proc.returncode}", file=sys.stderr)
            return proc.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
