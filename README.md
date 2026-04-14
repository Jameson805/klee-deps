# KLEE Constant-Time Analysis Workspace

This repository contains experimental infrastructure for evaluating constant-time behavior with multiple engines and benchmark suites.

## Layout

- benchmarks: vendored benchmark codebases used for experiments
  - bearssl-0.6
  - mbedtls-3.2.1
  - openssl-1.1.1q
  - libgcrypt-and-libgpg-error
- scripts/experiments: main experiment runners
  - run_klee_cf.sh
  - run_klee_eager.sh
  - run_self_comp.sh
  - run_binsec.sh
  - run_abacus.sh
  - run_experiments.sh
  - run_experiments_abacus.sh
  - parallel_klee_copies.sh
- scripts/validation: validation helpers for generated experiment outputs
- tools/postprocess: merge/filter/report utilities for collected results
- tools/converters: raw-output-to-schema converters used before postprocessing
- tools/utilities: reusable helper scripts
- tools/shared: shared Python modules
- configs/binsec: shared BINSEC execution config inputs
- configs/postprocess: checked-in CSV inputs for result relabeling and filtering
- configs/runner: shared runner config inputs reused by multiple benchmarks
- include/runner.h: shared generated-runner harness used by benchmark entrypoints
- results: generated outputs (ignored by git)
- tests: fixture assets and expected outputs for repository tooling

## Quick Notes

- Most experiment scripts resolve paths from repository root and write outputs under results.
- Benchmark build entry points remain inside each benchmark folder (for example, benchmarks/mbedtls-3.2.1/build.sh).
- Python tooling prefers the local virtual environment at .venv when available.
