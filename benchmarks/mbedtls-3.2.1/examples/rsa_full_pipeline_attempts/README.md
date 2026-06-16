# RSA Full-Pipeline Benchmark Attempts

This folder archives the exploratory benchmark variants we tried while attempting
to benchmark more of the mbedTLS RSA decryption pipeline than the existing
`mbedtls:rsa_private` and `mbedtls:pkcs1_v15_unpadding` targets.

## Attempted models

1. `rsa_private_full_key_wrapper.c`
   - Directly populated `mbedtls_rsa_context` fields `N, P, Q, D, DP, DQ, QP`.
   - Used fixed `E = 65537`.
   - Disabled blinding locally with `Vi = Vf = 1` and a zero RNG.

2. `rsa_private_pqe_wrapper.c`
   - Made `P` and `Q` symbolic, kept `E = 65537`, then called
     `mbedtls_rsa_complete()` to derive `D`, `DP`, `DQ`, and `QP`.
   - Disabled blinding locally with `Vi = Vf = 1` and a zero RNG.

## What we observed

1. The `full_key` model reached `mbedtls_rsa_private()`, but the search mostly
   concentrated in the first CRT modular exponentiation inside
   `mbedtls_mpi_exp_mod()`.
2. The `pqe` model usually failed to reach meaningful private-operation work.
   `run.istats` showed it spending almost all time in `mbedtls_rsa_complete()`,
   specifically in `mbedtls_rsa_deduce_private_exponent()` and then
   `mbedtls_mpi_gcd(P - 1, Q - 1)`.
3. Fixing `E = 65537` and disabling blinding removed some avoidable symbolic
   noise, but it did not change the core bottleneck for the `pqe` model.

## Outcome

The active benchmarks now use the simpler and more stable model described in
`/memories/repo/mbedtls-rsa-benchmark-notes.md`: a valid concrete RSA key with
symbolic `DP` and `DQ`, plus a zero RNG and no blinding. That model is used for
`rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, and `rsa_rsaes_oaep_decrypt`.

The files in this folder are kept as inactive examples and notes for future
experiments. They are no longer referenced by `configs/benchmarks/mbedtls.toml`.