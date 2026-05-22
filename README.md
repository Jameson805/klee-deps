# KLEE Constant-Time Analysis Workspace

This repository is an experiment workspace for comparing multiple constant-time analyses against the same benchmark wrappers and runner contracts. It contains benchmark integrations, modified KLEE trees, baseline tools, artifact generators, converters, and postprocessing code that all feed into one shared comparison pipeline.

The current pipeline is organized around one design rule: benchmark wrappers and benchmark metadata should stay tool-agnostic wherever possible, while tool-specific execution details stay in the runner that owns them.

## Building The Toolchain

The repository now includes a root build flow for the local KLEE toolchain and the loop-limiter LLVM plugin:

```bash
./build_all.sh all
```

That flow does the following:

1. Creates or updates a conda environment from `environment-build.yml`.
2. Initializes the KLEE git submodules if needed.
3. Builds STP and `klee-uclibc` under `build/deps/`.
4. Downloads Intel Pin under `build/deps/pin` and registers the real Pin binaries in `build/tool-paths.json`.
5. Installs `opam` in the conda environment, then clones and builds BINSEC in a local opam switch under `build/deps/src/binsec` and registers the real `binsec` plus `dune` executables in `build/tool-paths.json`.
6. Configures and builds every top-level `klee-*` submodule under `build/<project>/`.
7. Builds `loop-limiter` under the same top-level build root.

For direct manual use, the build step records workspace-local tool artifacts in
`build/tool-paths.json`. KLEE variants are registered in the manifest with
distinct ids, while activation exposes convenience shell functions for each
variant name:

```bash
source ./activate-workspace.sh
klee-cf --version
klee-eager --version
klee-self-comp --version
```

Those names stay workspace-local via the manifest, so separate worktrees can
expose different KLEE builds without overwriting each other inside a shared
conda environment.

BINSEC and Pin follow the same manifest-first rule after `./build_all.sh binsec`,
`./build_all.sh pin`, or `./build_all.sh all`. The activation helper reads
`build/tool-paths.json`, prepends directories for direct executable artifacts,
defines shell aliases for manifest ids whose real binary name differs, and when
BINSEC is present enters the local opam switch for the shell session. When Intel
Pin is installed by the root build, activation also exports `PIN_ROOT` to the
workspace-local Pin kit under `build/deps/pin`.

To opt into the shared conda environment plus the current workspace's manifest-
backed tool activation for one shell session, source:

```bash
source ./activate-workspace.sh
```

Useful narrower invocations:

```bash
./build_all.sh env
./build_all.sh deps
./build_all.sh pin
./build_all.sh binsec
./build_all.sh klee --project klee-cf
./build_all.sh extras
```

The script expects a working `conda` installation on the host and uses the active conda environment to provide LLVM 16, Clang 16, CMake, Ninja, OPAM, Dune, GMP, and the Python packages used by the rest of the repository. BINSEC itself is built from source in a workspace-local OPAM root under `build/opam-root`.

## Overview

At a high level, the repository works like this:

1. A benchmark descriptor under `configs/benchmarks/` declares which tools support a benchmark variant and how that benchmark should be built.
2. A benchmark-local `build.sh` materializes artifacts for one tool mode using the shared runner contract in `include/runner.h` plus generated artifacts from `tools/generate_runner_artifacts.py`.
3. A runner under `scripts/experiments/` expands benchmark cases, launches the tool, and converts raw output into the shared JSON schema from `tools/shared/result_schema.py`.
4. Campaign orchestration scripts run many exact configurations and write explicit metadata describing every run and every merged CSV column.
5. Postprocessing scripts in `tools/postprocess/` merge, filter, summarize, and plot those exact configurations.

The important boundary is:

- `tools/shared/experiment_registry.py` owns generic benchmark metadata and benchmark selection.
- `tools/shared/campaign_tools.py` discovers available tools.
- each runner in `scripts/experiments/` owns tool-specific case interpretation and execution.
- `tools/shared/configuration_metadata.py` records raw metadata and does not decide display policy.

## Main Components

Important repository areas:

- `benchmarks/`: benchmark code, wrappers, and benchmark-local build scripts
- `configs/benchmarks/`: benchmark descriptors keyed by `library` plus explicit `variant` entries
- `configs/runner/`: runner config inputs used to generate benchmark-local headers and Binsec cfg files
- `scripts/experiments/`: per-tool runners and campaign orchestration
- `tools/shared/`: shared registry, metadata, result schema, and campaign discovery
- `tools/converters/`: raw-output to shared-schema converters
- `tools/postprocess/`: merge, replay, summarize, compare, and plotting scripts
- `results/`: generated run outputs
- `ctchecker_results/`: checked-in external baseline results used in reporting

The main tool families currently wired into the repository are:

- `klee_cf`
- `klee_eager`
- `klee_self_comp`
- `binsec`
- `abacus`

## Running Scripts

Run repository-owned Python CLIs from the repository root with `python -m ...`. That is the canonical and supported invocation style, and it keeps imports and relative paths consistent.

Repository Python entrypoints assume Python 3.14. The supported setup is the shared conda environment defined in `environment-build.yml`.

Direct file execution such as `python scripts/experiments/run_klee_cf.py` is not a supported entrypoint.

Examples:

```bash
python -m scripts.experiments.run_klee_cf 1m --sym-size 4 --benchmarks bearssl:default
python -m scripts.experiments.run_binsec 1m --sym-size 4 --benchmarks bearssl:default
python -m scripts.experiments.run_experiments configs/experiments/run_experiments.toml
python -m scripts.experiments.run_experiments --postprocess-only configs/experiments/run_experiments.toml
python -m scripts.experiments.run_experiments_abacus configs/experiments/run_experiments_abacus.toml
python -m tools.postprocess.merge_results /path/to/campaign-output/all -o merged.csv
python -m tools.postprocess.summarize_reproduction_status /path/to/campaign-output/all --output summary.csv
```

Benchmark selectors are now always `library:variant`. The older benchmark-id abstraction is gone.

Useful entrypoints:

- `python -m scripts.experiments.run_klee_cf ...`: run the control-flow KLEE variant
- `python -m scripts.experiments.run_klee_eager ...`: run the eager KLEE variant
- `python -m scripts.experiments.run_klee_self_comp ...`: run the KLEE self-composition mode
- `python -m scripts.experiments.run_binsec ...`: run Binsec and convert its output
- `python -m scripts.experiments.run_abacus ...`: run ABACUS and convert its output
- `python -m scripts.experiments.run_experiments ...`: run the multi-tool campaign and postprocess it
- `python -m scripts.experiments.run_experiments_abacus ...`: run the ABACUS campaign flow

## Campaign Metadata And Postprocessing

Campaign runs now write explicit metadata that downstream tools rely on:

- each campaign output root contains `_run_metadata.json`
- merged CSVs can carry a `*.metadata.json` sidecar with per-column metadata

That metadata stores raw option values such as `searcher=random-path,dfs` and `concretization_policy=false`. The shared metadata layer does not normalize those values into tool-specific display names anymore. Presentation choices belong in reporting code, not in metadata generation.

Important postprocessing commands:

- `python -m tools.postprocess.merge_json_runs_by_experiment <dir>`: merge repeated JSON files for one exact configuration
- `python -m tools.postprocess.merge_results <dir>`: merge many exact configurations into one wide CSV keyed by source location
- `python -m tools.postprocess.apply_sliced_map ...`: remap sliced benchmark locations back to unsliced locations
- `python -m tools.postprocess.filter_merged_results ...`: filter merged CSV rows by configured location allowlists
- `python -m tools.postprocess.aggregate_experiment_groups ...`: summarize exact configurations, generate plots, and choose one default best configuration per tool
- `python -m tools.postprocess.summarize_reproduction_status ...`: summarize replay outcomes, including selected best-of tables and by-library tables
- `python -m tools.postprocess.reproduce_positives ...`: replay positives via the Pin-based tracer

## Adding A New Benchmark

Adding a benchmark now means teaching the shared registry about generic benchmark facts and teaching existing runners how to interpret that benchmark's already-generic case matrix.

### 1. Add a benchmark descriptor

Create a TOML file under `configs/benchmarks/` using the current schema.

Minimal shape:

```toml
[[benchmarks]]
library = "example"
code_path = "benchmarks/example"
path_prefixes = ["benchmarks/example/"]
tools = ["klee_cf", "klee_eager", "klee_self_comp", "binsec"]

[benchmarks.builds.klee]
script = "benchmarks/example/build.sh"
tool_flag = "--klee"
preset = "default"

[benchmarks.builds.binsec]
script = "benchmarks/example/build.sh"
tool_flag = "--binsec"
preset = "default"

[benchmarks.build_aliases]
klee_cf = "klee"
klee_eager = "klee"
klee_self_comp = "klee"

[benchmarks.runner_profiles.default]
config = "configs/runner/example_runner.toml"
preset = "default"

[benchmarks.variants.default]

[[benchmarks.targets]]
target = "foo"

[[benchmarks.configs]]
config = "fix_pub"
public_mode = "fix_pub"

[[benchmarks.configs]]
config = "var_pub"
public_mode = "var_pub"
```

Notes:

- benchmark identity is now always `library_id + variant_id`
- variants are explicit and required
- build aliases are the supported way for multiple tool ids to share one benchmark-local build mode
- runner profiles are benchmark-owned because the benchmark decides which wrapper config/preset pairs are valid

### 2. Add benchmark-local build support

Create or update `benchmarks/<name>/build.sh` so it understands the `tool_flag` values from the descriptor and calls:

```bash
python -m tools.generate_runner_artifacts ...
python -m tools.resolve_runner_profile ...
```

The current design keeps runner-config resolution and artifact generation out of shell logic as much as possible.

### 3. Make sure the existing runners can consume it

If the benchmark follows the shared `targets + configs + tools + exclusions + path_templates` pattern, the current runners can usually expand it without new shared code. The recent `expand_benchmark_cases` helper in `scripts/experiments/common.py` exists specifically to keep new benchmarks on that path.

If one tool needs genuinely benchmark-specific extra data, keep that extra data narrow and runner-local under `BenchmarkDefinition.extra_config` instead of pushing that field into the shared registry schema.

### 4. Validate the benchmark

Typical validation sequence:

```bash
python -m scripts.experiments.run_klee_cf 1m --benchmarks example:default
python -m scripts.experiments.run_binsec 1m --benchmarks example:default
python -m tools.resolve_runner_profile --library example --variant default --field config
```

## Adding A New Tool

After the refactor, adding a tool is driven by benchmark configs plus a matching runner entrypoint. There is no separate hardcoded tool registry.

### 1. Choose a tool id

Pick a stable id such as `my_tool`. That exact id is used in:

- benchmark TOML `tools = [...]`
- the runner filename `scripts/experiments/run_my_tool.py`
- `CampaignTool(tool_id="my_tool", ...)`
- campaign TOML `run_definitions.*.tool`

### 2. Create the runner entrypoint

Add `scripts/experiments/run_my_tool.py`.

At minimum it should expose:

```python
CAMPAIGN_TOOL = CampaignTool(tool_id="my_tool", module_name=__name__)

def main(argv: list[str] | None = None) -> int:
    ...
```

If the tool is just a thin mode wrapper, follow the `run_klee_cf.py`, `run_klee_eager.py`, or `run_klee_self_comp.py` pattern. If it has its own execution flow, follow `run_binsec.py` or `run_abacus.py`.

### 3. Reuse shared benchmark expansion when possible

For tools that fit the common benchmark matrix, use the shared helper in `scripts/experiments/common.py`:

- `expand_benchmark_cases(...)`
- `resolve_case_template(...)`

This is the current simplification path for new tools. A new runner should not copy the old nested `targets x configs x exclusions` parsing loops unless its input model truly falls outside the shared matrix.

### 4. Add the tool to benchmark descriptors

For each benchmark that supports the tool:

- add the tool id to the benchmark-level `tools` list
- add `benchmarks.builds.<build_id>` metadata, or add a `build_aliases` entry if the tool can reuse another build
- add any genuinely tool-specific extra config only if the runner cannot derive its cases from the shared matrix

### 5. Add campaign support if needed

If the tool should participate in `run_experiments.py`, add matching entries to the campaign TOML `run_definitions` and enable them in `[runs]`.

### 6. Validate the tool

Typical checks:

```bash
python -m scripts.experiments.run_my_tool --help
python -m scripts.experiments.run_my_tool ... --benchmarks example:default
python -m scripts.experiments.run_experiments path/to/campaign.toml
```

## Design Notes

Important design choices in the current codebase:

- benchmark descriptors own generic benchmark facts, not tool execution logic
- runner modules own tool-specific parsing and execution
- tool discovery is derived from benchmark descriptors, not from a hardcoded list
- campaign metadata stores raw values and leaves display normalization to reporting
- postprocessing works from exact configuration columns and treats "best configuration" selection as an explicit later step

Two tool-specific caveats worth knowing:

- self-composition currently emits branch findings only
- ABACUS infers `kind` by disassembling the divergent instruction because its raw logs do not classify branch versus memory directly

## Code Style

The code and documentation style in this repository is intentionally pragmatic and direct. New code and documentation should follow these rules:
- keep the code and documentation style pragmatic and direct across both Python and C++ code
- put a concise module docstring at the top of public CLI modules and shared modules
- document public helper functions whose behavior is reused across modules or relied on by build scripts, runners, or postprocessing
- for new or substantially changed C++ code, document important classes and functions that define behavior, invariants, or integration points
- for modified KLEE code, add a short local overview near the modified area or in the owning file describing what was changed and how that change fits into the surrounding KLEE flow; do not treat this as a requirement to retroactively document untouched upstream code
- keep tool-specific parsing in the runner or converter that owns it; do not move it into shared code unless multiple tools genuinely reuse it
- prefer explicit data flow over clever abstractions; long orchestration functions are acceptable when they are the clearest representation of the workflow
- keep benchmark identity explicit as `library_id` plus `variant_id`
- use explicit metadata files and structured fields instead of deriving semantics from filenames
- use type hints on shared and public Python functions when the surrounding file already does
- repository Python code should use absolute package imports such as `scripts.experiments.common` or `tools.shared.experiment_registry`, and repository Python entrypoints should use the canonical `python -m ...` invocation style rather than relative imports, direct-file assumptions, or `sys.path` hacks
- shell wrappers and benchmark build scripts that invoke repository Python modules should call `python -m ...` from the repository root instead of executing `.py` files by path
- document code sections whose behavior is hard to infer, easy to misuse, constrained by subtle pitfalls, or kept as temporary patches
- explain the reason for non-obvious designs and workarounds, not just the mechanical behavior, especially around workspace isolation, replay behavior, metadata propagation, fairness of comparisons, and KLEE integration boundaries
- use short comments for local rationale and longer nearby documentation when future readers need control-flow or design context
- keep generated or edited source-like files newline-terminated

This style guide is intentionally aligned with the current codebase rather than with a more abstract or framework-heavy style that the repository does not use.
