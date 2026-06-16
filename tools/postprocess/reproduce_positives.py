#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from tools.shared.tool_artifacts import resolve_intel_pin_root
from tools.shared.result_schema import (
    KIND_BRANCH,
    KIND_MEMORY,
    format_location,
    STATUS_IDENTICAL_TRACE,
    STATUS_LOCATION_MISMATCH,
    STATUS_KIND_MISMATCH,
    STATUS_NOT_REPRODUCED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    normalize_result_kind,
)

try:
    from tools.utilities.addrinfo import get_addr_info, get_addr_info_context  # type: ignore
except Exception as exc:  # pragma: no cover
    get_addr_info = None  # type: ignore
    get_addr_info_context = None  # type: ignore
    _ADDRINFO_IMPORT_ERROR = str(exc)
else:
    _ADDRINFO_IMPORT_ERROR = None


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PIN_TOOL_DIR = os.path.join(REPO_ROOT, "pin-tracer")
PIN_TOOL_NAME = "replay_trace"
PRIME_SUFFIXES = ("__prime", "_prime")
TRACE_LOOKBACK = 64

_ADDRINFO_WARNING_EMITTED = False
_PIN_RUNTIME_CACHE: dict[tuple[str, str], "PinRuntime"] = {}

type SourceLocation = tuple[str, int, int]
type ColumnBounds = tuple[int | None, int | None]


@dataclass(frozen=True)
class ExecutableArch:
    target: str
    pin_binary_name: str
    personality: str


@dataclass(frozen=True)
class PinRuntime:
    pin_root: str
    target: str
    pin_binary: str
    personality: str
    tool_path: str


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    ip: int
    address: int | None = None


@dataclass(frozen=True)
class Divergence:
    index: int
    event_a: TraceEvent | None
    event_b: TraceEvent | None
    culprit_ip: int | None
    recent_ips: tuple[int, ...]


@dataclass(frozen=True)
class ReplayResult:
    culprit_ip: int | None
    resolved_ip: int | None
    location: SourceLocation | None
    divergence_kind: str
    column_bounds: ColumnBounds | None = None


@dataclass(frozen=True)
class LocationMatchResult:
    matches: bool
    snapped: bool = False
    same_expression: bool = False
    same_line_different_column: bool = False


def _statement_bounds(lines: Sequence[str], line_number: int) -> tuple[int, int] | None:
    if line_number <= 0 or line_number > len(lines):
        return None

    start = line_number
    while start > 1:
        previous = lines[start - 2].strip()
        if not previous:
            break
        if previous.endswith((";", "{", "}")):
            break
        start -= 1

    end = line_number
    while end < len(lines):
        current = lines[end - 1].strip()
        if not current:
            break
        if current.endswith((";", "{", "}")):
            break
        end += 1

    if start == end:
        return None
    return start, end


def _same_expression_match(actual_file: str, expected_line: int, actual_line: int) -> bool:
    if expected_line <= 0 or actual_line <= 0 or expected_line == actual_line:
        return False

    try:
        with open(actual_file, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return False

    actual_bounds = _statement_bounds(lines, actual_line)
    if actual_bounds is None:
        return False
    return actual_bounds[0] <= expected_line <= actual_bounds[1]


def parse_list(spec: str) -> list[str]:
    return [part.strip() for part in spec.split(",") if part and part.strip()]


def _parse_input_value_int(raw_value: str, entry: str, value_name: str) -> int:
    text = raw_value.strip()
    try:
        return int(text, 0)
    except ValueError as exc:
        set_digit_limit = getattr(sys, "set_int_max_str_digits", None)
        if set_digit_limit is not None and "Exceeds the limit" in str(exc):
            set_digit_limit(0)
            try:
                return int(text, 0)
            except ValueError:
                pass
        raise ValueError(f"Invalid {value_name} value in specification '{entry}'") from exc


def require_tools(tools: Sequence[str]) -> None:
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        print(
            f"Error: required tools not found on PATH: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(2)


def coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def shell_join(argv: Sequence[str]) -> str:
    return shlex.join(list(argv))


def tail_text(text: str, n: int = 30) -> str:
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])


def warn_addrinfo_unavailable() -> None:
    global _ADDRINFO_WARNING_EMITTED
    if get_addr_info is not None or _ADDRINFO_WARNING_EMITTED:
        return
    message = "Warning: DWARF address lookup is unavailable."
    if _ADDRINFO_IMPORT_ERROR:
        message += f" Import error: {_ADDRINFO_IMPORT_ERROR}"
    print(message, file=sys.stderr)
    _ADDRINFO_WARNING_EMITTED = True


def resolve_pin_root() -> str:
    resolved = os.path.abspath(str(resolve_intel_pin_root()))
    if not os.path.isdir(resolved):
        raise RuntimeError(f"Intel Pin root does not exist: {resolved}")
    return resolved


def inspect_executable_arch(executable: str) -> ExecutableArch:
    with open(executable, "rb") as stream:
        header = stream.read(20)

    if len(header) < 20 or header[:4] != b"\x7fELF":
        raise RuntimeError(f"Replay executable is not an ELF file: {executable}")

    elf_class = header[4]
    data_encoding = header[5]
    if data_encoding == 1:
        machine = struct.unpack("<H", header[18:20])[0]
    elif data_encoding == 2:
        machine = struct.unpack(">H", header[18:20])[0]
    else:
        raise RuntimeError(f"Unsupported ELF data encoding in: {executable}")

    if elf_class == 1:
        if machine != 3:
            raise RuntimeError(f"Unsupported 32-bit replay executable machine {machine} in: {executable}")
        return ExecutableArch(target="ia32", pin_binary_name="pin32", personality="linux32")

    if elf_class == 2:
        if machine != 62:
            raise RuntimeError(f"Unsupported 64-bit replay executable machine {machine} in: {executable}")
        return ExecutableArch(target="intel64", pin_binary_name="pin", personality="linux64")

    raise RuntimeError(f"Unsupported ELF class {elf_class} in: {executable}")


def ensure_pin_runtime(executable: str, pin_root: str) -> PinRuntime:
    arch = inspect_executable_arch(executable)
    cache_key = (pin_root, arch.target)
    cached = _PIN_RUNTIME_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if not os.path.isdir(PIN_TOOL_DIR):
        raise RuntimeError(f"Pin tracer directory is missing: {PIN_TOOL_DIR}")

    pin_binary = os.path.join(pin_root, arch.pin_binary_name)
    if not os.path.isfile(pin_binary):
        raise RuntimeError(f"Required Pin launcher not found: {pin_binary}")

    tool_path = os.path.join(PIN_TOOL_DIR, f"obj-{arch.target}", f"{PIN_TOOL_NAME}.so")
    if not os.path.isfile(tool_path):
        require_tools(["make"])
        cmd = [
            "make",
            "-C",
            PIN_TOOL_DIR,
            f"PIN_ROOT={pin_root}",
            f"TARGET={arch.target}",
            "tools",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not os.path.isfile(tool_path):
            details = [
                f"Failed to build the Pin tracer for target {arch.target}.",
                f"Command: {shell_join(cmd)}",
            ]
            if proc.stdout:
                details.append(f"stdout:\n{tail_text(proc.stdout)}")
            if proc.stderr:
                details.append(f"stderr:\n{tail_text(proc.stderr)}")
            raise RuntimeError("\n".join(details))

    runtime = PinRuntime(
        pin_root=pin_root,
        target=arch.target,
        pin_binary=pin_binary,
        personality=arch.personality,
        tool_path=tool_path,
    )
    _PIN_RUNTIME_CACHE[cache_key] = runtime
    return runtime


def run_pin_trace(
    executable: str,
    arg_files: Sequence[str],
    timeout: int,
    pin_root: str,
    trace_path: str,
    debug: bool,
) -> None:
    runtime = ensure_pin_runtime(executable, pin_root)
    require_tools(["setarch"])

    setarch_path = shutil.which("setarch")
    assert setarch_path is not None
    cmd = [
        setarch_path,
        runtime.personality,
        "-R",
        runtime.pin_binary,
        "-t",
        runtime.tool_path,
        "-o",
        trace_path,
        "--",
        executable,
    ] + list(arg_files)

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if debug:
            print(f"[debug] timed out running: {shell_join(cmd)}", file=sys.stderr)
        raise

    trace_ready = os.path.isfile(trace_path) and os.path.getsize(trace_path) > 0

    if proc.returncode != 0:
        # The replay executable returns the benchmark result directly, so non-zero
        # exits can still be valid as long as Pin emitted a usable trace.
        if trace_ready:
            if debug:
                print(
                    f"[debug] replay exited with status {proc.returncode} but produced trace: {trace_path}",
                    file=sys.stderr,
                )
                print(f"[debug] Pin command: {shell_join(cmd)}", file=sys.stderr)
                if proc.stdout:
                    print("=== pin stdout ===", file=sys.stderr)
                    print(proc.stdout, file=sys.stderr, end="")
                if proc.stderr:
                    print("=== pin stderr ===", file=sys.stderr)
                    print(proc.stderr, file=sys.stderr, end="")
            return

        print(f"Pin exited with status {proc.returncode} running: {shell_join(cmd)}", file=sys.stderr)
        if debug:
            print(f"[debug] Pin command: {shell_join(cmd)}", file=sys.stderr)
        if proc.stdout:
            print("=== pin stdout ===", file=sys.stderr)
            print(proc.stdout, file=sys.stderr, end="")
        if proc.stderr:
            print("=== pin stderr ===", file=sys.stderr)
            print(proc.stderr, file=sys.stderr, end="")
        raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)

    if not trace_ready:
        if debug:
            print(f"[debug] Pin command: {shell_join(cmd)}", file=sys.stderr)
        raise RuntimeError("Pin produced an empty trace; check the workspace Pin install, the replay executable, and the tracer build")


def parse_trace_line(raw_line: str) -> TraceEvent:
    parts = raw_line.strip().split()
    if len(parts) == 2 and parts[0] == "I":
        return TraceEvent(kind="I", ip=int(parts[1], 0))
    if len(parts) == 3 and parts[0] in {"R", "W"}:
        return TraceEvent(kind=parts[0], ip=int(parts[1], 0), address=int(parts[2], 0))
    raise RuntimeError(f"Unrecognized Pin trace line: {raw_line.rstrip()}")


def compare_trace_files(trace_a_path: str, trace_b_path: str) -> Divergence | None:
    recent_ips: deque[int] = deque(maxlen=TRACE_LOOKBACK)

    with open(trace_a_path, "r", encoding="utf-8", errors="replace", buffering=1024 * 1024) as trace_a:
        with open(trace_b_path, "r", encoding="utf-8", errors="replace", buffering=1024 * 1024) as trace_b:
            index = 0
            while True:
                raw_a = trace_a.readline()
                raw_b = trace_b.readline()

                if not raw_a and not raw_b:
                    return None

                if raw_a == raw_b:
                    if raw_a:
                        event = parse_trace_line(raw_a)
                        recent_ips.append(event.ip)
                    index += 1
                    continue

                event_a = parse_trace_line(raw_a) if raw_a else None
                event_b = parse_trace_line(raw_b) if raw_b else None
                last_common_ip = recent_ips[-1] if recent_ips else None
                culprit_ip = last_common_ip
                if event_a is not None and event_b is not None:
                    # For control-flow divergence, report the last shared instruction,
                    # not the first instruction already inside the two different paths.
                    if not (event_a.kind == "I" and event_b.kind == "I" and event_a.ip != event_b.ip):
                        culprit_ip = event_a.ip
                elif event_a is not None:
                    culprit_ip = event_a.ip if event_a.kind != "I" or last_common_ip is None else last_common_ip
                elif event_b is not None:
                    culprit_ip = event_b.ip if event_b.kind != "I" or last_common_ip is None else last_common_ip

                return Divergence(
                    index=index,
                    event_a=event_a,
                    event_b=event_b,
                    culprit_ip=culprit_ip,
                    recent_ips=tuple(recent_ips),
                )


def classify_divergence(divergence: Divergence) -> str:
    event_a = divergence.event_a
    event_b = divergence.event_b

    if event_a is None or event_b is None:
        return KIND_BRANCH

    if event_a.ip != event_b.ip:
        return KIND_BRANCH

    memory_kinds = {"R", "W"}
    if event_a.kind in memory_kinds and event_b.kind in memory_kinds:
        return KIND_MEMORY

    return KIND_BRANCH


def resolve_divergence_location(
    executable: str,
    divergence: Divergence,
) -> tuple[int | None, SourceLocation | None, ColumnBounds | None]:
    if get_addr_info_context is None:
        return divergence.culprit_ip, None, None

    candidates: list[int] = []
    if divergence.culprit_ip is not None:
        candidates.append(divergence.culprit_ip)
    for ip in reversed(divergence.recent_ips):
        if ip not in candidates:
            candidates.append(ip)

    for ip in candidates:
        info = get_addr_info_context(executable, ip)
        if info is not None:
            file_name, line_no, col_no, previous_column, next_column = info
            return ip, (file_name, line_no, col_no), (previous_column, next_column)

    return divergence.culprit_ip, None, None


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as stream:
        return stream.read()


def write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as stream:
        stream.write(data)


def write_int_file(path: str, value: int, size: int) -> None:
    with open(path, "wb") as stream:
        stream.write(int(value).to_bytes(size, byteorder="big", signed=False))


def analyze_input_bytes(
    executable: str,
    secret_names: Sequence[str],
    public_names: Sequence[str],
    secret_orig: dict[str, bytes],
    secret_prime: dict[str, bytes],
    public_values: dict[str, bytes],
    timeout: int,
    pin_root: str,
    debug: bool,
) -> ReplayResult | None:
    executable_path = os.path.abspath(executable)

    with tempfile.TemporaryDirectory() as tmpdir:
        run_a_dir = os.path.join(tmpdir, "run0")
        run_b_dir = os.path.join(tmpdir, "run1")
        os.makedirs(run_a_dir, exist_ok=True)
        os.makedirs(run_b_dir, exist_ok=True)

        files_run_a: list[str] = []
        files_run_b: list[str] = []

        # Keep identical directory layouts between the two runs so argv stack addresses stay aligned.
        for name in secret_names:
            path_a = os.path.join(run_a_dir, name)
            path_b = os.path.join(run_b_dir, name)
            write_bytes(path_a, secret_orig[name])
            write_bytes(path_b, secret_prime[name])
            files_run_a.append(path_a)
            files_run_b.append(path_b)

        for name in public_names:
            path_a = os.path.join(run_a_dir, name)
            path_b = os.path.join(run_b_dir, name)
            write_bytes(path_a, public_values[name])
            write_bytes(path_b, public_values[name])
            files_run_a.append(path_a)
            files_run_b.append(path_b)

        trace_a_path = os.path.join(tmpdir, "trace0.log")
        trace_b_path = os.path.join(tmpdir, "trace1.log")
        run_pin_trace(executable_path, files_run_a, timeout, pin_root, trace_a_path, debug)
        run_pin_trace(executable_path, files_run_b, timeout, pin_root, trace_b_path, debug)

        divergence = compare_trace_files(trace_a_path, trace_b_path)
        if divergence is None:
            return None

        resolved_ip, location, column_bounds = resolve_divergence_location(executable_path, divergence)
        return ReplayResult(
            culprit_ip=divergence.culprit_ip,
            resolved_ip=resolved_ip,
            location=location,
            divergence_kind=classify_divergence(divergence),
            column_bounds=column_bounds,
        )


def extract_var_bytes(ktest_file: str, variable_name: str) -> bytes:
    output_path = f"{ktest_file}.{variable_name}"
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    subprocess.run(
        ["ktest-tool", "--extract", variable_name, ktest_file],
        check=True,
        capture_output=True,
        text=True,
    )
    if not os.path.isfile(output_path):
        raise RuntimeError(f"ktest-tool did not produce {output_path}")
    return read_bytes(output_path)


def extract_ktest_inputs(
    ktest_file: str,
    secrets: Sequence[str],
    publics: Sequence[str],
) -> tuple[dict[str, bytes], dict[str, bytes], dict[str, bytes]]:
    secret_orig: dict[str, bytes] = {}
    secret_prime: dict[str, bytes] = {}
    public_values: dict[str, bytes] = {}

    for public_name in publics:
        public_values[public_name] = extract_var_bytes(ktest_file, public_name)

    for secret_name in secrets:
        secret_orig[secret_name] = extract_var_bytes(ktest_file, secret_name)
        for suffix in PRIME_SUFFIXES:
            prime_name = f"{secret_name}{suffix}"
            try:
                secret_prime[secret_name] = extract_var_bytes(ktest_file, prime_name)
                break
            except subprocess.CalledProcessError:
                continue
        if secret_name not in secret_prime:
            raise RuntimeError(f"Could not extract a prime variant for secret '{secret_name}' from {ktest_file}")

    return secret_orig, secret_prime, public_values


def resolve_ktest_file(klee_output: str, inst_id: int, kind: str) -> str:
    klee_output_dir = os.path.abspath(klee_output)
    candidate = os.path.join(klee_output_dir, f"{kind}_counterexample_{inst_id}.ktest")
    if os.path.isfile(candidate):
        return candidate

    raise FileNotFoundError(f"Missing KTest file for inst_id={inst_id} under {klee_output_dir}")


def print_replay_location(result: ReplayResult) -> None:
    if result.location is None:
        if result.culprit_ip is not None:
            print(f"{result.divergence_kind} divergence after 0x{result.culprit_ip:x}")
        else:
            print(f"{result.divergence_kind} divergence observed but no instruction address was resolved")
        return

    file_name, line_no, col_no = result.location
    address = result.resolved_ip if result.resolved_ip is not None else result.culprit_ip
    if address is None:
        print(f"{result.divergence_kind} divergence at {file_name}:{line_no}:{col_no}")
        return
    print(f"{result.divergence_kind} divergence at 0x{address:x}: {file_name}:{line_no}:{col_no}")


def divergence_kind_matches(expected_kind: str | None, actual_kind: str) -> bool:
    if expected_kind is None:
        return True
    return expected_kind == actual_kind


def location_matches(
    expected_filename: str | None,
    expected_line: int | None,
    expected_column: int | None,
    actual_file: str,
    actual_line: int,
    actual_column: int,
    actual_previous_column: int | None = None,
    actual_next_column: int | None = None,
) -> LocationMatchResult:
    if expected_filename is not None and os.path.basename(expected_filename) != os.path.basename(actual_file):
        return LocationMatchResult(matches=False)
    if expected_line is not None and expected_line != actual_line:
        if _same_expression_match(actual_file, expected_line, actual_line):
            return LocationMatchResult(matches=True, same_expression=True)
        return LocationMatchResult(matches=False)
    if expected_column is None:
        return LocationMatchResult(matches=True)
    if expected_column == actual_column:
        return LocationMatchResult(matches=True)

    lower_bound = actual_previous_column
    upper_bound = actual_next_column
    if lower_bound is not None and lower_bound >= actual_column:
        lower_bound = None
    if upper_bound is not None and upper_bound <= actual_column:
        upper_bound = None
    if lower_bound is None and upper_bound is None:
        return LocationMatchResult(matches=True, same_line_different_column=True)
    if lower_bound is not None and not (lower_bound <= expected_column):
        return LocationMatchResult(matches=True, same_line_different_column=True)
    if upper_bound is not None and not (expected_column <= upper_bound):
        return LocationMatchResult(matches=True, same_line_different_column=True)
    return LocationMatchResult(matches=True, snapped=True)


def format_snapped_success(
    actual_column: int,
    expected_column: int,
    previous_column: int | None,
    next_column: int | None,
) -> str:
    if previous_column is not None and next_column is not None:
        window = f"{previous_column} <= y <= {next_column}"
    elif previous_column is not None:
        window = f"{previous_column} <= y"
    elif next_column is not None:
        window = f"y <= {next_column}"
    else:
        window = "no DWARF column window"
    return (
        f"Success (reported column {actual_column} vs expected {expected_column}, "
        f"considered close enough within {window})"
    )


def format_same_expression_success(
    actual_file: str,
    actual_line: int,
    actual_column: int,
    expected_file: str | None,
    expected_line: int | None,
    expected_column: int | None,
) -> str:
    expected_loc = format_location(expected_file, expected_line, expected_column)
    actual_loc = format_location(actual_file, actual_line, actual_column)
    return f"Success (same expression span: expected {expected_loc}, got {actual_loc})"


def format_same_line_column_success(actual_column: int, expected_column: int) -> str:
    return f"Success (same line; using replay column {actual_column} instead of reported column {expected_column})"


def parse_secret_input_spec(spec: str) -> dict[str, tuple[int, int, int]]:
    result: dict[str, tuple[int, int, int]] = {}
    if not spec:
        return result

    for item in spec.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(f"Invalid secret specification '{entry}', expected name:bytes=orig/prime")
        name_part, values_part = entry.split("=", 1)
        if ":" not in name_part:
            raise ValueError(f"Invalid secret specification '{entry}', expected name:bytes=orig/prime")
        name, size_str = name_part.split(":", 1)
        name = name.strip()
        try:
            size = int(size_str, 0)
        except ValueError as exc:
            raise ValueError(f"Invalid byte size in secret specification '{entry}'") from exc
        if size <= 0:
            raise ValueError(f"Byte size must be positive in secret specification '{entry}'")
        if "/" not in values_part:
            raise ValueError(f"Invalid secret specification '{entry}', expected name:bytes=orig/prime")
        orig_str, prime_str = values_part.split("/", 1)
        result[name] = (
            size,
            _parse_input_value_int(orig_str, entry, "original secret"),
            _parse_input_value_int(prime_str, entry, "prime secret"),
        )

    return result


def parse_public_input_spec(spec: str) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    if not spec:
        return result

    for item in spec.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(f"Invalid public specification '{entry}', expected name:bytes=value")
        name_part, value_str = entry.split("=", 1)
        if ":" not in name_part:
            raise ValueError(f"Invalid public specification '{entry}', expected name:bytes=value")
        name, size_str = name_part.split(":", 1)
        name = name.strip()
        try:
            size = int(size_str, 0)
        except ValueError as exc:
            raise ValueError(f"Invalid byte size in public specification '{entry}'") from exc
        if size <= 0:
            raise ValueError(f"Byte size must be positive in public specification '{entry}'")
        result[name] = (size, _parse_input_value_int(value_str, entry, "public"))

    return result


def build_value_input_bytes(
    secrets: dict[str, tuple[int, int, int]],
    publics: dict[str, tuple[int, int]],
) -> tuple[dict[str, bytes], dict[str, bytes], dict[str, bytes]]:
    secret_orig: dict[str, bytes] = {}
    secret_prime: dict[str, bytes] = {}
    public_values: dict[str, bytes] = {}

    for name, (size, value_orig, value_prime) in secrets.items():
        try:
            secret_orig[name] = int(value_orig).to_bytes(size, byteorder="big", signed=False)
            secret_prime[name] = int(value_prime).to_bytes(size, byteorder="big", signed=False)
        except OverflowError as exc:
            raise ValueError(f"Secret value for '{name}' does not fit in {size} bytes") from exc

    for name, (size, value) in publics.items():
        try:
            public_values[name] = int(value).to_bytes(size, byteorder="big", signed=False)
        except OverflowError as exc:
            raise ValueError(f"Public value for '{name}' does not fit in {size} bytes") from exc

    return secret_orig, secret_prime, public_values


def _load_json_notes(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            raw = json.load(stream)
    except (OSError, ValueError):
        return {}

    if isinstance(raw, dict):
        notes = raw.get("notes")
        if isinstance(notes, dict):
            return notes
    return {}


def _build_abacus_specs(
    counterexamples: dict[str, int],
    notes: dict[str, Any],
    sym_size: int,
) -> tuple[str, str] | None:
    secret_layout = notes.get("secret_layout")
    public_layout = notes.get("public_layout")

    secret_parts: list[str] = []
    if isinstance(secret_layout, list) and secret_layout:
        for entry in secret_layout:
            if not isinstance(entry, dict):
                raise ValueError("notes.secret_layout entries must be dictionaries")
            name = entry.get("name")
            size = entry.get("size")
            if not isinstance(name, str) or not name:
                raise ValueError("notes.secret_layout entries must define a non-empty name")
            if not isinstance(size, int) or size <= 0:
                raise ValueError(f"notes.secret_layout entry for {name!r} has invalid size")
            value = counterexamples.get(name)
            prime_value = counterexamples.get(f"{name}__prime")
            if value is None or prime_value is None:
                return None
            secret_parts.append(f"{name}:{size}={int(value)}/{int(prime_value)}")
    else:
        exp = counterexamples.get("exp")
        exp_prime = counterexamples.get("exp__prime")
        if exp is None or exp_prime is None:
            return None
        secret_parts.append(f"exp:{sym_size}={int(exp)}/{int(exp_prime)}")

    public_parts: list[str] = []
    if isinstance(public_layout, list) and public_layout:
        for entry in public_layout:
            if not isinstance(entry, dict):
                raise ValueError("notes.public_layout entries must be dictionaries")
            name = entry.get("name")
            size = entry.get("size")
            if not isinstance(name, str) or not name:
                raise ValueError("notes.public_layout entries must define a non-empty name")
            if not isinstance(size, int) or size <= 0:
                raise ValueError(f"notes.public_layout entry for {name!r} has invalid size")
            value = counterexamples.get(name)
            if value is None:
                return None
            public_parts.append(f"{name}:{size}={int(value)}")
    elif counterexamples.get("base") is not None and counterexamples.get("mod") is not None:
        public_parts.append(f"base:{sym_size}={int(counterexamples['base'])}")
        public_parts.append(f"mod:{sym_size}={int(counterexamples['mod'])}")

    return ",".join(secret_parts), ",".join(public_parts)


def mode_dataframe(
    input_json: str,
    klee_output: str,
    executable: str,
    secret: str,
    public: str,
    timeout: int,
    output: str | None,
    library: str,
    debug: bool,
) -> int:
    from tools.shared.common import load_combined_json, save_combined_json  # type: ignore

    require_tools(["ktest-tool"])
    warn_addrinfo_unavailable()

    resolved_pin_root = resolve_pin_root()
    executable_path = os.path.abspath(executable)
    secrets = parse_list(secret)
    publics = parse_list(public)

    df = load_combined_json(input_json)
    if "reproduced" in df.columns:
        df = df.drop(columns=["reproduced"])
    if "counterexamples" not in df.columns:
        df["counterexamples"] = [dict() for _ in range(len(df.index))]
    else:
        df["counterexamples"] = df["counterexamples"].apply(lambda value: value if isinstance(value, dict) else {})
    if "non_ct_count" not in df.columns:
        df["non_ct_count"] = 0
    if "library" not in df.columns:
        df["library"] = library
    else:
        df["library"] = df["library"].apply(lambda value: value if isinstance(value, str) and value.strip() else library)

    df["reproduced_status"] = STATUS_NOT_REPRODUCED
    for idx, row in df[df["non_ct_count"] > 0].iterrows():
        inst_id = coerce_int(row.get("inst_id"))
        if inst_id is None:
            print(f"Reproducing {row.get('filename')}:{row.get('line')}:{row.get('column')} ... missing inst_id")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        try:
            row_kind = normalize_result_kind(row.get("kind"))
        except (TypeError, ValueError) as err:
            print(f"Reproducing {row.get('filename')}:{row.get('line')}:{row.get('column')} ... invalid kind ({err})")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        try:
            ktest_file = resolve_ktest_file(klee_output, inst_id, row_kind)
        except FileNotFoundError as err:
            print(f"Reproducing {row.get('filename')}:{row.get('line')}:{row.get('column')} ... {err}")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        print(
            f"Reproducing {row.get('filename')}:{row.get('line')}:{row.get('column')} with {os.path.basename(ktest_file)} ... ",
            end="",
            flush=True,
        )

        try:
            secret_orig, secret_prime, public_values = extract_ktest_inputs(ktest_file, secrets, publics)
        except (subprocess.CalledProcessError, RuntimeError, OSError) as err:
            print(f"Failed ({err})")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        try:
            replay = analyze_input_bytes(
                executable=executable_path,
                secret_names=secrets,
                public_names=publics,
                secret_orig=secret_orig,
                secret_prime=secret_prime,
                public_values=public_values,
                timeout=timeout,
                pin_root=resolved_pin_root,
                debug=debug,
            )
        except subprocess.TimeoutExpired:
            print("Timeout")
            df.at[idx, "reproduced_status"] = STATUS_TIMEOUT
            continue
        except (RuntimeError, subprocess.CalledProcessError) as err:
            print(f"Operational failure: {err}", file=sys.stderr)
            return 2

        if replay is None:
            print("Failed with identical traces")
            df.at[idx, "reproduced_status"] = STATUS_IDENTICAL_TRACE
            continue

        if replay.location is None:
            if replay.culprit_ip is not None:
                print(f"Failed with {replay.divergence_kind} divergence at 0x{replay.culprit_ip:x} (no debug info)")
            else:
                print(f"Failed ({replay.divergence_kind} divergence, no debug info)")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        if not divergence_kind_matches(row_kind, replay.divergence_kind):
            print(f"Failed (kind mismatch: expected {row_kind}, got {replay.divergence_kind})")
            df.at[idx, "reproduced_status"] = STATUS_KIND_MISMATCH
            continue

        actual_file, actual_line, actual_col = replay.location
        expected_line = coerce_int(row.get("line"))
        expected_col = coerce_int(row.get("column"))
        previous_column = None
        next_column = None
        if replay.column_bounds is not None:
            previous_column, next_column = replay.column_bounds
        match_result = location_matches(
            expected_filename=row.get("filename") if isinstance(row.get("filename"), str) else None,
            expected_line=expected_line,
            expected_column=expected_col,
            actual_file=actual_file,
            actual_line=actual_line,
            actual_column=actual_col,
            actual_previous_column=previous_column,
            actual_next_column=next_column,
        )
        if match_result.matches:
            if match_result.snapped and expected_col is not None:
                print(format_snapped_success(actual_col, expected_col, previous_column, next_column))
            elif match_result.same_expression:
                print(
                    format_same_expression_success(
                        actual_file,
                        actual_line,
                        actual_col,
                        row.get("filename") if isinstance(row.get("filename"), str) else None,
                        expected_line,
                        expected_col,
                    )
                )
            elif match_result.same_line_different_column and expected_col is not None:
                print(format_same_line_column_success(actual_col, expected_col))
            else:
                print("Success")
            if expected_line == actual_line and expected_col is not None and expected_col != actual_col:
                df.at[idx, "column"] = actual_col
            df.at[idx, "reproduced_status"] = STATUS_SUCCESS
        else:
            print(f"Failed at {actual_file}:{actual_line}:{actual_col}")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH

    if output:
        save_combined_json(df, output)
    return 0


def mode_ktest_file(
    executable: str,
    ktest_file: str,
    secret: str,
    public: str,
    timeout: int,
    debug: bool,
) -> int:
    require_tools(["ktest-tool"])
    warn_addrinfo_unavailable()

    resolved_pin_root = resolve_pin_root()
    executable_path = os.path.abspath(executable)
    secrets = parse_list(secret)
    publics = parse_list(public)

    try:
        secret_orig, secret_prime, public_values = extract_ktest_inputs(ktest_file, secrets, publics)
        replay = analyze_input_bytes(
            executable=executable_path,
            secret_names=secrets,
            public_names=publics,
            secret_orig=secret_orig,
            secret_prime=secret_prime,
            public_values=public_values,
            timeout=timeout,
            pin_root=resolved_pin_root,
            debug=debug,
        )
    except subprocess.TimeoutExpired:
        print("Timeout while running Pin traces", file=sys.stderr)
        return 124
    except (subprocess.CalledProcessError, RuntimeError, OSError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    if replay is None:
        print("Identical traces")
        return 1

    print_replay_location(replay)
    return 0


def mode_input_values(
    executable: str,
    secret_spec: str,
    public_spec: str,
    timeout: int,
    debug: bool,
    pin_root: str | None = None,
    expected_filename: str | None = None,
    expected_line: int | None = None,
    expected_column: int | None = None,
    expected_kind: str | None = None,
) -> int:
    warn_addrinfo_unavailable()

    try:
        secrets = parse_secret_input_spec(secret_spec)
        publics = parse_public_input_spec(public_spec)
        secret_orig, secret_prime, public_values = build_value_input_bytes(secrets, publics)
    except ValueError as err:
        print(f"Error parsing inputs: {err}", file=sys.stderr)
        return 2

    resolved_pin_root = pin_root if pin_root is not None else resolve_pin_root()
    executable_path = os.path.abspath(executable)

    try:
        replay = analyze_input_bytes(
            executable=executable_path,
            secret_names=list(secrets.keys()),
            public_names=list(publics.keys()),
            secret_orig=secret_orig,
            secret_prime=secret_prime,
            public_values=public_values,
            timeout=timeout,
            pin_root=resolved_pin_root,
            debug=debug,
        )
    except subprocess.TimeoutExpired:
        print("Timeout while running Pin traces", file=sys.stderr)
        return 124
    except (RuntimeError, subprocess.CalledProcessError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    if replay is None:
        print("Identical traces")
        return 1

    print_replay_location(replay)
    if not divergence_kind_matches(expected_kind, replay.divergence_kind):
        print(f"Kind mismatch: expected {expected_kind}, got {replay.divergence_kind}")
        return 42  # unique code for kind mismatch

    if replay.location is None:
        if expected_filename is not None or expected_line is not None or expected_column is not None:
            return 3
        return 0

    actual_file, actual_line, actual_column = replay.location
    previous_column = None
    next_column = None
    if replay.column_bounds is not None:
        previous_column, next_column = replay.column_bounds
    match_result = location_matches(
        expected_filename,
        expected_line,
        expected_column,
        actual_file,
        actual_line,
        actual_column,
        actual_previous_column=previous_column,
        actual_next_column=next_column,
    )
    if match_result.matches:
        if match_result.snapped and expected_column is not None:
            print(format_snapped_success(actual_column, expected_column, previous_column, next_column))
        elif match_result.same_expression:
            print(
                format_same_expression_success(
                    actual_file,
                    actual_line,
                    actual_column,
                    expected_filename,
                    expected_line,
                    expected_column,
                )
            )
        elif match_result.same_line_different_column and expected_column is not None:
            print(format_same_line_column_success(actual_column, expected_column))
        return 0

    print(
        f"Location mismatch: expected {expected_filename}:{expected_line}:{expected_column}, "
        f"got {actual_file}:{actual_line}:{actual_column}"
    )
    return 3


def mode_abacus_json(
    input_json: str,
    executable: str,
    sym_size: int,
    timeout: int,
    output: str | None,
    library: str,
    debug: bool,
) -> int:
    from tools.shared.common import load_combined_json, save_combined_json  # type: ignore

    resolved_pin_root = resolve_pin_root()
    notes = _load_json_notes(input_json)
    df = load_combined_json(input_json)
    if "counterexamples" not in df.columns:
        if len(df.index) == 0:
            save_combined_json(df, output if output else input_json)
            return 0
        print("Error: counterexamples column missing in input JSON", file=sys.stderr)
        return 2

    if "reproduced" in df.columns:
        df = df.drop(columns=["reproduced"])
    if "counterexamples" not in df.columns:
        df["counterexamples"] = [dict() for _ in range(len(df.index))]
    else:
        df["counterexamples"] = df["counterexamples"].apply(lambda value: value if isinstance(value, dict) else {})
    if "library" not in df.columns:
        df["library"] = library
    else:
        df["library"] = df["library"].apply(lambda value: value if isinstance(value, str) and value.strip() else library)

    df["reproduced_status"] = STATUS_NOT_REPRODUCED
    for idx, row in df.iterrows():
        counterexamples = row.get("counterexamples")
        if not isinstance(counterexamples, dict):
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        try:
            specs = _build_abacus_specs(counterexamples, notes, sym_size)
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
        if specs is None:
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
            continue

        filename = row.get("filename")
        line_no = coerce_int(row.get("line"))
        column_no = coerce_int(row.get("column"))
        expected_kind = None
        raw_kind = row.get("kind")
        if raw_kind is not None:
            try:
                expected_kind = normalize_result_kind(raw_kind)
            except (TypeError, ValueError) as err:
                print(f"Reproducing {filename}:{line_no} ... invalid kind ({err})")
                df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
                continue
        print(f"Reproducing {filename}:{line_no} ... ", end="", flush=True)

        secret_spec, public_spec = specs
        rc = mode_input_values(
            executable=executable,
            secret_spec=secret_spec,
            public_spec=public_spec,
            timeout=timeout,
            pin_root=resolved_pin_root,
            debug=debug,
            expected_filename=filename if isinstance(filename, str) else None,
            expected_line=line_no,
            expected_column=column_no,
            expected_kind=expected_kind,
        )
        if rc == 0:
            print("Success")
            df.at[idx, "reproduced_status"] = STATUS_SUCCESS
        elif rc == 124:
            print("Failed (timeout)")
            df.at[idx, "reproduced_status"] = STATUS_TIMEOUT
        elif rc == 1:
            print("Failed (identical traces)")
            df.at[idx, "reproduced_status"] = STATUS_IDENTICAL_TRACE
        elif rc == 42:
            print("Failed (kind mismatch)")
            df.at[idx, "reproduced_status"] = STATUS_KIND_MISMATCH
        elif rc == 3:
            print("Failed (location mismatch)")
            df.at[idx, "reproduced_status"] = STATUS_LOCATION_MISMATCH
        else:
            print(f"Failed (unexpected rc={rc})", file=sys.stderr)
            return rc

    for column_name in ["visit_count", "non_ct_count", "visit_time"]:
        if column_name in df.columns:
            try:
                if df[column_name].isna().all():
                    df = df.drop(columns=[column_name])
            except Exception:
                pass

    save_combined_json(df, output if output else input_json)
    return 0


def reproduce_json_positives(
    *,
    input_json: str,
    klee_output: str,
    executable: str,
    secret: str,
    public: str = "",
    timeout: int = 300,
    output: str | None = None,
    library: str = "unknown",
    debug: bool = False,
) -> int:
    return mode_dataframe(
        input_json=input_json,
        klee_output=klee_output,
        executable=executable,
        secret=secret,
        public=public,
        timeout=timeout,
        output=output,
        library=library,
        debug=debug,
    )


def reproduce_ktest_positive(
    *,
    executable: str,
    ktest_file: str,
    secret: str,
    public: str = "",
    timeout: int = 300,
    debug: bool = False,
) -> int:
    return mode_ktest_file(
        executable=executable,
        ktest_file=ktest_file,
        secret=secret,
        public=public,
        timeout=timeout,
        debug=debug,
    )


def reproduce_input_values(
    *,
    executable: str,
    secret_spec: str,
    public_spec: str,
    timeout: int = 300,
    debug: bool = False,
    expected_filename: str | None = None,
    expected_line: int | None = None,
    expected_column: int | None = None,
    expected_kind: str | None = None,
) -> int:
    return mode_input_values(
        executable=executable,
        secret_spec=secret_spec,
        public_spec=public_spec,
        timeout=timeout,
        debug=debug,
        expected_filename=expected_filename,
        expected_line=expected_line,
        expected_column=expected_column,
        expected_kind=expected_kind,
    )


def reproduce_abacus_json_positives(
    *,
    input_json: str,
    executable: str,
    sym_size: int = 4,
    timeout: int = 300,
    output: str | None = None,
    library: str = "unknown",
    debug: bool = False,
) -> int:
    return mode_abacus_json(
        input_json=input_json,
        executable=executable,
        sym_size=sym_size,
        timeout=timeout,
        output=output,
        library=library,
        debug=debug,
    )


def build_parsers_and_dispatch(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce divergence either from a dataframe (--json), a single .ktest (--file), "
            "explicit input values (--input), or an Abacus JSON batch (--abacus-json)."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", help="Path to the combined JSON produced by klee_log_to_json.py or postprocess comparison.")
    group.add_argument("--file", help="Path to a single KLEE .ktest file.")
    group.add_argument(
        "--input",
        action="store_true",
        help=(
            "Use explicit values instead of a ktest file. "
            "Example: --input --executable ./prog --secret v1:8=100/200 --public v2:8=5"
        ),
    )
    group.add_argument("--abacus-json", help="Path to an Abacus-style combined JSON containing per-row counterexamples.")

    parser.add_argument("--klee-output", help="Path to the KLEE output directory (required with --json).")
    parser.add_argument("--executable", required=True, help="Path to the replay executable.")
    parser.add_argument(
        "--secret",
        default="",
        help=(
            "In --json/--file modes: comma-separated secret variable names. "
            "In --input mode: comma-separated name:bytes=orig/prime."
        ),
    )
    parser.add_argument(
        "--public",
        default="",
        help=(
            "In --json/--file modes: comma-separated public variable names. "
            "In --input mode: comma-separated name:bytes=value."
        ),
    )
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300).")
    parser.add_argument("--output", help="Output JSON path for --json and --abacus-json modes.")
    parser.add_argument("--debug", action="store_true", help="Print the exact Pin command when a replay fails or times out.")
    parser.add_argument("--sym-size", type=int, default=4, help="Symbol byte size for --abacus-json mode (default: 4).")
    parser.add_argument(
        "--library",
        default="unknown",
        choices=["mbedtls", "libgcrypt", "openssl", "bearssl", "unknown"],
        help="Library identifier for JSON-writing modes.",
    )
    parser.add_argument("--expected-filename", help="Expected replay source filename for --input mode.")
    parser.add_argument("--expected-line", type=int, help="Expected replay source line for --input mode.")
    parser.add_argument("--expected-column", type=int, help="Expected replay source column for --input mode.")
    parser.add_argument(
        "--expected-kind",
        choices=[KIND_BRANCH, KIND_MEMORY],
        help="Expected replay divergence kind for --input mode.",
    )

    args = parser.parse_args(argv)

    if args.json:
        if not args.klee_output:
            parser.error("--klee-output is required when using --json")
        if not args.secret:
            parser.error("--secret is required when using --json")
        return mode_dataframe(
            input_json=args.json,
            klee_output=args.klee_output,
            executable=args.executable,
            secret=args.secret,
            public=args.public,
            timeout=args.timeout,
            output=args.output,
            library=args.library,
            debug=args.debug,
        )

    if args.file:
        if not args.secret:
            parser.error("--secret is required when using --file")
        return mode_ktest_file(
            executable=args.executable,
            ktest_file=args.file,
            secret=args.secret,
            public=args.public,
            timeout=args.timeout,
            debug=args.debug,
        )

    if args.abacus_json:
        return mode_abacus_json(
            input_json=args.abacus_json,
            executable=args.executable,
            sym_size=args.sym_size,
            timeout=args.timeout,
            output=args.output,
            library=args.library,
            debug=args.debug,
        )

    if not args.secret:
        parser.error("--secret is required when using --input")
    return mode_input_values(
        executable=args.executable,
        secret_spec=args.secret,
        public_spec=args.public,
        timeout=args.timeout,
        debug=args.debug,
        expected_filename=args.expected_filename,
        expected_line=args.expected_line,
        expected_column=args.expected_column,
        expected_kind=args.expected_kind,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return build_parsers_and_dispatch(list(sys.argv[1:] if argv is None else argv))
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
