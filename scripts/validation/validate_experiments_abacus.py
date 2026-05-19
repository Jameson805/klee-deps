#!/usr/bin/env python3
"""Validate one or more merged ABACUS experiment directories.

This is the host-side wrapper used by the ABACUS campaign orchestrator after it
merges per-copy JSON files into `abacus_<sym>` directories. It exists so the
campaign runner can invoke the same validation flow for one or many sym sizes.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.validate_abacus import validate_results_dir


def _run_one(output_base: Path, sym_size: int) -> int:
    """Validate one merged `abacus_<sym>` directory under the output root."""

    results_dir = output_base / f"abacus_{sym_size}"
    print(f"[VALIDATE SYM {sym_size}] validating {results_dir}")
    rc = validate_results_dir(
        results_dir=results_dir,
        output_dir=results_dir,
        sym_size_override=sym_size,
        timeout=300,
        pin_root=None,
    )
    if rc == 0:
        print(f"[VALIDATE SYM {sym_size}] done")
    return rc


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for validating one or more ABACUS sym sizes."""

    parser = argparse.ArgumentParser(description="Validate one or more ABACUS experiment outputs.")
    parser.add_argument(
        "--output-base",
        default=str(Path(__file__).resolve().parents[2] / "results" / "abacus_experiments"),
        help="Output root containing abacus_<sym> directories",
    )
    parser.add_argument(
        "--sym-size",
        type=int,
        action="append",
        dest="sym_sizes",
        help="Sym size to validate (repeatable; default: 4 and 16)",
    )
    parser.add_argument("--parallel", action="store_true", help="Validate selected sym sizes in parallel")
    parser.add_argument("--sequential", action="store_true", help="Validate selected sym sizes sequentially")
    args = parser.parse_args(argv)

    output_base = Path(args.output_base).expanduser().resolve()
    if not output_base.is_dir():
        raise SystemExit(f"output base directory not found: {output_base}")

    sym_sizes = args.sym_sizes or [4, 16]
    if args.parallel and args.sequential:
        raise SystemExit("--parallel and --sequential are mutually exclusive")

    if args.parallel:
        with ThreadPoolExecutor(max_workers=len(sym_sizes)) as executor:
            futures = [executor.submit(_run_one, output_base, sym_size) for sym_size in sym_sizes]
            for future in futures:
                rc = future.result()
                if rc != 0:
                    return rc
    else:
        for sym_size in sym_sizes:
            rc = _run_one(output_base, sym_size)
            if rc != 0:
                return rc

    print(f"All requested Abacus validations completed under: {output_base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())