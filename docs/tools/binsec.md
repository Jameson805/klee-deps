# BINSEC

This page documents how BINSEC is integrated and run in this repository.

## What BINSEC Is Used For Here

BINSEC is one of the constant-time analysis backends compared against the same benchmark wrappers, case matrix, replay flow, and postprocessing schema used by the in-repo KLEE variants.

The repository does not treat BINSEC as a drop-in peer of the KLEE runners. BINSEC has its own build shape, cfg generation, execution contract, and replay caveats, so it has a dedicated runner and dedicated troubleshooting notes.

## Build And Activation

BINSEC is built from source in a workspace-local OPAM root during `./build_all.sh binsec` or `./build_all.sh all`.

After activation:

```bash
source ./activate-workspace.sh
```

the workspace manifest in `build/tool-paths.json` is used to expose the BINSEC executable and switch-local environment for the current shell session.

## How The Repository Runs BINSEC

The entrypoint is:

```bash
python -m scripts.experiments.run_binsec 1m --sym-size 4 --benchmarks bearssl:default
```

`scripts/experiments/run_binsec.py` owns the flow.

That runner handles:

- case expansion from benchmark descriptors
- benchmark-local executable and cfg selection
- BINSEC invocation
- conversion through `tools.converters.binsec_toml_to_json`
- replay of positives when a replay executable is available

## Generated CFG Flow

The repository does not rely on static checked-in benchmark-local BINSEC cfg files.

Instead:

- shared BINSEC prelude content lives in `configs/binsec/binsec_base.cfg`
- benchmark-local generated cfg files are emitted during artifact generation
- generated cfgs stay local to the benchmark build outputs so they are easy to inspect and do not leak across benchmarks

The runner-config schema and artifact generation rules are documented in `../architecture/runner-config.md`.

## Build Shape Differences From KLEE Modes

BINSEC mode has different build constraints than the KLEE modes. In practice, that includes repository-specific handling around:

- executable shape
- dynamic versus static boundaries
- external calls and stubs
- replay-compatible metadata

Those constraints are why BINSEC has a dedicated experience page and preserved deep-dive notes instead of relying on a one-paragraph summary.

## Conversion And Replay

The BINSEC runner writes a stats file, then converts it into the shared JSON schema with `tools.converters.binsec_toml_to_json`.

Replay is used to turn positive models into concrete execution comparisons when a replay executable exists. That replay stage is useful, but it is not identical to BINSEC's own reporting semantics. See `../experiences/binsec-challenges.md` for the mismatch cases that matter in practice.

## Important Option Surface

- `--sym-size`
- `--jump-enum`
- `--sse-depth`
- `--max-solver-time`
- `--fml-solver`
- `--smt-solver`
- `--benchmarks`

The runner keeps the option surface explicit and repository-local rather than pushing tool-specific policy into generic shared code.

## Read This Next

- `../experiences/binsec-challenges.md`
- `../notes/binsec-external-calls.md`
- `../notes/binsec-wrong-location-reproducer.md`
- `../../examples/README.md`