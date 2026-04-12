## Constantine Phase 1 Output

This document records Phase 1 deliverables for integrating Constantine benchmarks:
1. Target inventory and entrypoint mapping.
2. Direct-compile vs wrapper-needed classification.
3. Secret/public hints from existing Constantine config files.
4. Normalized naming matrix for build artifacts and result files.
5. Known ambiguities and non-blocking risks to address in Phase 2.

CTChecker comparison is treated as optional sanity validation, not benchmark pass/fail criteria.

### Scope (10 targets)
- binsec/aes_big
- binsec/des_tab
- binsec/tls-rempad-luk13
- issta18/appliedCryp/3way
- issta18/appliedCryp/des
- issta18/appliedCryp/loki91
- issta18/ghostrider/findmax
- issta18/ghostrider/matmul
- issta18/libg/des
- pycrypto/ARC4

### A. Benchmark Inventory and Integration Readiness

| Benchmark ID | Source file | Config file | Entry from config | C entry observed | Integration classification |
| --- | --- | --- | --- | --- | --- |
| binsec_aes_big | benchmarks/Constantine/binsec/aes_big.c | benchmarks/Constantine/binsec/config-aes_big.json | dfs_EC___main | main and dfs_EC___main | Direct compile; light benchmark-specific harness for var/fix pub split likely needed |
| binsec_des_tab | benchmarks/Constantine/binsec/des_tab.c | benchmarks/Constantine/binsec/config-des_tab.json | __main | main | Direct compile; light benchmark-specific harness for var/fix pub split likely needed |
| binsec_tls_rempad_luk13 | benchmarks/Constantine/binsec/tls-rempad-luk13.c | benchmarks/Constantine/binsec/config-tls-rempad-luk13.json | __main | main | Direct compile; light benchmark-specific harness likely needed |
| issta_appliedcryp_3way | benchmarks/Constantine/issta18/appliedCryp/3way.c | benchmarks/Constantine/issta18/appliedCryp/config-3way.json | main | main | Direct compile; likely easiest MVP target |
| issta_appliedcryp_des | benchmarks/Constantine/issta18/appliedCryp/des.c | benchmarks/Constantine/issta18/appliedCryp/config-des.json | main | main | Direct compile |
| issta_appliedcryp_loki91 | benchmarks/Constantine/issta18/appliedCryp/loki91.c | benchmarks/Constantine/issta18/appliedCryp/config-loki91.json | main | main | Direct compile |
| issta_ghostrider_findmax | benchmarks/Constantine/issta18/ghostrider/findmax.c | benchmarks/Constantine/issta18/ghostrider/config-findmax.json | __main | main | Direct compile; simple dataflow benchmark |
| issta_ghostrider_matmul | benchmarks/Constantine/issta18/ghostrider/matmul.c | benchmarks/Constantine/issta18/ghostrider/config-matmul.json | __main | main | Direct compile; simple dataflow benchmark |
| issta_libg_des | benchmarks/Constantine/issta18/libg/des.c | benchmarks/Constantine/issta18/libg/config-des.json | __main | main | Direct compile |
| pycrypto_arc4 | benchmarks/Constantine/pycrypto/ARC4.c | benchmarks/Constantine/pycrypto/config-ARC4.json | __main | main | Direct compile |

Interpretation of "wrapper-needed":
- Full compile wrappers are not required for most targets because each file already includes a runnable main-like entry.
- Lightweight integration wrappers (or benchmark-specific switches in a shared harness) are still expected to create clear var_pub/fix_pub variants and replay-compatible argument handling.

### B. Secret/Public Input Hints (from Constantine configs)

| Benchmark ID | Secret/source hints (from config) | Notes for Phase 2 harness |
| --- | --- | --- |
| binsec_aes_big | llvm_cbe_ctx, _7 in dfs_EC___main | Preserve pointer-shaped symbolic regions; avoid over-constraining table accesses |
| binsec_des_tab | llvm_cbe_ctx, _4 in __main | Similar to aes_big; likely memory-access-heavy behavior |
| binsec_tls_rempad_luk13 | promoted_stack_var_main_0 in __main | Candidate where symbolic length/value constraints may be needed |
| issta_appliedcryp_3way | in_key, in in main | Straightforward secret input split |
| issta_appliedcryp_des | in_key, in in main | Straightforward secret input split |
| issta_appliedcryp_loki91 | in_key, in in main | Straightforward secret input split |
| issta_ghostrider_findmax | in in __main | Single secret buffer/input |
| issta_ghostrider_matmul | in1, in2 in __main | Two secret inputs |
| issta_libg_des | in_key, in in __main | Similar shape to appliedCryp des |
| pycrypto_arc4 | llvm_cbe_key in __main | Key-only secret source in config |

Public input convention for integration:
- Use current repository conventions: var_pub keeps declared public inputs symbolic; fix_pub concretizes public inputs only.
- If no explicit public set is inferable from Constantine configs, start with an empty public set and expose public controls incrementally in Phase 2.

### C. Normalized Naming Matrix (for all runners)

Naming base:
- benchmark key: const_<suite>_<name>
- suites: binsec, appliedcryp, ghostrider, libg, pycrypto

Per-benchmark canonical base names:
- const_binsec_aes_big
- const_binsec_des_tab
- const_binsec_tls_rempad_luk13
- const_appliedcryp_3way
- const_appliedcryp_des
- const_appliedcryp_loki91
- const_ghostrider_findmax
- const_ghostrider_matmul
- const_libg_des
- const_pycrypto_arc4

Artifact naming templates:
- KLEE-CF/Eager bitcode:
  - <base>_var_pub.bc
  - <base>_fix_pub.bc
- Replay executables:
  - <base>_var_pub_replay
  - <base>_fix_pub_replay
- Self-comp bitcode:
  - <base>_self_comp_var_pub.bc
  - <base>_self_comp_fix_pub.bc
- BINSEC executables:
  - <base>_binsec_var_pub
  - <base>_binsec_fix_pub
  - optional replay: <base>_binsec_var_pub_replay, <base>_binsec_fix_pub_replay
- Abacus executables:
  - <base>_abacus_fix_pub

Result naming templates:
- run_case result_name:
  - <base>_var_pub
  - <base>_fix_pub
  - tool-specialized: <base>_self_comp_var_pub, <base>_self_comp_fix_pub
- JSON outputs:
  - <base>_var_pub.json
  - <base>_fix_pub.json
- BINSEC TOML outputs:
  - <base>_var_pub.toml
  - <base>_fix_pub.toml

### D. Phase 1 blockers and ambiguities

1. Var/fix public split is not explicit in Constantine config files.
- Impact: benchmark variant definitions need a local policy in build/harness.
- Phase 2 approach: start with a minimal fixed policy and document per-benchmark overrides.

2. Mixed entry naming in configs (__main, dfs_EC___main, main) vs C runtime main.
- Impact: postprocessing or harness code must use explicit benchmark metadata rather than inferred entry names.

3. Some benchmark files are generated-style C (llvm_cbe_* symbols).
- Impact: type/pointer layouts can be fragile under transformations.
- Phase 2 approach: keep compile flags conservative (-O0, debug) and avoid aggressive source rewrites.

4. Memory-vs-branch behavior differs by benchmark.
- Impact: memory comparison should remain optional and non-gating.
- Phase 2 approach: keep benchmark success tied to producing tool outputs; run optional sanity checks separately.

### E. Phase 1 outcome

Phase 1 is complete for Constantine integration planning:
- Inventory and entrypoint mapping are established.
- Secret/source hints are extracted from existing config files.
- A normalized naming scheme is defined for all required tools.
- Key risks are identified with mitigation direction for Phase 2 implementation.
