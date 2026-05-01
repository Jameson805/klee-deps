"""Small shared utilities for experiment runners.

This module intentionally stays narrow: it owns only generic path, TOML, and
logging helpers that are reused by multiple runners. Tool-specific config
parsing stays in the runner that executes it so the orchestration code remains
easy to follow without chasing abstractions across files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import subprocess
from typing import TextIO


REPO_ROOT = Path(__file__).resolve().parents[2]
_DURATION_TOKEN_RE = re.compile(r"(?P<amount>\d+)(?P<unit>[hmsHMS])")


def resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def duration_to_seconds(value: str | int, location: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{location} must be a positive duration")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{location} must be a positive duration")
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{location} must be a non-empty duration string like '60', '1m', or '2h30m'"
        )

    text = value.strip().replace(" ", "")
    if text.isdigit():
        seconds = int(text)
        if seconds <= 0:
            raise ValueError(f"{location} must be a positive duration")
        return seconds

    multipliers = {"h": 3600, "m": 60, "s": 1}
    total_seconds = 0
    position = 0
    while position < len(text):
        match = _DURATION_TOKEN_RE.match(text, position)
        if match is None:
            raise ValueError(
                f"{location} must use h/m/s suffixes like '1m', '4h', or '2h30m'"
            )
        total_seconds += int(match.group("amount")) * multipliers[match.group("unit").lower()]
        position = match.end()

    if total_seconds <= 0:
        raise ValueError(f"{location} must be a positive duration")
    return total_seconds


def expect_table(value: object, location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a TOML table")
    return value


def expect_array(value: object, location: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{location} must be an array")
    return value


def expect_string(table: dict[str, object], key: str, location: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string")
    return value


def optional_string(table: dict[str, object], key: str, location: str) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{location}.{key} must be a non-empty string when present")
    return value


def optional_string_list(table: dict[str, object], key: str, location: str) -> tuple[str, ...]:
    value = table.get(key)
    if value is None:
        return ()
    values = expect_array(value, f"{location}.{key}")
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"{location}.{key} must contain only non-empty strings")
    return tuple(values)


@dataclass
class ExperimentContext:
    """Shared logging and subprocess helper for experiment runner scripts.

    The experiment entrypoints all need the same behavior: print progress to the
    terminal, optionally mirror that output into a shared `output.log`, and run
    subprocesses while streaming their combined stdout/stderr line by line.
    This class keeps that behavior consistent across the different runners.
    """

    output_handle: TextIO | None = None

    def log(self, message: str = "") -> None:
        """Write a message to stdout and mirror it to the shared output log."""
        print(message)
        if self.output_handle is not None:
            self.output_handle.write(f"{message}\n")
            self.output_handle.flush()

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> int:
        """Run a command and stream its merged output to the active log sinks.

        Returns the process exit code. When `check` is true, a non-zero exit
        code terminates the current runner via `SystemExit`.
        """
        self.log(f"$ {shlex.join(command)}")
        process = subprocess.Popen(
            command,
            cwd=cwd or REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            rendered = line.rstrip("\n")
            print(rendered)
            if self.output_handle is not None:
                self.output_handle.write(f"{rendered}\n")
                self.output_handle.flush()
        return_code = process.wait()
        if check and return_code != 0:
            raise SystemExit(return_code)
        return return_code

    def run_and_capture(
        self,
        command: list[str],
        *,
        log_path: Path,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        prefix: str | None = None,
    ) -> int:
        """Run a command like `run`, and also save raw output to `log_path`.

        `prefix` is applied only to the mirrored terminal/shared-log output; the
        per-command log file keeps the original subprocess output unchanged.
        """
        self.log(f"$ {shlex.join(command)}")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as handle:
            process = subprocess.Popen(
                command,
                cwd=cwd or REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                rendered = line.rstrip("\n")
                if prefix:
                    rendered = f"{prefix}{rendered}"
                print(rendered)
                if self.output_handle is not None:
                    self.output_handle.write(f"{rendered}\n")
                    self.output_handle.flush()
                handle.write(line)
                handle.flush()
            return_code = process.wait()

        if check and return_code != 0:
            raise SystemExit(return_code)
        return return_code