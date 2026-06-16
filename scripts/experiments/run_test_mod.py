#!/usr/bin/env python3
"""Ad hoc helper for the historical Mbed TLS test_mod experiment.

This script intentionally stays small and direct because it is a one-off manual
debugging entry point rather than part of the structured benchmark registry.
"""

from __future__ import annotations

import argparse
import os
import resource

from scripts.experiments.common import ExperimentContext, REPO_ROOT
from tools.shared.tool_artifacts import resolve_executable_path


def main() -> int:
    """Run the historical one-off Mbed TLS test_mod experiment."""
    argparse.ArgumentParser(description="Run the ad hoc test_mod KLEE experiment.").parse_args()
    limit_bytes = 70_000_000 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))

    klee_executable = str(resolve_executable_path("klee-cf"))
    script_path = REPO_ROOT / "tools" / "postprocess"
    env = dict(os.environ)
    env["PATH"] = f"{script_path}:{env.get('PATH', '')}"

    context = ExperimentContext()
    context.run(["benchmarks/mbedtls-3.2.1/build_test_mod.sh"], env=env)
    context.run(
        [
            "timeout",
            "--foreground",
            "--signal=INT",
            "--kill-after=30s",
            "10m",
            klee_executable,
            "--libc=uclibc",
            "--posix-runtime",
            "--external-calls=all",
            "--kdalloc",
            "--kdalloc-constants-size=5",
            "--kdalloc-globals-size=5",
            "--kdalloc-heap-size=20",
            "--kdalloc-stack-size=10",
            "--dump-states-on-halt=false",
            "--use-batching-search=false",
            "--search=random-path",
            "--search=nurs:covnew",
            "--use-cv-model=true",
            "--max-solver-time=30s",
            "--max-memory=10000",
            "benchmarks/mbedtls-3.2.1/test_mod.bc",
        ],
        env=env,
        check=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())