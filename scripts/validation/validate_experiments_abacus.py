#!/usr/bin/env python3
"""Validate one or more merged ABACUS experiment directories.

This is the host-side wrapper used by the ABACUS campaign orchestrator after it
merges per-copy JSON files into `abacus_<bucket>` directories. It exists so the
campaign runner can invoke the same validation flow for one or many output buckets.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.validation.validate_abacus import validate_results_dir


def _parse_bucket_sym_size(bucket: str) -> int | None:
    """Interpret a bucket label as a sym size when it is numeric."""
    return int(bucket) if bucket.isdigit() else None


def _discover_buckets(output_base: Path) -> list[str]:
    """Discover available ABACUS output buckets under one campaign root."""
    buckets = sorted(
        child.name.removeprefix("abacus_")
        for child in output_base.iterdir()
        if child.is_dir() and child.name.startswith("abacus_")
    )
    if not buckets:
        raise SystemExit(f"no abacus_* directories found under {output_base}")
    return buckets


def _run_one(output_base: Path, bucket: str, debug: bool) -> int:
    """Validate one merged `abacus_<bucket>` directory under the output root."""

    results_dir = output_base / f"abacus_{bucket}"
    print(f"[VALIDATE {bucket}] validating {results_dir}")
    rc = validate_results_dir(
        results_dir=results_dir,
        output_dir=results_dir,
        sym_size_override=_parse_bucket_sym_size(bucket),
        timeout=300,
        pin_root=None,
        debug=debug,
    )
    if rc == 0:
        print(f"[VALIDATE {bucket}] done")
    return rc


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for validating one or more ABACUS output buckets."""

    parser = argparse.ArgumentParser(description="Validate one or more ABACUS experiment outputs.")
    parser.add_argument(
        "--output-base",
        default=str(Path(__file__).resolve().parents[2] / "results" / "abacus_experiments"),
        help="Output root containing abacus_<sym> directories",
    )
    parser.add_argument(
        "--bucket",
        action="append",
        dest="buckets",
        help="Bucket label to validate (repeatable; default: autodiscover abacus_* directories)",
    )
    parser.add_argument(
        "--sym-size",
        type=int,
        action="append",
        dest="sym_sizes",
        help="Deprecated numeric bucket selector kept for compatibility",
    )
    parser.add_argument("--parallel", action="store_true", help="Validate selected sym sizes in parallel")
    parser.add_argument("--sequential", action="store_true", help="Validate selected sym sizes sequentially")
    parser.add_argument("--debug", action="store_true", help="Print per-row validation decisions and replay locations")
    args = parser.parse_args(argv)

    output_base = Path(args.output_base).expanduser().resolve()
    if not output_base.is_dir():
        raise SystemExit(f"output base directory not found: {output_base}")

    bucket_labels = args.buckets or ([str(sym_size) for sym_size in args.sym_sizes] if args.sym_sizes else None)
    if bucket_labels is None:
        bucket_labels = _discover_buckets(output_base)
    if args.parallel and args.sequential:
        raise SystemExit("--parallel and --sequential are mutually exclusive")

    if args.parallel:
        with ThreadPoolExecutor(max_workers=len(bucket_labels)) as executor:
            futures = [executor.submit(_run_one, output_base, bucket, args.debug) for bucket in bucket_labels]
            for future in futures:
                rc = future.result()
                if rc != 0:
                    return rc
    else:
        for bucket in bucket_labels:
            rc = _run_one(output_base, bucket, args.debug)
            if rc != 0:
                return rc

    print(f"All requested Abacus validations completed under: {output_base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())