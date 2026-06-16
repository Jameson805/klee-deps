# Examples Index

This directory contains toy programs, reproducers, focused helper scripts, and raw solver artifacts used to understand tool behavior in this repository.

## What Belongs Here

- small cross-tool comparison programs
- focused reproducer inputs for one bug or behavior
- local helper scripts used to run or profile those toy programs
- raw solver inputs when a bug is easier to discuss outside the full benchmark pipeline

This directory is not the main benchmark set. The benchmark set lives under `benchmarks/` and is driven by the descriptor and runner pipeline.

## Current Inventory

### Cross-Tool Toys

- `cf_favored_branch_maze_cross_tool.c`: branch-oriented toy used in the KLEE-CF candidate-model note
- `cf_symbolic_mod_chain_branch.c`: symbolic modular-chain toy used in the same note

### BINSEC Reproducers

- `toy_binsec_wrong_location.c`: reproducer for replay-versus-reporting mismatch semantics
- `toy_binsec_wrong_location_var_pub.cfg`: matching focused BINSEC script

### Self-Composition Profiling Inputs

- `toy_selfcomp_arc4_like.c`: toy workload used by the expression-comparison profiling note
- `toy_selfcomp_arc4_like.profile.sh`: local profiling helper

### Small Standalone Demos

- `example.c`
- `is_bit_set.c`
- `is_bit_set_no_sc.c`

### Misc Focused Reproducers

- `min_missing_dbg_shift_repro.c`
- `toy_aes_big_like.c`
- `toy_aes_big_like_no_tables.c`

### Solver Artifacts

- `solver_timeout_mult_div.smt2`
- `solver_timeout_mult_div_bitwise.smt2`

### Local Helpers

- `run_proof_comparison.py`: exploratory helper for focused proof and output comparison
- `build.sh`
- `run.sh`

## Related Documentation

- `../docs/tools/klee-cf.md`
- `../docs/tools/klee-self-comp.md`
- `../docs/tools/binsec.md`
- `../docs/notes/klee-cf-candidate-models.md`
- `../docs/notes/expr-compare-findings.md`
- `../docs/notes/binsec-wrong-location-reproducer.md`

## Cleanup Notes

Some source comments and historical outputs may still mention the former singular directory name.