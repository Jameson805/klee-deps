#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from tools.shared.result_schema import (
    STATUS_NOT_REPRODUCED,
    KIND_BRANCH,
    KIND_MEMORY,
    build_payload,
    get_source_line,
    make_result_row,
    normalize_result_kind,
)
from tools.shared.runtime_limits import configure_int_max_str_digits


configure_int_max_str_digits()


KLEE_OPTIONAL_DTYPES = {
    "kind": "object",
    "column": "Int64",
    "inst_id": "Int64",
    "visit_count": "Int64",
    "non_ct_count": "Int64",
    "visit_time": "float64",
    "code": "object",
}


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item and item.strip()]


def require_tools(tools: list[str]) -> None:
    missing = [tool for tool in tools if not shutil.which(tool)]
    if missing:
        raise RuntimeError(f"required tools not found on PATH: {', '.join(missing)}")


def _to_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def load_preaggregated_from_messages(messages_path: str, tag: str) -> list[dict[str, object]]:
    rows_by_inst_id: dict[int, dict[str, object]] = {}
    with open(messages_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(f"KLEE: [{tag}]"):
                continue
            start = line.find("{")
            if start == -1:
                continue
            try:
                payload = json.loads(line[start:])
            except json.JSONDecodeError:
                continue

            inst_id = _to_int(payload.get("inst_id"))
            if inst_id is None:
                continue
            if inst_id in rows_by_inst_id:
                continue

            rows_by_inst_id[inst_id] = {
                "filename": payload.get("filename"),
                "line": _to_int(payload.get("line")),
                "column": _to_int(payload.get("col")),
                "inst_id": inst_id,
                "visit_count": _to_int(payload.get("visit_count")),
                "non_ct_count": _to_int(payload.get("non_ct_count")),
                "visit_time": _to_float(payload.get("visit_time")),
                "non_ct_time": _to_float(payload.get("non_ct_time")),
            }

    return sorted(
        rows_by_inst_id.values(),
        key=lambda row: (
            str(row.get("filename") or ""),
            _to_int(row.get("line")) or -1,
            _to_int(row.get("column")) or -1,
            _to_int(row.get("inst_id")) or -1,
        ),
    )


def _split_parts(name: object) -> list[str] | None:
    if not isinstance(name, str):
        return None
    return [part for part in os.path.normpath(name).split(os.sep) if part not in ("", ".")]


def _find_subsequence(parts: list[str] | None, subsequence: list[str]) -> int:
    if parts is None or not subsequence:
        return -1
    if len(subsequence) > len(parts):
        return -1
    for index in range(len(parts) - len(subsequence) + 1):
        if parts[index:index + len(subsequence)] == subsequence:
            return index
    return -1


def _read_counterexample_value(path: str) -> int | None:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        print(f"[counterexamples] failed to read {path}: {error}", file=sys.stderr)
        return None
    if not data:
        return 0
    return int.from_bytes(data, byteorder="big", signed=False)


def _extract_var(ktest_file: str, variable: str) -> bool:
    try:
        subprocess.run(
            ["ktest-tool", "--extract", variable, ktest_file],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def extract_counterexamples(
    rows: list[dict[str, object]],
    klee_output: str,
    kind: str,
    secrets: list[str],
    publics: list[str],
) -> None:
    if not secrets and not publics:
        return

    require_tools(["ktest-tool"])
    for row in rows:
        non_ct_count = _to_int(row.get("non_ct_count")) or 0
        inst_id = _to_int(row.get("inst_id"))
        if non_ct_count <= 0 or inst_id is None:
            continue

        ktest_file = os.path.join(klee_output, f"{kind}_counterexample_{inst_id}.ktest")
        if not os.path.isfile(ktest_file):
            print(f"[counterexamples] missing ktest file: {ktest_file}", file=sys.stderr)
            continue

        counterexamples: dict[str, int] = {}
        for variable in publics:
            if _extract_var(ktest_file, variable):
                value = _read_counterexample_value(f"{ktest_file}.{variable}")
                if value is not None:
                    counterexamples[variable] = value

        for variable in secrets:
            if _extract_var(ktest_file, variable):
                value = _read_counterexample_value(f"{ktest_file}.{variable}")
                if value is not None:
                    counterexamples[variable] = value
            for prime_name in (f"{variable}__prime", f"{variable}_prime", f"{variable}_2"):
                if _extract_var(ktest_file, prime_name):
                    prime_value = _read_counterexample_value(f"{ktest_file}.{prime_name}")
                    if prime_value is not None:
                        counterexamples[prime_name] = prime_value
                    break

        if counterexamples:
            row["counterexamples"] = counterexamples


def build_klee_payload(rows: list[dict[str, object]]) -> dict[str, object]:
    return build_payload(rows, optional_dtypes=KLEE_OPTIONAL_DTYPES)


def convert_klee_output(
    *,
    kind: str,
    klee_output: str,
    output_path: str | None = None,
    code_path: str | None = None,
    filename: str = "",
    lines: str = "",
    src_prefix: str = "",
    secret: str = "",
    public: str = "",
    library: str,
) -> dict[str, object]:
    kind = normalize_result_kind(kind)

    messages_path = os.path.join(klee_output, "messages.txt")
    if not os.path.isfile(messages_path):
        raise FileNotFoundError(f"messages.txt not found under {klee_output}")

    rows = load_preaggregated_from_messages(messages_path, kind.upper())

    if src_prefix:
        prefix_parts = [part for part in os.path.normpath(src_prefix).split(os.sep) if part not in ("", ".")]
        filtered_rows: list[dict[str, object]] = []
        for row in rows:
            parts = _split_parts(row.get("filename"))
            index = _find_subsequence(parts, prefix_parts)
            if index == -1:
                continue
            rest = (parts or [])[index + len(prefix_parts):]
            row = dict(row)
            row["filename"] = os.path.join(*rest) if rest else ""
            filtered_rows.append(row)
        rows = filtered_rows

    if filename:
        rows = [row for row in rows if row.get("filename") == filename]

    if lines:
        bounds = lines.split(":", 1)
        if len(bounds) != 2:
            raise ValueError("lines must be in the format start:end")
        start = int(bounds[0])
        end = int(bounds[1])
        rows = [
            row for row in rows
            if isinstance(row.get("line"), int) and start <= int(row["line"]) <= end
        ]

    code_root = os.path.abspath(code_path) if code_path else None
    if code_root:
        for row in rows:
            file_value = row.get("filename")
            line_value = row.get("line")
            if isinstance(file_value, str) and isinstance(line_value, int) and line_value > 0:
                source_line = get_source_line(library, os.path.join(code_root, file_value), line_value)
                if source_line is not None:
                    row["code"] = source_line

    extract_counterexamples(rows, klee_output, kind, parse_list(secret), parse_list(public))

    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        row_filename = row.get("filename")
        row_line = row.get("line")
        if not isinstance(row_filename, str) or not row_filename:
            continue
        if not isinstance(row_line, int):
            continue

        optional = {
            key: value
            for key, value in row.items()
            if key not in {"filename", "line", "non_ct_time", "counterexamples", "reproduced_status", "library"}
        }
        optional["kind"] = kind
        if "non_ct_count" not in optional:
            optional["non_ct_count"] = 0
        if "visit_count" not in optional and row.get("visit_count") is not None:
            optional["visit_count"] = row.get("visit_count")

        non_ct_time = _to_float(row.get("non_ct_time"))
        normalized_rows.append(
            make_result_row(
                filename=row_filename,
                line=row_line,
                non_ct_time=non_ct_time if non_ct_time is not None else float("nan"),
                counterexamples=row.get("counterexamples") if isinstance(row.get("counterexamples"), dict) else {},
                reproduced_status=row.get("reproduced_status") or STATUS_NOT_REPRODUCED,
                library=row.get("library") if isinstance(row.get("library"), str) and row.get("library") else library,
                optional_fields=optional,
            )
        )

    payload = build_klee_payload(normalized_rows)

    if output_path:
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")

    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Convert aggregated KLEE messages.txt output into the shared combined JSON format.",
    )
    parser.add_argument("kind", choices=[KIND_BRANCH, KIND_MEMORY])
    parser.add_argument("klee_output", help="Path to the KLEE output directory")
    parser.add_argument("output_path", help="Output JSON path")
    parser.add_argument("--code-path", default="", help="Path to the source code root for the filenames in the KLEE output")
    parser.add_argument("--filename", default="", help="Filename to filter (for example: main.c)")
    parser.add_argument("--lines", default="", help="Line number range to filter (for example: 100:200)")
    parser.add_argument(
        "--src-prefix",
        default="",
        help="If set, keep only KLEE rows whose filename contains this prefix and strip it from the filename.",
    )
    parser.add_argument("--secret", default="", help="Comma-separated list of secret variable names")
    parser.add_argument("--public", default="", help="Comma-separated list of public variable names")
    parser.add_argument(
        "--library",
        required=True,
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "unknown"],
        help="Library identifier for this dataset.",
    )
    args = parser.parse_args(argv)

    try:
        convert_klee_output(
            kind=args.kind,
            klee_output=args.klee_output,
            output_path=args.output_path,
            code_path=args.code_path,
            filename=args.filename,
            lines=args.lines,
            src_prefix=args.src_prefix,
            secret=args.secret,
            public=args.public,
            library=args.library,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
