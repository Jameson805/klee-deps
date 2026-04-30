# KLEE Constant-Time Analysis Workspace

This repository is an experiment workspace for comparing several timing side-channel analyses on the same benchmark wrappers. It contains benchmark integrations, modified KLEE builds, baseline tools, and the scripts that build per-tool artifacts, run experiments, normalize raw outputs, and merge the results into comparable reports.

The current comparison pipeline is centered on constant-time violations that show up as secret-dependent control-flow or memory behavior. In practice, the workspace is used to run the same benchmark families under multiple engines, then line up the findings by source location and compare what each engine reports.

## What This Repository Contains

The main benchmark families currently wired into the experiment runners are:

- Mbed TLS 3.2.1
- Libgcrypt 1.10.1 with libgpg-error
- OpenSSL 1.1.1q
- selected BearSSL cases

There are also additional prototype or auxiliary benchmark directories in the workspace, but the top-level runners above are the core comparison set.

The engines and baselines compared here include:

- `klee-controlflow`: the main modified KLEE tree used for the control-flow-oriented constant-time analysis
- `klee-eager`: a second modified KLEE tree evaluated as a separate KLEE-based configuration
- self-composition runs driven by KLEE and branch-recording instrumentation
- BINSEC
- ABACUS
- checked-in CtChecker result sets used as an external comparison baseline during reporting

## How The Repository Generally Works

At a high level, the workflow is:

1. Pick a benchmark family, engine, and preset or symbolic-input size.
2. Build the benchmark in the mode needed by that engine.
3. Run the engine-specific experiment script.
4. Convert raw logs or output directories into a shared JSON schema.
5. Merge repeated runs and configurations into CSV or JSON tables keyed by source location.
6. Optionally replay reported positives under Intel Pin to check whether they reproduce.
7. Compare the resulting locations against CtChecker or other baselines.

The important detail is that the benchmark wrappers are shared across tools. Each benchmark `build.sh` materializes exactly one preset from a runner config, generates benchmark-local artifacts, and then emits the binaries or bitcode needed for one mode such as KLEE, self-composition, BINSEC, or ABACUS. That keeps the tool comparison anchored to the same input layout and wrapper logic instead of maintaining unrelated harnesses for each engine.

## Shared Runner Model

The common harness layer lives in `include/runner.h`, and benchmark-specific materialization is driven by `tools/generate_runner_artifacts.py` plus configs under `configs/runner`.

For a given preset, the generator writes benchmark-local artifacts such as:

- `generated/runner_config.generated.h`
- generated BINSEC cfg files when the benchmark is built in BINSEC mode
- preset-specific constants and default public values used by the shared runner contract

That generated header is then included by the benchmark entrypoint so the same wrapper can be rebuilt into different analysis modes. Most benchmark integrations expose a combination of:

- KLEE bitcode for symbolic execution
- replay executables for counterexample checking
- BINSEC binaries and cfg inputs
- ABACUS binaries
- self-composition bitcode

## Modified KLEE Trees And Support Passes

The repository keeps multiple KLEE trees because they represent different implementations or reference points rather than one interchangeable build:

- `klee-controlflow` is the primary modified KLEE used by `scripts/experiments/run_klee_cf.sh`. This is the tree that emits the branch and memory-side-channel findings later consumed by the converters and replay tooling.
- `klee-eager` is a separate modified KLEE used by `scripts/experiments/run_klee_eager.sh`. It is evaluated as a distinct analysis configuration rather than as a drop-in rebuild of the control-flow tree.
- `klee-orig` is an in-repo upstream or reference KLEE copy kept for comparison and patch development. The main experiment scripts do not currently drive it directly.

Two LLVM passes in this repository also participate in the workflow:

- `loop-limiter` bounds loop exploration before KLEE runs so experiments stay tractable.
- `branch-recorder` instruments benchmark bitcode so self-composition runs can compare branch decisions at source locations.

## Main Experiment Entry Points

The scripts under `scripts/experiments` are the primary entry points for actual runs:

- `run_klee_cf.sh`: runs the `klee-controlflow` variant across selected benchmarks and writes raw outputs under `results/klee_cf_results`
- `run_klee_eager.sh`: runs the `klee-eager` variant and writes to `results/klee_eager_results`
- `run_self_comp.sh`: runs the self-composition baseline, converts logs to JSON, and can replay positives
- `run_binsec.sh`: builds static replayable binaries, runs BINSEC, and converts results into the common JSON schema
- `run_abacus.sh`: runs the ABACUS prototype for supported benchmarks
- `run_experiments.sh`: launches larger KLEE, self-comp, and BINSEC campaigns across many configurations, using `parallel_klee_copies.sh` to isolate heavy runs in temporary workspace copies, then performs the postprocessing steps
- `run_experiments_abacus.sh`: orchestrates ABACUS-only experiment batches and merges per-size JSON outputs

The high-level campaign runner is important because it reflects how the repository is normally used in practice: not just one run at a time, but sweeps over symbolic sizes, search strategies, and tool configurations, followed by aggregation.

## Results, Conversion, And Comparison

Each engine writes raw outputs into its own subdirectory under `results`. Those raw artifacts are then normalized into a shared schema defined in `tools/shared/result_schema.py`, which is what allows cross-tool and cross-run comparison.

The processing stack is split by responsibility:

- `tools/converters`: turns raw KLEE, self-comp, BINSEC, or ABACUS outputs into the shared JSON format
- `tools/postprocess/merge_json_runs_by_experiment.py`: merges repeated runs for one experiment configuration
- `tools/postprocess/merge_results.py`: combines many per-run JSON files into comparison CSVs keyed by source location
- `tools/postprocess/apply_sliced_map.py`, `merge_csv_by_location.py`, and `filter_merged_results.py`: relabel sliced benchmarks, combine tables, and filter locations
- `tools/postprocess/summarize_reproduction_status.py`: summarizes whether reported positives reproduced; with `--selection-csv` it writes selected best-of status tables, and with `--by-library-selection-tables` it also writes a per-library success-count matrix ordered as `KLEE-CF | other KLEE-based | external`
- `tools/postprocess/reproduce_positives.py`: replays positive findings with the repository's Intel Pin tracer in `pin-tracer`

CtChecker is handled as an external baseline rather than as a runner in this repository. Checked-in CtChecker outputs live under `ctchecker_results`, and helper scripts such as `tools/converters/compare_with_ctchecker.py`, `tools/postprocess/make_report.py`, and `tools/postprocess/make_plot.py` join those baseline results with KLEE-derived outputs for reporting.

## Directory Guide

- `benchmarks/`: vendored benchmark code plus benchmark-local wrappers and build scripts
- `klee-controlflow/`, `klee-eager/`, `klee-orig/`: KLEE source trees used for modified or reference builds
- `branch-recorder/`, `loop-limiter/`: LLVM passes used by the experiment pipeline
- `configs/binsec/`: shared BINSEC config inputs
- `configs/postprocess/`: checked-in CSV inputs for relabeling, filtering, and result selection
- `configs/runner/`: runner config inputs used to generate benchmark-local artifacts
- `include/runner.h`: shared runner harness contract used by benchmark entrypoints
- `scripts/experiments/`: main experiment runners and batch orchestration scripts
- `scripts/validation/`: validation helpers for generated outputs
- `tools/converters/`: raw-output to shared-schema converters
- `tools/postprocess/`: merge, filter, report, and replay utilities
- `tools/shared/`: shared Python modules and result schema definitions
- `pin-tracer/`: repository-owned Intel Pin tracer used for replay-based validation
- `ctchecker_results/`: checked-in CtChecker result sets used as a reporting baseline
- `results/`: generated experiment outputs, typically ignored by git
- `tests/`: fixtures for repository tooling

## Notes

- Most scripts resolve paths from repository root and write outputs under `results`.
- Benchmark build entry points remain inside each benchmark directory, for example `benchmarks/mbedtls-3.2.1/build.sh`.
- Python tooling prefers the local virtual environment at `.venv` when available.
- Replay reproduction uses Intel Pin instead of GDB. Point the workflow at an external Pin kit with `--pin-root <path>` or `PIN_ROOT=<path>`.
- Support varies slightly by benchmark family. For example, some KLEE runs have sliced variants, BearSSL uses benchmark-local runner configs with `default` presets, and CtChecker data is not available for every benchmark.
- Repo-owned glue files such as wrappers, benchmark-local `build.sh` scripts, runner configs, and checked-in placeholder JSONs should end with a trailing newline.
- Imported benchmark sources, vendored data files, and raw input blobs should be kept byte-for-byte as imported unless there is a task-specific reason to modify them.
