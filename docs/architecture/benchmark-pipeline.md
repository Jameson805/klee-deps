# Benchmark Pipeline

This repository compares multiple tools against the same benchmark descriptors, build presets, replay surfaces, and postprocessing schema.

## End-To-End Flow

The pipeline is intentionally split into a small number of ownership boundaries.

1. A benchmark descriptor under `configs/benchmarks/` declares generic benchmark facts.
2. The shared build entrypoint `python -m tools.build_benchmark` materializes benchmark-local artifacts for one tool mode.
3. A runner under `scripts/experiments/` expands cases, launches the tool, and converts raw output into the shared JSON schema.
4. Campaign orchestration runs many exact configurations and records explicit metadata for each one.
5. Postprocessing scripts merge, filter, summarize, replay, and plot those exact configurations.

## Ownership Boundaries

The important split is:

- `tools/shared/experiment_registry.py` owns generic benchmark metadata and benchmark selection.
- `scripts/experiments/common.py` owns narrow shared runner utilities such as workspace setup, subprocess wiring, and generic argument handling.
- Each runner in `scripts/experiments/` owns tool-specific case interpretation and execution.
- Each converter in `tools/converters/` owns tool-specific raw-output normalization.
- `tools/shared/configuration_metadata.py` records raw metadata and does not decide display policy.

This keeps benchmark descriptors generic while letting runners stay explicit about tool-specific execution details.

## Benchmark Descriptors

Benchmark descriptors are keyed by `library` plus explicit `target` entries. The canonical CLI selector is always `library:target`.

The descriptor layer owns:

- benchmark identity
- supported tools
- benchmark code path
- build preset selection
- runner-profile mapping
- tool-local extra config when a runner genuinely needs it

Each target is one build/run unit. Descriptors should split algorithm,
backend, sliced, and stage differences into separate targets instead of hiding
multiple former subtargets inside one selector.

The descriptor layer should not grow a second tool-specific schema language when runner-local parsing is clearer.

## Build Stage

The build stage is driven by `python -m tools.build_benchmark`.

It uses benchmark metadata plus runner-config inputs to generate benchmark-local artifacts such as:

- compiled KLEE bitcode
- BINSEC executables
- replay binaries
- generated headers
- generated BINSEC cfg files

The build flow intentionally keeps generated artifacts benchmark-local so the outputs are inspectable and do not bleed across benchmarks.

## Runner Stage

The runner layer owns tool-specific execution.

### KLEE Family

`scripts/experiments/run_klee_cf.py`, `scripts/experiments/run_klee_eager.py`, and `scripts/experiments/run_klee_self_comp.py` are thin wrappers over the shared implementation in `scripts/experiments/run_klee_family.py`.

That shared runner handles:

- benchmark-local bitcode execution
- optional preprocessing
- KLEE output capture
- conversion through `tools.converters.klee_log_to_json`
- replay of positives through the benchmark replay executable

Mode-specific behavior is kept explicit through a small `KleeModeProfile` table instead of duplicating the orchestration flow.

### BINSEC

`scripts/experiments/run_binsec.py` owns the BINSEC flow:

- benchmark-local executable and cfg selection
- BINSEC invocation
- TOML-to-JSON conversion through `tools.converters.binsec_toml_to_json`
- replay integration when a replay executable is available

## Conversion Stage

The shared result schema is in `tools/shared/result_schema.py`.

Converters normalize tool-local output into one common shape so downstream replay, merge, and reporting code can stay tool-agnostic.

Important converter responsibilities:

- retain tool-local evidence needed for replay or debugging
- normalize finding kind and source location into the shared schema
- leave raw metadata raw rather than inventing display labels too early

## Campaign Metadata And Postprocessing

Campaign outputs record exact run metadata. Postprocessing works from those exact configuration columns rather than from inferred or normalized labels.

Important commands:

- `python -m tools.postprocess.merge_json_runs_by_experiment <dir>`
- `python -m tools.postprocess.merge_results <dir>`
- `python -m tools.postprocess.apply_sliced_map ...`
- `python -m tools.postprocess.filter_merged_results ...`
- `python -m tools.postprocess.aggregate_experiment_groups ...`
- `python -m tools.postprocess.summarize_reproduction_status ...`
- `python -m tools.postprocess.reproduce_positives ...`

## Adding A Benchmark

The preferred path is:

1. Add a benchmark descriptor under `configs/benchmarks/`.
2. Add or reuse a runner profile and runner-config input.
3. Validate that existing runners can consume the generic case matrix.
4. Keep genuinely tool-specific data narrow and runner-local.

For the runner-config details, see `runner-config.md`.

## Adding A Tool

Adding a tool means:

1. Choose a stable tool id.
2. Add a runner entrypoint under `scripts/experiments/`.
3. Reuse shared benchmark expansion when the tool fits the common matrix.
4. Add the tool id to supported benchmark descriptors.
5. Add campaign support if needed.

The repository intentionally does not keep a separate hardcoded tool registry.

## Current Caveats

- KLEE-Self-Comp currently emits branch findings only through the shared conversion path.
- ABACUS infers finding kind by disassembling the divergent instruction because its raw logs do not classify branch versus memory directly.
- BINSEC needs repository-specific handling for external calls, replay, and build shape. See `../tools/binsec.md` and `../experiences/binsec-challenges.md`.