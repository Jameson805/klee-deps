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
5. Merge repeated runs and configurations into per-configuration JSON plus comparison CSV tables keyed by source location.
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

- `klee-controlflow` is the primary modified KLEE used by `python -m scripts.experiments.run_klee_cf`. This is the tree that emits the branch and memory-side-channel findings later consumed by the converters and replay tooling.
- `klee-eager` is a separate modified KLEE used by `python -m scripts.experiments.run_klee_eager`. It is evaluated as a distinct analysis configuration rather than as a drop-in rebuild of the control-flow tree.
- `klee-orig` is an in-repo upstream or reference KLEE copy kept for comparison and patch development. The main experiment scripts do not currently drive it directly.

Two LLVM passes in this repository also participate in the workflow:

- `loop-limiter` bounds loop exploration before KLEE runs so experiments stay tractable.
- `branch-recorder` instruments benchmark bitcode so self-composition runs can compare branch decisions at source locations.

## Main Experiment Entry Points

The scripts under `scripts/experiments` are the primary entry points for actual runs:

Run all repository-owned Python CLIs from the repository root with `python -m ...`. Experiment runners live under `scripts.experiments`, converters live under `tools.converters`, and postprocess tools live under `tools.postprocess`. Direct filename execution is no longer the supported interface.

Examples:

- `python -m scripts.experiments.run_klee_cf 1m --sym-size 4 --benchmarks mbedtls`
- `python -m scripts.experiments.run_klee_cf 4h --sym-size 4`
- `python -m scripts.experiments.run_experiments configs/experiments/run_experiments.toml`
- `python -m scripts.experiments.run_experiments_abacus configs/experiments/run_experiments_abacus.toml`
- `python -m scripts.experiments.run_experiments --postprocess-only configs/experiments/run_experiments.toml`
- `python -m tools.postprocess.summarize_reproduction_status results/... --output summary.csv`
- `python -m tools.postprocess.compare_with_ctchecker branch ctchecker.json klee.json combined.json`

- `run_klee_cf.py`: runs the `klee-controlflow` variant across selected benchmarks and writes raw outputs under `results/klee_cf_results`
- `run_klee_eager.py`: runs the `klee-eager` variant and writes to `results/klee_eager_results`
- `run_self_comp.py`: runs the self-composition baseline, converts logs to JSON, and can replay positives
- `run_binsec.py`: builds static replayable binaries, runs BINSEC, and converts results into the common JSON schema
- `run_abacus.py`: runs the ABACUS prototype for supported benchmarks
- `run_experiments.py`: launches larger KLEE, self-comp, and BINSEC campaigns across many configurations, using `parallel_klee_copies.py` to isolate heavy runs in temporary workspace copies, then performs the postprocessing steps based on `configs/experiments/run_experiments.toml`; both the benchmark selection and the campaign run-definition matrix now live in TOML rather than in the script
- `run_experiments_abacus.py`: orchestrates ABACUS-only experiment batches and merges per-size JSON outputs based on `configs/experiments/run_experiments_abacus.toml`

The high-level campaign runner is important because it reflects how the repository is normally used in practice: not just one run at a time, but sweeps over symbolic sizes, search strategies, and tool configurations, followed by aggregation.

## Experiment Script Style

The experiment runners are intentionally written in a fairly direct style:

- keep tool-specific parsing and validation in the runner that uses it instead of pushing it into shared helper layers too early
- prefer one readable orchestration function over several one-use utilities when the extra indirection does not buy much reuse
- add short comments for overall phase structure and for design choices that are non-obvious, especially around workspace isolation, replay naming, and cleanup behavior
- keep generated or edited source-like files newline-terminated so `git diff --check` stays clean

### Common Runner Examples

Run only the Mbed TLS benchmark with KLEE-CF for one minute:

```bash
python -m scripts.experiments.run_klee_cf 1m --sym-size 4 --benchmarks mbedtls
```

That command selects the `mbedtls` benchmark group from the shared benchmark registry and writes the raw run under `results/klee_cf_results`.

Run the full checked-in campaign config:

```bash
python -m scripts.experiments.run_experiments configs/experiments/run_experiments.toml
```

Run only the merge and reporting steps for an already-finished campaign directory:

```bash
python -m scripts.experiments.run_experiments --postprocess-only configs/experiments/run_experiments.toml
```

### Configuring `run_experiments.py`

`python -m scripts.experiments.run_experiments <config.toml>` reads four top-level sections from the campaign TOML:

- `[campaign]`: global paths and timeouts used by the whole batch, including `output`, `run_time`, `run_time_seconds`, `klee_root`, the checked-in postprocess CSV inputs, and optional postprocess output prefixes such as `aggregate_output_prefix` and `by_library_output_prefix`
- `[benchmarks]`: optional per-tool benchmark filters; empty arrays mean "use that tool's default benchmark set"
- `[runs]`: booleans that turn individual named campaign entries on or off
- `[run_definitions.<name>]`: the command template and output routing for each named run; these usually stay checked in and you mostly customize `[campaign]`, `[benchmarks]`, and `[runs]`

The checked-in `configs/experiments/run_experiments.toml` uses these command-template placeholders inside each `run_definitions.*.command` array:

- `{python_bin}`
- `{run_time}`
- `{run_time_seconds}`
- `{klee_root}`

In practice, the common workflow is to copy `configs/experiments/run_experiments.toml`, adjust a few global values, narrow the benchmark lists, and disable the runs you do not want.

For example, a one-minute Mbed TLS-focused campaign can start from this TOML excerpt:

```toml
[campaign]
num_copies = 10
temp_dir = "/datapool/theta-lin-experiments/tmp"
output = "/tmp/mbedtls-klee-cf-1m"
run_time = "1m"
run_time_seconds = 60
klee_root = "/home/theta-lin/klee/build/bin"
sliced_map_csv = "configs/postprocess/sliced_map.csv"
filtered_locations_csv = "configs/postprocess/filtered_locations.csv"
ideal_config_selection_csv = "configs/postprocess/ideal_config_selection.csv"
aggregate_output_prefix = "aggregated"
by_library_output_prefix = "filtered_reproduction_status_by_library"

[benchmarks]
klee_cf = ["mbedtls"]
klee_eager = []
self_comp = []
binsec = []

[runs]
klee_cf_default_4 = true
klee_cf_default_16 = false
klee_cf_dfs_4 = false
klee_cf_dfs_16 = false
klee_cf_rand_path_dfs_4 = false
klee_cf_rand_path_dfs_16 = false
klee_cf_no_conc_4 = false
klee_eager_default_4 = false
klee_eager_default_16 = false
klee_eager_dfs_4 = false
klee_eager_dfs_16 = false
klee_eager_rand_path_dfs_4 = false
klee_eager_rand_path_dfs_16 = false
self_comp_default_4 = false
self_comp_default_16 = false
self_comp_dfs_4 = false
self_comp_dfs_16 = false
self_comp_rand_path_dfs_4 = false
self_comp_rand_path_dfs_16 = false
binsec_4 = false
binsec_16 = false
```

Then run it as:

```bash
python -m scripts.experiments.run_experiments path/to/your_mbedtls_1m.toml
```

If you want the same benchmark restriction across every enabled tool, set `all = ["mbedtls"]` instead of per-tool arrays under `[benchmarks]`.

### Configuring Benchmark Descriptors

Benchmark descriptors live under `configs/benchmarks/` and are loaded through `tools/shared/experiment_registry.py`.

For benchmarks that repeat the same case structure across `fix_pub` and `var_pub`, prefer the compact matrix form:

```toml
[benchmarks.mode_case_templates]
abacus_executable = "benchmarks/example/abacus_{public_mode}_{artifact_suffix}"
self_comp_bitcode = "benchmarks/example/self_comp_{public_mode}_{artifact_suffix}.bc"
self_comp_replay_executable = "klee_{public_mode}_replay_{artifact_suffix}"
binsec_sse_script = "benchmarks/example/generated/{artifact_suffix}/binsec_{public_mode}.cfg"
binsec_executable = "benchmarks/example/binsec_{public_mode}_{artifact_suffix}"
klee_bitcode = "benchmarks/example/klee_{public_mode}_{artifact_suffix}.bc"
klee_replay_script = "benchmarks/example/klee_{public_mode}_replay_{artifact_suffix}"

[[benchmarks.mode_cases]]
display_name = "Example"
artifact_suffix = "example"
output_stem = "example_case"
replay_opts = "--secret key,data"
ct_json = "ctchecker_results/OriginalBenchmarks/empty.json"
memory_flag = true
secret_layout = "key:16,data:16"
secret_inputs = ["key:16:key_buf", "data:16:data_buf"]
runner_config = "configs/runner/example_runner_config.toml"
preset_name = "default"
```

The registry expands each `mode_cases` entry into the concrete `abacus_cases`, `self_comp_cases`, `binsec_cases`, and `klee_cases` at load time. Use explicit per-tool case arrays only when one benchmark variant really does not follow the shared pattern.

## Results, Conversion, And Comparison

Each engine writes raw outputs into its own subdirectory under `results`. Those raw artifacts are then normalized into a shared schema defined in `tools/shared/result_schema.py`, which is what allows cross-tool and cross-run comparison.

Campaign runs now also emit explicit metadata alongside the raw data:

- each campaign output root contains `_run_metadata.json`, which records the configuration for each run directory
- each merged CSV can carry a `*.metadata.json` sidecar that records the exact metadata for every result column

The postprocess pipeline now expects those metadata files when it is operating on campaign-generated outputs. Helper steps such as filtering, sliced relabeling, and CSV merges preserve the sidecars when they are present.

The shared JSON rows now use one canonical side-channel field: `kind`, whose value is always either `branch` or `memory`. No converter or postprocess step should rely on legacy field names or JSON filename suffixes to recover this information.

Two caveats are worth knowing when reading those normalized JSON files:

- `self_comp` is currently branch-only. The benchmark build scripts instrument self-composition bitcode with `record_branch`, and `tools/converters/self_comp_log_to_json.py` only parses `NON-CT BRANCH` log records, so every self-comp positive is emitted with `kind = "branch"`.
- `abacus` does not report branch-vs-memory explicitly in its raw logs. `tools/converters/abacus_log_to_json.py` infers `kind` from the divergent instruction by disassembling the executable with `objdump`; if that instruction cannot be classified cleanly as branch or memory, conversion fails.

The processing stack is split by responsibility:

- `tools/converters`: turns raw KLEE, self-comp, BINSEC, or ABACUS outputs into the shared JSON format; invoke converter CLIs as `python -m tools.converters.<name>`
- `python -m tools.postprocess.merge_json_runs_by_experiment`: merges repeated runs for one experiment configuration and retains all positives with non-null `non_ct_time`, aggregating `reproduced_status` as status-count maps
- `python -m tools.postprocess.merge_results`: combines many per-run JSON files into comparison CSVs keyed by source location; by default it keeps only locations whose merged `reproduced_status` includes at least one success, and `--all-positives` widens that to every positive with non-null `non_ct_time`
- `python -m tools.postprocess.apply_sliced_map`, `python -m tools.postprocess.merge_csv_by_location`, and `python -m tools.postprocess.filter_merged_results`: relabel sliced benchmarks, combine tables, and filter locations; libraries absent from `filtered_locations.csv` pass through unchanged, while listed libraries are restricted to the configured line ranges
- `python -m tools.postprocess.aggregate_experiment_groups`: writes aggregate configuration summaries, exploration cactus plots, a generated one-best-configuration-per-tool selection based on `insecure_locations_found` then `max_time`, and selected-configuration comparison plots; `--selection-csv` still overrides the automatic choice
- `python -m tools.postprocess.summarize_reproduction_status`: summarizes whether reported positives reproduced; with `--selection-csv` it writes selected best-of status tables, and with `--by-library-selection-tables` it also writes a per-library success-count matrix ordered as `KLEE-CF | other KLEE-based | external`
- `python -m tools.postprocess.reproduce_positives`: replays positive findings with the repository's Intel Pin tracer in `pin-tracer`

Current TODOs worth keeping in mind:

- finish converting the remaining verbose benchmark descriptor TOMLs onto `mode_cases` / `mode_case_templates`
- add a broader end-to-end campaign smoke test that exercises `_run_metadata.json` and CSV sidecar propagation together
- clean incidental local artifacts such as stray `pinos.log.*` files before landing large experiment-runner changes

CtChecker is handled as an external baseline rather than as a runner in this repository. Checked-in CtChecker outputs live under `ctchecker_results`, and helper scripts such as `python -m tools.converters.klee_log_to_json`, `python -m tools.postprocess.compare_with_ctchecker`, and `python -m tools.postprocess.make_report` join those baseline results with KLEE-derived outputs for reporting.

## Directory Guide

- `benchmarks/`: vendored benchmark code plus benchmark-local wrappers and build scripts
- `klee-controlflow/`, `klee-eager/`, `klee-orig/`: KLEE source trees used for modified or reference builds
- `branch-recorder/`, `loop-limiter/`: LLVM passes used by the experiment pipeline
- `configs/binsec/`: shared BINSEC config inputs
- `configs/benchmarks/`: per-benchmark descriptor TOMLs scanned by `tools/shared/experiment_registry.py`; the shared registry reads only generic benchmark fields and build metadata, while each runner parses its own raw tool-specific sections from these files
- `configs/postprocess/`: checked-in CSV inputs for relabeling, filtering, and result selection
- `configs/experiments/`: campaign-level TOML configs for batch runners
- `configs/runner/`: runner config inputs used to generate benchmark-local artifacts
- `include/runner.h`: shared runner harness contract used by benchmark entrypoints
- `scripts/experiments/`: main experiment runners and batch orchestration scripts
- `scripts/validation/`: validation helpers for generated outputs
- `tools/converters/`: raw-output to shared-schema converters
- `tools/postprocess/`: merge, filter, report, and replay utilities
- `tools/shared/`: shared Python modules, the generic benchmark registry, and result schema definitions
- `pin-tracer/`: repository-owned Intel Pin tracer used for replay-based validation
- `ctchecker_results/`: checked-in CtChecker result sets used as a reporting baseline
- `results/`: generated experiment outputs, typically ignored by git
- `tests/`: fixtures for repository tooling

## Adding A Tool

The intended split is now:

- `tools/shared/experiment_registry.py` and `tools/shared/registry/` own only generic benchmark data: benchmark ids, display names, path inference metadata, supported runner ids, and build metadata.
- Each runner under `scripts/experiments/` owns its own case dataclasses, validation, and parsing of its tool-specific benchmark config sections.

That means adding one more tool should usually not require changing the shared registry code.

If you want to add a new tool runner, do the following:

1. Create a new runner entry point under `scripts/experiments/`, for example `run_my_tool.py`, and run it from repo root as `python -m scripts.experiments.run_my_tool ...`.
2. Pick one runner id, for example `my_tool`, and use that exact string consistently in the runner and benchmark TOMLs.
3. In the runner, select benchmarks with `selected_benchmarks("my_tool", args.benchmarks)` and resolve generic benchmark metadata with `benchmark_definition(...)`, `benchmark_build_for_tool(...)`, `library_for_path(...)`, and `code_path_for_executable(...)` as needed.
4. Keep the tool-specific shapes in the runner itself. The runner should define its own case dataclasses and parse raw sections from `definition.extra_config`. Use `definition.config_location` plus helpers from `tools.shared.registry.parsing` for consistent error messages when validating those sections.
5. In each supported benchmark descriptor under `configs/benchmarks/`, add `"my_tool"` to the benchmark's `tools` list and add a generic build section:

```toml
[benchmarks.builds.my_tool]
script = "benchmarks/example/build.sh"
tool_flag = "--my-tool"
preset = "default"
```

6. Add whatever raw tool-specific sections the runner expects. The shared registry does not interpret these sections; it only preserves them in `BenchmarkDefinition.extra_config`. For example:

```toml
[[benchmarks.my_tool_cases]]
title = "Example case"
input = "benchmarks/example/example.bc"
output = "example.json"
```

7. If the new tool should participate in batch campaigns, add the corresponding entry points or run definitions to `scripts/experiments/run_experiments.py`, `scripts/experiments/run_experiments_abacus.py`, or `configs/experiments/*.toml` as appropriate.
8. Validate the new tool with at least:

```bash
python -m scripts.experiments.run_my_tool --help
python -m tools.shared.experiment_registry benchmark-list --tool my_tool --format csv
```

The one common exception is shared build aliases. Today `klee_cf` and `klee_eager` intentionally share the benchmark-local build key `builds.klee`. If a new tool needs a similar alias instead of a one-to-one `builds.<runner_id>` mapping, then `benchmark_build_for_tool()` in `tools/shared/registry/core.py` is the only shared-registry function that should need adjustment.

## Notes

- Most scripts resolve paths from repository root and write outputs under `results`.
- Benchmark build entry points remain inside each benchmark directory, for example `benchmarks/mbedtls-3.2.1/build.sh`.
- Python tooling prefers the local virtual environment at `.venv` when available.
- Python orchestration code in this repository prefers longer functions over many small helpers; factor code out only when logic is reused or nesting would otherwise become too deep.
- Replay reproduction uses Intel Pin instead of GDB. Point the workflow at an external Pin kit with `--pin-root <path>` or `PIN_ROOT=<path>`.
- Support varies slightly by benchmark family. For example, some KLEE runs have sliced variants, BearSSL uses benchmark-local runner configs with `default` presets, and CtChecker data is not available for every benchmark.
- Repo-owned glue files such as wrappers, benchmark-local `build.sh` scripts, runner configs, and checked-in placeholder JSONs should end with a trailing newline.
- Imported benchmark sources, vendored data files, and raw input blobs should be kept byte-for-byte as imported unless there is a task-specific reason to modify them.
