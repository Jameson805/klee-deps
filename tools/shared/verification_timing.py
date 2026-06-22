"""Helpers for recording per-case bounded-verification runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


TIMING_DIR_NAME = "_timings"


def verification_status(
    *,
    exit_code: int,
    elapsed_seconds: float,
    timeout_seconds: int,
    timed_out_exit_codes: set[int] | None = None,
) -> str:
    """Classify one backend invocation for timing reports."""
    if timed_out_exit_codes and exit_code in timed_out_exit_codes:
        return "timeout"
    if elapsed_seconds >= float(timeout_seconds):
        return "timeout"
    if exit_code == 0:
        return "completed"
    return "failed"


def write_verification_timing(
    results_dir: str | Path,
    *,
    case_id: str,
    title: str,
    metadata: Mapping[str, Any],
    timeout_seconds: int,
    elapsed_seconds: float,
    exit_code: int,
    status: str,
) -> Path:
    """Write one per-case timing payload under the runner result directory."""
    timing_dir = Path(results_dir) / TIMING_DIR_NAME
    timing_dir.mkdir(parents=True, exist_ok=True)
    output_path = timing_dir / f"{case_id}.json"
    effective_seconds = float(timeout_seconds) if status == "timeout" else float(elapsed_seconds)
    library = metadata.get("library")
    target = metadata.get("target")
    config = metadata.get("config")
    if not isinstance(library, str) or not library:
        raise ValueError("timing metadata must define non-empty library")
    if not isinstance(target, str) or not target:
        raise ValueError("timing metadata must define non-empty target")
    if not isinstance(config, str) or not config:
        raise ValueError("timing metadata must define non-empty config")
    payload = {
        "data": [
            {
                "case_id": case_id,
                "title": title,
                "library": library,
                "target": target,
                "config": config,
                "timeout_seconds": int(timeout_seconds),
                "elapsed_seconds": float(elapsed_seconds),
                "verification_time_seconds": effective_seconds,
                "status": status,
                "exit_code": int(exit_code),
            }
        ],
        "metadata": dict(metadata),
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path