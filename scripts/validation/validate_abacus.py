#!/usr/bin/env python3
"""Validate merged ABACUS JSON outputs on the host.

ABACUS runs inside the container and emits one merged JSON file per benchmark case.
This module resolves the matching replay executable from benchmark registry data,
rebuilds it when needed, and runs the shared Pin-based reproduction helper over
rows that actually carry concrete counterexamples.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from scripts.experiments.common import REPO_ROOT, expand_benchmark_cases, resolve_case_template
from tools.postprocess.reproduce_positives import reproduce_abacus_json_positives
from tools.shared.experiment_registry import (
    build_for_tool,
    canonical_case_id,
    definition,
    selected_benchmarks,
)


def _resolve_preset_name(preset_template: str, sym_size: int | None, *, owner: str) -> str:
    """Resolve one preset template, requiring a sym size only when the template uses it."""
    if "{sym_size}" in preset_template:
        if sym_size is None:
            raise SystemExit(f"{owner} requires --sym-size because preset {preset_template!r} depends on it")
        return preset_template.format(sym_size=sym_size)
    return preset_template


@dataclass(frozen=True)
class AbacusValidationCase:
    """Replay metadata derived from one registry-backed ABACUS benchmark case."""

    output_stem: str
    replay_executable: str
    build_tool_id: str
    benchmark_selector: str
    build_preset: str
    library: str


def _validation_library_name(library_id: str) -> str:
    """Map benchmark library ids onto the replay helper's supported library set."""

    if library_id in {"mbedtls", "libgcrypt", "bearssl", "openssl"}:
        return library_id
    if library_id == "openssl_almeida":
        return "openssl"
    return "unknown"


def _build_case_index() -> dict[str, AbacusValidationCase]:
    """Index merged ABACUS output stems by the replay data needed to validate them."""

    cases_by_stem: dict[str, AbacusValidationCase] = {}
    for library_id, variant_id in selected_benchmarks("abacus", None):
        benchmark_definition = definition(library_id, variant_id)
        klee_build = build_for_tool(benchmark_definition, "klee_cf")
        selector_text = f"{benchmark_definition.library_id}:{benchmark_definition.variant_id}"
        for expanded_case in expand_benchmark_cases(benchmark_definition, "abacus"):
            output_stem = canonical_case_id(
                benchmark_definition.library_id,
                benchmark_definition.variant_id,
                expanded_case.target_id,
                expanded_case.config_id,
            )
            replay_executable = resolve_case_template(
                benchmark_definition,
                expanded_case,
                "klee_replay_script",
                f"{benchmark_definition.code_path}/klee_{expanded_case.public_mode}_replay{expanded_case.target_suffix}",
            )
            if output_stem in cases_by_stem:
                raise ValueError(f"duplicate ABACUS validation case id: {output_stem}")
            cases_by_stem[output_stem] = AbacusValidationCase(
                output_stem=output_stem,
                replay_executable=replay_executable,
                build_tool_id="klee_cf",
                benchmark_selector=selector_text,
                build_preset=klee_build.preset,
                library=_validation_library_name(benchmark_definition.library_id),
            )
    return cases_by_stem


def _count_replayable_rows(json_file: Path) -> int:
    """Count rows that contain concrete A/B counterexamples worth replaying."""

    with json_file.open("r", encoding="utf-8") as handle:
        obj = json.load(handle)

    rows = obj.get("data") if isinstance(obj, dict) else obj
    if not isinstance(rows, list) or not rows:
        return 0

    replayable_rows = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        counterexamples = row.get("counterexamples")
        if isinstance(counterexamples, dict) and any(
            isinstance(key, str) and (key.endswith("__prime") or key.endswith("_prime"))
            for key in counterexamples
        ):
            replayable_rows += 1
    return replayable_rows


def _infer_sym_size(results_dir: Path, sym_size_override: int | None) -> int | None:
    """Infer sym size from the results directory name unless the caller overrides it."""

    if sym_size_override is not None:
        return sym_size_override
    suffix = results_dir.name.removeprefix("abacus_")
    if suffix.isdigit():
        return int(suffix)
    return None


def _ensure_replay_executable(case: AbacusValidationCase, sym_size: int | None) -> Path:
    """Return the replay executable for one case, building it on demand when absent."""

    replay_path = REPO_ROOT / case.replay_executable
    if replay_path.is_file() and os.access(replay_path, os.X_OK):
        return replay_path

    build_command = [
        "python",
        "-m",
        "tools.build_benchmark",
        "--tool",
        case.build_tool_id,
        "--benchmark",
        case.benchmark_selector,
        "--preset",
        _resolve_preset_name(
            case.build_preset,
            sym_size,
            owner=f"ABACUS replay build preset for {case.output_stem}",
        ),
    ]
    print(f"Replay executable not found: {replay_path}")
    print(f"$ {' '.join(build_command)}")
    if subprocess.run(build_command, cwd=REPO_ROOT, check=False).returncode != 0:
        raise SystemExit(f"failed building replay executable for {case.output_stem}")
    if not replay_path.is_file() or not os.access(replay_path, os.X_OK):
        raise SystemExit(f"Missing replay executable after build attempt: {replay_path}")
    return replay_path


def validate_results_dir(
    *,
    results_dir: Path,
    output_dir: Path,
    sym_size_override: int | None,
    timeout: int,
    pin_root: str | None,
) -> int:
    """Validate one merged ABACUS results directory in place or into another output dir."""

    case_index = _build_case_index()
    sym_size = _infer_sym_size(results_dir, sym_size_override)
    replayed_files = 0
    replayed_rows = 0

    if not results_dir.is_dir():
        raise SystemExit(f"results directory not found: {results_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(results_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in {results_dir}")

    for json_file in json_files:
        output_stem = json_file.stem
        try:
            case = case_index[output_stem]
        except KeyError as error:
            raise SystemExit(
                f"unknown ABACUS JSON output {json_file.name!r}; no registry-backed case matches this stem"
            ) from error

        output_json = output_dir / json_file.name
        replayable_rows = _count_replayable_rows(json_file)
        if replayable_rows == 0:
            print(f"Skipping JSON with no replayable counterexamples: {json_file.name}")
            if output_json.resolve() != json_file.resolve():
                shutil.copyfile(json_file, output_json)
            continue

        replay_executable = _ensure_replay_executable(case, sym_size)
        print(f"Validating {json_file.name} ({replayable_rows} replayable row(s)) with {replay_executable}")
        reproduce_return_code = reproduce_abacus_json_positives(
            input_json=str(json_file),
            executable=str(replay_executable),
            sym_size=sym_size if sym_size is not None else 0,
            timeout=timeout,
            output=str(output_json),
            library=case.library,
            pin_root=pin_root,
        )
        if reproduce_return_code != 0:
            return reproduce_return_code
        replayed_files += 1
        replayed_rows += replayable_rows

    if replayed_files == 0:
        print(
            "Validation scanned "
            f"{len(json_files)} JSON file(s) under {results_dir} but found no replayable counterexamples; no replay executions were run."
        )
    else:
        print(
            f"Validated {replayed_files} JSON file(s) with {replayed_rows} replayable row(s); outputs written to {output_dir}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for validating one ABACUS results directory."""

    parser = argparse.ArgumentParser(description="Validate one ABACUS results directory on the host.")
    parser.add_argument("--results-dir", default="results/abacus_results", help="Input directory of ABACUS JSON files")
    parser.add_argument("--output-dir", help="Output directory for validated JSON files (default: in-place)")
    parser.add_argument("--sym-size", type=int, help="Override sym size instead of inferring it from results-dir")
    parser.add_argument("--timeout", type=int, default=300, help="Replay timeout in seconds (default: 300)")
    parser.add_argument("--pin-root", default=None, help="Path to external Intel Pin kit (defaults to PIN_ROOT)")
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else results_dir
    return validate_results_dir(
        results_dir=results_dir,
        output_dir=output_dir,
        sym_size_override=args.sym_size,
        timeout=args.timeout,
        pin_root=args.pin_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())