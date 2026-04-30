from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Mapping, Optional

STATUS_SUCCESS = "success"
STATUS_TIMEOUT = "timeout"
STATUS_IDENTICAL_TRACE = "identical_trace"
STATUS_LOCATION_MISMATCH = "location_mismatch"
STATUS_NOT_REPRODUCED = "not_reproduced"

REPRODUCED_STATUSES = {
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_IDENTICAL_TRACE,
    STATUS_LOCATION_MISMATCH,
    STATUS_NOT_REPRODUCED,
}

MANDATORY_FIELDS = (
    "filename",
    "line",
    "non_ct_time",
    "counterexamples",
    "reproduced_status",
    "library",
)

MANDATORY_DTYPES: Dict[str, str] = {
    "filename": "object",
    "line": "Int64",
    "non_ct_time": "float64",
    "counterexamples": "object",
    "reproduced_status": "object",
    "library": "object",
}

PREFERRED_COLUMN_ORDER = [
    "library",
    "filename",
    "line",
    "column",
    "inst_id",
    "visit_count",
    "non_ct_count",
    "visit_time",
    "non_ct_time",
    "reproduced_status",
    "counterexamples",
    "code",
    "in_ctchecker",
]

_SOURCE_LINE_CACHE: Dict[tuple[str, int], Optional[str]] = {}


def format_location(file: Optional[str], line: Optional[int], col: Optional[int]) -> str:
    if not file or line is None or col is None:
        return "<unknown>"
    return f"{file}:{line}:{col}"


def _library_root(library: str) -> Optional[str]:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    mapping = {
        "mbedtls": os.path.join(repo_root, "benchmarks", "mbedtls-3.2.1"),
        "libgcrypt": os.path.join(repo_root, "benchmarks", "libgcrypt-and-libgpg-error"),
        "openssl": os.path.join(repo_root, "benchmarks", "openssl-1.1.1q"),
        "bearssl": os.path.join(repo_root, "benchmarks", "bearssl-0.6"),
    }
    root = mapping.get(library)
    return root if root and os.path.isdir(root) else None


def get_source_line(library: str, filename: str, line: int) -> Optional[str]:
    if not isinstance(filename, str) or not filename or not isinstance(line, int) or line <= 0:
        return None

    candidates: List[str] = []
    if os.path.isabs(filename):
        candidates.append(filename)
    else:
        candidates.append(filename)
        root = _library_root(library)
        if root:
            candidates.append(os.path.join(root, filename))

    for path in candidates:
        if not os.path.isfile(path):
            continue
        key = (os.path.abspath(path), line)
        if key in _SOURCE_LINE_CACHE:
            return _SOURCE_LINE_CACHE[key]
        text: Optional[str] = None
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for idx, line_text in enumerate(f, start=1):
                    if idx == line:
                        text = line_text.rstrip("\n")
                        break
        except OSError:
            text = None
        _SOURCE_LINE_CACHE[key] = text
        return text

    return None


def make_result_row(
    *,
    filename: Any,
    line: Any,
    non_ct_time: Any,
    counterexamples: Any,
    reproduced_status: Any,
    library: Any,
    optional_fields: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(filename, str) or not filename:
        raise TypeError("filename must be a non-empty str")
    if not isinstance(line, int) or isinstance(line, bool):
        raise TypeError("line must be an int")
    if not isinstance(non_ct_time, float):
        raise TypeError("non_ct_time must be a float")
    if not isinstance(counterexamples, dict):
        raise TypeError("counterexamples must be a dict")
    if any(not isinstance(k, str) for k in counterexamples.keys()):
        raise TypeError("counterexamples keys must all be str")
    if not isinstance(reproduced_status, str):
        raise TypeError("reproduced_status must be a str")
    normalized_status = reproduced_status.strip().lower()
    if normalized_status not in REPRODUCED_STATUSES:
        raise ValueError(
            f"reproduced_status must be one of {sorted(REPRODUCED_STATUSES)}"
        )
    if not isinstance(library, str):
        raise TypeError("library must be a str")
    normalized_library = library.strip()
    if not normalized_library:
        raise ValueError("library must be a non-empty str")

    row: Dict[str, Any] = {}
    row["filename"] = filename
    row["line"] = line
    row["non_ct_time"] = non_ct_time
    row["counterexamples"] = dict(counterexamples)
    row["reproduced_status"] = normalized_status
    row["library"] = normalized_library

    if optional_fields:
        for key, value in optional_fields.items():
            if key in MANDATORY_FIELDS:
                continue
            row[key] = value

    return row


def build_payload(
    rows: Iterable[Mapping[str, Any]],
    *,
    optional_dtypes: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    normalized = [dict(r) for r in rows]

    observed = set()
    for row in normalized:
        observed.update(row.keys())

    ordered: List[str] = [k for k in PREFERRED_COLUMN_ORDER if k in observed]
    extras = [k for k in observed if k not in ordered]
    ordered.extend(sorted(extras))

    optional_dtypes = dict(optional_dtypes or {})
    dtypes: Dict[str, str] = {}
    for key in ordered:
        if key in MANDATORY_DTYPES:
            dtypes[key] = MANDATORY_DTYPES[key]
            continue
        if key not in optional_dtypes:
            raise ValueError(
                f"Missing explicit dtype for optional field '{key}'. "
                "Pass optional_dtypes to build_payload()."
            )
        dtypes[key] = optional_dtypes[key]

    return {
        "columns": ordered,
        "data": normalized,
        "dtypes": dtypes,
    }
