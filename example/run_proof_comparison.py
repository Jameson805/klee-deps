#!/usr/bin/env python3
"""Run a focused BINSEC vs KLEE-CF proof comparison for one benchmark case.

This helper lives under ``example/`` on purpose: it is a narrow, exploratory
workflow rather than part of the main experiment pipeline.

What it does:

- materializes one temporary benchmark workspace
- builds the selected case for both BINSEC and KLEE-CF
- runs a small fixed heuristic set for each tool
- stores raw logs plus a single ``summary.json`` with compact coverage data

Common uses:

- compare BINSEC and KLEE coverage on one target/config pair
- inspect an existing ``summary.json`` without rerunning either tool
- print per-file visited line differences from a finished proof run

Examples:

- run one comparison and save artifacts under the default proof-runs directory
  ``python example/run_proof_comparison.py --benchmark libg:default --target des --config fix_pub --trace-binsec``
- inspect a previous run
  ``python example/run_proof_comparison.py --summary /path/to/summary.json --diff-lines cipher/bn.c``
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if os.fspath(REPO_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(REPO_ROOT))

from scripts.experiments.common import REPO_ROOT as COMMON_REPO_ROOT, expand_benchmark_cases, prepare_benchmark_workspace
from tools.shared.experiment_registry import build_for_tool, definition, format_benchmark_selector
from tools.shared.tool_artifacts import resolve_executable_path, resolve_klee_tool_layout

assert COMMON_REPO_ROOT == REPO_ROOT


KLEE_DEFAULT_SEARCH = ("random-path", "nurs:covnew")
BINSEC_HEURISTICS = ("nurs", "dfs")
KLEE_HEURISTICS = {
    "default": KLEE_DEFAULT_SEARCH,
    "dfs": ("dfs",),
}
TRACE_LINE_RE = re.compile(r"^\[sse:[^]]+\] (0x[0-9a-fA-F]+)")
KLEE_DONE_RE = re.compile(r"^KLEE: done: (?P<key>.+?) = (?P<value>.+)$")
ADDR2LINE_LOCATION_RE = re.compile(r"^(?P<path>.+):(?P<line>\d+)(?::(?P<column>\d+))?$")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one benchmark proof comparison with BINSEC and KLEE-CF.",
        epilog=(
            "Examples:\n"
            "  python example/run_proof_comparison.py --benchmark libg:default --target des --config fix_pub\n"
            "  python example/run_proof_comparison.py --output-dir /tmp/proof --diff-lines src/foo.c\n"
            "  python example/run_proof_comparison.py --summary /tmp/proof/summary.json --diff-lines src/foo.c"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--benchmark", default="libg:default", help="Benchmark selector in LIBRARY:VARIANT form")
    parser.add_argument("--target", default="des", help="Expanded target id to run")
    parser.add_argument("--config", default="fix_pub", help="Expanded config id to run")
    parser.add_argument("--timeout", type=int, default=60, help="Per-run timeout in seconds")
    parser.add_argument("--tmp-dir", default="/tmp", help="Temporary workspace parent directory")
    parser.add_argument(
        "--output-dir",
        help="Optional output directory; defaults to a timestamped proof_runs path",
    )
    parser.add_argument(
        "--trace-binsec",
        action="store_true",
        help="Capture BINSEC instruction addresses from the debug trace and map them back to benchmark sources",
    )
    parser.add_argument(
        "--summary",
        help="Existing summary.json path to inspect without rerunning the proof comparison",
    )
    parser.add_argument(
        "--diff-lines",
        metavar="FILE",
        help="Print per-file visited line differences for the given benchmark-local file",
    )
    parser.add_argument(
        "--binsec-heuristic",
        choices=BINSEC_HEURISTICS,
        default="nurs",
        help="BINSEC heuristic to use for --diff-lines output",
    )
    parser.add_argument(
        "--klee-mode",
        choices=tuple(KLEE_HEURISTICS),
        default="default",
        help="KLEE mode to use for --diff-lines output",
    )
    return parser.parse_args(argv)


def _default_output_dir(benchmark_selector: str, target_id: str, config_id: str) -> Path:
    parent = Path("/work/yl925/klee-deps/proof_runs")
    if not parent.is_dir():
        parent = REPO_ROOT / "results" / "proof_runs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    benchmark_slug = benchmark_selector.replace(":", "_")
    return parent / f"{benchmark_slug}_{target_id}_{config_id}_{stamp}"


def _run(command: list[str], *, cwd: Path, env: dict[str, str], stdout_path: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    rendered_command = [os.fspath(part) for part in command]
    if stdout_path is None:
        return subprocess.run(rendered_command, cwd=cwd, env=env, text=True, check=check)

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as handle:
        return subprocess.run(rendered_command, cwd=cwd, env=env, text=True, stdout=handle, stderr=subprocess.STDOUT, check=check)


def _resolve_case(benchmark_selector: str, target_id: str, config_id: str):
    library_id, variant_id = benchmark_selector.split(":", 1)
    benchmark_definition = definition(library_id, variant_id)
    for tool_id in ("binsec", "klee_cf"):
        if tool_id not in benchmark_definition.tools:
            raise SystemExit(f"benchmark {benchmark_selector!r} does not support {tool_id}")
    matching_cases = [
        case
        for case in expand_benchmark_cases(benchmark_definition, "binsec")
        if case.target_id == target_id and case.config_id == config_id
    ]
    if not matching_cases:
        raise SystemExit(
            f"no case matches benchmark={benchmark_selector!r}, target={target_id!r}, config={config_id!r}"
        )
    return benchmark_definition, matching_cases[0]


def _build_workspace(benchmark_definition, *, tmp_dir: str, env: dict[str, str]) -> Path:
    workspace = prepare_benchmark_workspace(benchmark_definition.code_path, tmp_dir)
    workspace_env = dict(env)
    workspace_env["KLEE_DEPS_WORKSPACE_ROOT"] = str(workspace.root)
    binsec_preset = build_for_tool(benchmark_definition, "binsec").preset
    klee_preset = build_for_tool(benchmark_definition, "klee_cf").preset
    _run(
        [
            "python",
            "-m",
            "tools.build_benchmark",
            "--benchmark",
            format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id),
            "--tool",
            "binsec",
            "--preset",
            binsec_preset,
        ],
        cwd=REPO_ROOT,
        env=workspace_env,
    )
    _run(
        [
            "python",
            "-m",
            "tools.build_benchmark",
            "--benchmark",
            format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id),
            "--tool",
            "klee_cf",
            "--preset",
            klee_preset,
        ],
        cwd=REPO_ROOT,
        env=workspace_env,
    )
    return workspace.root


def _binsec_paths(workspace_root: Path, benchmark_definition, expanded_case) -> tuple[Path, Path]:
    code_path = workspace_root / benchmark_definition.code_path
    executable = code_path / "artifacts" / "binsec" / expanded_case.output_target / expanded_case.public_mode
    sse_script = code_path / "generated" / expanded_case.output_target / f"binsec_{expanded_case.public_mode}.cfg"
    return executable, sse_script


def _klee_bitcode_path(workspace_root: Path, benchmark_definition, expanded_case) -> Path:
    code_path = workspace_root / benchmark_definition.code_path
    return code_path / "artifacts" / "klee" / expanded_case.output_target / f"{expanded_case.config_id}.bc"


def _summarize_mapped_locations(mapped_text: str, *, benchmark_root: Path) -> dict[str, object]:
    benchmark_root = benchmark_root.resolve()
    benchmark_files: dict[str, set[int]] = {}
    benchmark_functions: dict[str, set[str]] = {}

    lines = mapped_text.splitlines()
    for index in range(0, len(lines) - 1, 2):
        function_name = lines[index].strip()
        location_line = lines[index + 1].strip()
        match = ADDR2LINE_LOCATION_RE.match(location_line)
        if match is None:
            continue

        raw_path = os.path.normpath(match.group("path"))
        if raw_path == "??":
            continue

        resolved_path = Path(raw_path).resolve(strict=False)
        try:
            relative_path = resolved_path.relative_to(benchmark_root)
        except ValueError:
            continue

        relative_text = os.fspath(relative_path)
        benchmark_files.setdefault(relative_text, set()).add(int(match.group("line")))
        if function_name and function_name != "??":
            benchmark_functions.setdefault(relative_text, set()).add(function_name)

    files_summary = {
        file_name: {
            "functions": sorted(benchmark_functions.get(file_name, set())),
            "lines": sorted(lines_seen),
            "unique_line_count": len(lines_seen),
        }
        for file_name, lines_seen in sorted(benchmark_files.items())
    }
    total_unique_lines = sum(entry["unique_line_count"] for entry in files_summary.values())
    return {
        "files": files_summary,
        "unique_file_count": len(files_summary),
        "unique_line_count": total_unique_lines,
    }


def _summarize_klee_istats(istats_path: Path, *, benchmark_root: Path) -> dict[str, object]:
    benchmark_root = benchmark_root.resolve()
    current_file: str | None = None
    current_function: str | None = None
    files: dict[str, dict[str, object]] = {}

    for raw_line in istats_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("fl="):
            current_file = line[3:]
            current_function = None
            continue
        if line.startswith("fn="):
            current_function = line[3:]
            continue
        if line.startswith(("cfl=", "cfn=", "calls=", "ob=", "event:", "events:", "positions:", "version:", "creator:", "pid:", "cmd:")):
            continue
        if current_file is None:
            continue

        parts = line.split()
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue

        try:
            source_line = int(parts[1])
            covered_instructions = int(parts[2])
        except ValueError:
            continue
        if source_line <= 0 or covered_instructions <= 0:
            continue

        raw_path = Path(os.path.normpath(current_file))
        if raw_path.is_absolute():
            candidate_path = raw_path.resolve(strict=False)
        else:
            candidate_path = (benchmark_root / raw_path).resolve(strict=False)
            if not candidate_path.exists():
                continue

        try:
            relative_file = candidate_path.relative_to(benchmark_root)
        except ValueError:
            continue

        relative_text = os.fspath(relative_file)
        file_entry = files.setdefault(
            relative_text,
            {
                "functions": set(),
                "lines": set(),
                "covered_instruction_count": 0,
            },
        )
        file_entry["lines"].add(source_line)
        file_entry["covered_instruction_count"] += covered_instructions
        if current_function:
            file_entry["functions"].add(current_function)

    normalized_files = {
        file_name: {
            "functions": sorted(entry["functions"]),
            "lines": sorted(entry["lines"]),
            "unique_line_count": len(entry["lines"]),
            "covered_instruction_count": entry["covered_instruction_count"],
        }
        for file_name, entry in sorted(files.items())
    }
    return {
        "files": normalized_files,
        "unique_file_count": len(normalized_files),
        "unique_line_count": sum(entry["unique_line_count"] for entry in normalized_files.values()),
        "covered_instruction_count": sum(entry["covered_instruction_count"] for entry in normalized_files.values()),
    }


def _extract_binsec_trace(log_path: Path, executable: Path, output_dir: Path, *, benchmark_root: Path) -> dict[str, object]:
    visited_addrs = sorted({match.group(1) for line in log_path.read_text(encoding="utf-8").splitlines() if (match := TRACE_LINE_RE.match(line))})
    trace_summary: dict[str, object] = {"visited_address_count": len(visited_addrs)}
    visited_path = output_dir / "visited.addrs"
    visited_path.write_text("\n".join(visited_addrs) + ("\n" if visited_addrs else ""), encoding="utf-8")
    if not visited_addrs:
        return trace_summary

    addr2line_binary = shutil.which("llvm-addr2line") or shutil.which("addr2line")
    if addr2line_binary is None:
        trace_summary["addr2line_error"] = "missing llvm-addr2line/addr2line"
        return trace_summary

    output = subprocess.run(
        [addr2line_binary, "-e", os.fspath(executable), "-f", "-C", *visited_addrs],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    mapped_path = output_dir / "visited.addr2line"
    mapped_path.write_text(output.stdout, encoding="utf-8")
    trace_summary["addr2line_binary"] = addr2line_binary
    trace_summary["addr2line_exit_code"] = output.returncode
    trace_summary["benchmark_sources"] = _summarize_mapped_locations(output.stdout, benchmark_root=benchmark_root)
    return trace_summary


def _run_binsec(
    *,
    heuristic: str,
    executable: Path,
    sse_script: Path,
    timeout_seconds: int,
    output_dir: Path,
    trace_binsec: bool,
    benchmark_root: Path,
    env: dict[str, str],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stats_path = output_dir / "checkct_stats.toml"
    log_path = output_dir / "binsec.log"
    command = [
        os.fspath(resolve_executable_path("binsec")),
        "-sse",
        "-checkct",
        "-fml-solver",
        "z3",
        "-smt-solver",
        "z3",
        "-sse-timeout",
        str(timeout_seconds),
        "-sse-jump-enum",
        "10",
        "-sse-script",
        os.fspath(sse_script),
        "-sse-depth",
        "1000000000000",
        "-sse-heuristics",
        heuristic,
        "-checkct-features",
        "control-flow,memory-access",
        "-checkct-stats-file",
        os.fspath(stats_path),
    ]
    if trace_binsec:
        command.extend(["-sse-no-screen", "-sse-debug-level", "2"])
    command.append(os.fspath(executable))
    _run(command, cwd=REPO_ROOT, env=env, stdout_path=log_path)
    with stats_path.open("rb") as handle:
        stats = tomllib.load(handle)
    result: dict[str, object] = {
        "heuristic": heuristic,
        "stats_file": os.fspath(stats_path),
        "log_file": os.fspath(log_path),
        "stats": stats,
    }
    if trace_binsec:
        result["trace"] = _extract_binsec_trace(log_path, executable, output_dir, benchmark_root=benchmark_root)
    return result


def _parse_klee_done_info(info_path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not info_path.is_file():
        return parsed
    for line in info_path.read_text(encoding="utf-8").splitlines():
        match = KLEE_DONE_RE.match(line)
        if match:
            parsed[match.group("key")] = match.group("value")
    return parsed


def _run_klee(
    *,
    label: str,
    searchers: tuple[str, ...],
    bitcode: Path,
    timeout_seconds: int,
    output_root: Path,
    benchmark_root: Path,
    env: dict[str, str],
) -> dict[str, object]:
    output_dir = output_root / f"klee_{label}_out"
    log_path = output_root / f"klee_{label}.log"
    shutil.rmtree(output_dir, ignore_errors=True)
    timeout_text = f"{timeout_seconds}s"
    command = [
        "timeout",
        "--foreground",
        "--signal=INT",
        "--kill-after=1800s",
        timeout_text,
        os.fspath(resolve_klee_tool_layout("klee-cf").binary),
        f"--output-dir={output_dir}",
        "--libc=uclibc",
        "--posix-runtime",
        "--external-calls=all",
        "--solver-backend=stp",
        "--concretize-on-solver-timeout=true",
        "--kdalloc",
        "--kdalloc-constants-size=5",
        "--kdalloc-globals-size=5",
        "--kdalloc-heap-size=20",
        "--kdalloc-stack-size=10",
        "--dump-states-on-halt=false",
        "--use-batching-search=false",
        "--max-solver-time=30s",
        "--max-memory=10000",
        "--emit-all-errors=true",
    ]
    command.extend(f"--search={searcher}" for searcher in searchers)
    command.append(os.fspath(bitcode))
    completed = _run(command, cwd=REPO_ROOT, env=env, stdout_path=log_path, check=False)
    if completed.returncode not in (0, 124):
        raise SystemExit(f"KLEE run {label!r} failed with exit code {completed.returncode}; see {log_path}")
    info_path = output_dir / "info"
    counterexamples = sorted(output_dir.glob("memory_counterexample_*.ktest"))
    istats_path = output_dir / "run.istats"
    return {
        "label": label,
        "search": list(searchers),
        "log_file": os.fspath(log_path),
        "output_dir": os.fspath(output_dir),
        "exit_code": completed.returncode,
        "done": _parse_klee_done_info(info_path),
        "memory_counterexample_count": len(counterexamples),
        "benchmark_sources": _summarize_klee_istats(istats_path, benchmark_root=benchmark_root),
    }


def _load_summary(summary_path: Path) -> dict[str, object]:
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _get_nested(mapping: dict[str, object], *keys: str) -> object:
    current: object = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _print_line_diff(summary: dict[str, object], *, file_name: str, binsec_heuristic: str, klee_mode: str) -> int:
    binsec_lines = _get_nested(summary, "binsec", binsec_heuristic, "trace", "benchmark_sources", "files", file_name, "lines")
    klee_lines = _get_nested(summary, "klee", klee_mode, "benchmark_sources", "files", file_name, "lines")
    if binsec_lines is None and klee_lines is None:
        print(f"no visited lines found for {file_name!r} in BINSEC {binsec_heuristic!r} or KLEE {klee_mode!r}", file=sys.stderr)
        return 1

    normalized_binsec = sorted({int(value) for value in (binsec_lines or [])})
    normalized_klee = sorted({int(value) for value in (klee_lines or [])})
    binsec_set = set(normalized_binsec)
    klee_set = set(normalized_klee)
    diff = {
        "file": file_name,
        "binsec_heuristic": binsec_heuristic,
        "klee_mode": klee_mode,
        "binsec_lines": normalized_binsec,
        "klee_lines": normalized_klee,
        "only_binsec": sorted(binsec_set - klee_set),
        "only_klee": sorted(klee_set - binsec_set),
        "both": sorted(binsec_set & klee_set),
    }
    print(json.dumps(diff, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.diff_lines:
        if args.summary:
            summary_path = Path(args.summary).expanduser().resolve()
        else:
            if not args.output_dir:
                raise SystemExit("--diff-lines without --summary requires --output-dir pointing to an existing proof run")
            summary_path = Path(args.output_dir).expanduser().resolve() / "summary.json"
        if not summary_path.is_file():
            raise SystemExit(f"summary file not found: {summary_path}")
        summary = _load_summary(summary_path)
        return _print_line_diff(
            summary,
            file_name=args.diff_lines,
            binsec_heuristic=args.binsec_heuristic,
            klee_mode=args.klee_mode,
        )

    benchmark_definition, expanded_case = _resolve_case(args.benchmark, args.target, args.config)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else _default_output_dir(args.benchmark, args.target, args.config)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.setdefault("KLEE_TOOL_ID", "klee-cf")
    binsec_binary = resolve_executable_path("binsec")
    klee_binary = resolve_klee_tool_layout("klee-cf").binary

    workspace_root = _build_workspace(benchmark_definition, tmp_dir=args.tmp_dir, env=env)
    env["KLEE_DEPS_WORKSPACE_ROOT"] = os.fspath(workspace_root)

    executable, sse_script = _binsec_paths(workspace_root, benchmark_definition, expanded_case)
    bitcode = _klee_bitcode_path(workspace_root, benchmark_definition, expanded_case)
    benchmark_root = workspace_root / benchmark_definition.code_path

    summary: dict[str, object] = {
        "benchmark": args.benchmark,
        "target": args.target,
        "config": args.config,
        "timeout_seconds": args.timeout,
        "workspace_root": os.fspath(workspace_root),
        "output_dir": os.fspath(output_dir),
        "environment": {
            "binsec": os.fspath(binsec_binary),
            "klee_cf": os.fspath(klee_binary),
        },
        "binsec": {},
        "klee": {},
    }

    for heuristic in BINSEC_HEURISTICS:
        summary["binsec"][heuristic] = _run_binsec(
            heuristic=heuristic,
            executable=executable,
            sse_script=sse_script,
            timeout_seconds=args.timeout,
            output_dir=output_dir / f"binsec_{heuristic}",
            trace_binsec=args.trace_binsec,
            benchmark_root=benchmark_root,
            env=env,
        )

    for label, searchers in KLEE_HEURISTICS.items():
        summary["klee"][label] = _run_klee(
            label=label,
            searchers=searchers,
            bitcode=bitcode,
            timeout_seconds=args.timeout,
            output_root=output_dir,
            benchmark_root=benchmark_root,
            env=env,
        )

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote proof run summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())