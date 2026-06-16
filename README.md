# KLEE Constant-Time Analysis Workspace

This repository compares multiple constant-time analyses against the same benchmark wrappers, runner contracts, replay flow, and postprocessing pipeline. The main in-repo tool families are KLEE-CF, KLEE-Eager, KLEE-Self-Comp, BINSEC, and ABACUS.

This page is the landing page only. Detailed architecture, tool, benchmark, and style documentation lives under `docs/`.

## Quickstart

Build the local toolchain:

```bash
./build_all.sh all
```

Activate the shared conda environment plus the current workspace's manifest-backed tool aliases:

```bash
source ./activate-workspace.sh
```

Useful narrower build targets:

```bash
./build_all.sh env
./build_all.sh deps
./build_all.sh binsec
./build_all.sh klee --project klee-cf
./build_all.sh extras
```

The build flow creates or updates the conda environment from `environment-build.yml`, builds the local KLEE dependencies, builds BINSEC in a workspace-local OPAM root, records executable artifacts in `build/tool-paths.json`, and builds each top-level `klee-*` tree plus the `loop-limiter` plugin.

## Minimal Runs

Run repository-owned Python CLIs from the repository root with `python -m ...`.

```bash
python -m scripts.experiments.run_klee_cf 1m --sym-size 4 --benchmarks bearssl:default
python -m scripts.experiments.run_klee_eager 1m --sym-size 4 --benchmarks bearssl:default
python -m scripts.experiments.run_klee_self_comp 1m --sym-size 4 --benchmarks bearssl:default
python -m scripts.experiments.run_binsec 1m --sym-size 4 --benchmarks bearssl:default
```

Benchmark selectors are always `library:variant`.

## Documentation

- `docs/index.md`: documentation map and reading order
- `docs/tools/`: tool-specific usage and implementation notes
- `docs/architecture/`: pipeline, runner-config, and integration structure
- `docs/benchmarks/`: benchmark modeling notes
- `docs/experiences/`: lessons learned from external tools and debugging work
- `docs/notes/`: deeper implementation notes, repro writeups, and focused findings
- `docs/style-guide.md`: repository code and documentation style guide
- `examples/README.md`: catalog of toy programs, reproducers, and local helper scripts

## Repository Layout

- `benchmarks/`: benchmark integrations and generated benchmark-local artifacts
- `configs/benchmarks/`: benchmark descriptors keyed by `library` plus explicit `variant` entries
- `configs/runner/`: runner config inputs used to generate benchmark-local headers and BINSEC cfg files
- `scripts/experiments/`: per-tool runners and campaign orchestration entrypoints
- `tools/`: shared builders, converters, postprocessing, and metadata helpers
- `results/`: generated experiment outputs and focused validation artifacts
- `examples/`: toy programs, reproducers, and local analysis helpers

## Contributing

Follow `docs/style-guide.md` before editing code or documentation. The short repository-specific Copilot instructions live in `.github/copilot-instructions.md` and point to the same style guide.
