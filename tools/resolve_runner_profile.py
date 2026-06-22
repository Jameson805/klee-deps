#!/usr/bin/env python3
"""Resolve benchmark-owned runner profiles for the shared builder and tooling."""

from __future__ import annotations

import argparse

from scripts.experiments.common import resolve_repo_path
from tools.shared.experiment_registry import definition, runner_profile_for_definition


def parse_format_values(values: list[str]) -> dict[str, str]:
    """Parse repeated ``--format KEY=VALUE`` options."""
    formatted: dict[str, str] = {}
    for value in values:
        key, separator, raw_value = value.partition("=")
        if not separator or not key:
            raise ValueError(f"invalid --format value {value!r}; expected KEY=VALUE")
        formatted[key] = raw_value
    return formatted


def main(argv: list[str] | None = None) -> int:
    """Resolve one benchmark-owned runner profile field for shell tooling."""
    parser = argparse.ArgumentParser(description="Resolve a benchmark runner profile field.")
    parser.add_argument("--library", required=True, help="Benchmark library id from configs/benchmarks")
    parser.add_argument("--target", required=True, help="Benchmark target id from configs/benchmarks")
    parser.add_argument("--profile", help="Runner profile id; omit only when the benchmark defines one profile")
    parser.add_argument("--field", choices=("config", "preset", "profile"), default="config")
    parser.add_argument(
        "--format",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Template value used when formatting the selected field",
    )
    args = parser.parse_args(argv)

    try:
        resolved_profile_id, runner_profile = runner_profile_for_definition(
            definition(args.library, args.target),
            args.profile,
        )
        if args.field == "profile":
            value = resolved_profile_id
        elif args.field == "config":
            value = str(resolve_repo_path(runner_profile.config))
        else:
            value = runner_profile.preset
            if value:
                value = value.format(**parse_format_values(args.format))
        print(value)
    except ValueError as error:
        parser.error(str(error))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
