# Benchmark Inventory

This page records the benchmark families that are currently implemented in the
descriptor layer and the families that are planned but do not yet have complete
repository descriptors.

Implemented means there is a benchmark descriptor under `configs/benchmarks/`
and the benchmark can be selected in `library:variant` form. Planned means the
benchmark is part of the intended evaluation set, or appears in bundled source
trees or prior artifact data, but does not yet have a complete selector in the
repository benchmark pipeline.

## Current Descriptor Set

| Selector | Targets | Benchmark family |
| --- | --- | --- |
| `appliedcryp:default` | `3way`, `des`, `loki91` | Constantine-style known-violation subset from Applied Crypto sources. |
| `bearssl:default` | `aes_big`, `aes_ct`, `modexp`, `des_tab` | Legacy combined BearSSL selector. Use focused selectors when possible. |
| `bearssl:aes_des` | `aes_big`, `aes_ct`, `des_tab` | BearSSL symmetric routines used by BINSEC/Rel2 and ABACUS-style comparisons. |
| `bearssl:modexp` | `modexp` | BearSSL 0.6 modular exponentiation. |
| `ghostrider:default` | `findmax`, `matmul` | Constantine-style known-violation subset from GhostRider/Raccoon-style microbenchmarks. |
| `hacl_modexp:default` | `modexp32`, `modexp64` | HACL Packages C v0.6 modular exponentiation. |
| `libg:default` | `des` | Constantine image-table `libgcrypt` row as represented by `benchmarks/libg`; this is distinct from the real Libgcrypt 1.10.1 tree. |
| `libgcrypt:default` | `modexp` | Libgcrypt 1.10.1 modular exponentiation. |
| `libgcrypt:sliced` | `modexp` | KLEE-CF sliced Libgcrypt modular exponentiation variant. |
| `libsodium:curve25519` | `curve25519_scalarmult` | Libsodium safe cryptographic routine from the broader BINSEC/Rel2 and ABACUS comparison space. |
| `mbedtls:default` | `modexp`, `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Mbed TLS 3.2.1 modular exponentiation plus RSA stages. |
| `mbedtls:rsa_stages` | `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Focused Mbed TLS RSA stage selector. |
| `mbedtls:rsa_decrypt_only` | `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Focused Mbed TLS RSA decrypt campaign selector. |
| `mbedtls:sliced` | `modexp` | KLEE-CF sliced Mbed TLS modular exponentiation variant. |
| `openssl:default` | `recp`, `mont`, `mont_consttime`, `mont_word` | OpenSSL 1.1.1q modular exponentiation backends. |
| `openssl:rsa_stages` | `rsa_private_core`, `padding_check_pkcs1_type_2`, `padding_check_oaep_mgf1`, `padding_check_sslv23`, `pkey_rsa_pkcs1_decrypt`, `pkey_rsa_oaep_decrypt`, `pkey_rsa_sslv23_decrypt`, `pkey_rsa_no_padding_decrypt` | OpenSSL 1.1.1q RSA primitive, padding, and EVP-facing decrypt stages. |
| `openssl:sliced` | `recp`, `mont`, `mont_word` | KLEE-CF sliced OpenSSL modular exponentiation variant; `mont_consttime` is excluded. |
| `openssl_almeida:default` | `tls_rempad_luk13` | BINSEC/Rel2 TLS record-padding benchmark from the Almeida/OpenSSL source. |
| `pycrypto:default` | `arc4` | Constantine-style PyCrypto subset. |

## Intended Benchmark Families

### Modular Exponentiation

This family is implemented for the libraries currently listed in the proposed
evaluation scope:

| Library | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL 0.6 | Implemented | `bearssl:modexp` and the legacy `bearssl:default` selector. |
| Mbed TLS 3.2.1 | Implemented | `mbedtls:default`; sliced variant in `mbedtls:sliced`. |
| Libgcrypt 1.10.1 | Implemented | `libgcrypt:default`; sliced variant in `libgcrypt:sliced`. |
| OpenSSL 1.1.1q | Implemented | `openssl:default` with reciprocal, Montgomery, constant-time Montgomery, and word Montgomery targets. |
| HACL Packages C v0.6 | Implemented | `hacl_modexp:default` with 32-bit and 64-bit bignum targets. |

The standard cases compare fixed-public-input and variable-public-input modes
where the descriptor supports both. Several modular-exponentiation descriptors
also define loop-limiter or sliced variants for focused KLEE-CF experiments.

### Constantine-Style Known Violations

The current repository covers the subset below:

| Source group | Implemented targets | Selector |
| --- | --- | --- |
| Applied Crypto | `3way`, `des`, `loki91` | `appliedcryp:default` |
| GhostRider | `findmax`, `matmul` | `ghostrider:default` |
| Image-table Libgcrypt subset | `des` | `libg:default` |
| PyCrypto | `arc4` | `pycrypto:default` |
| BINSEC/Rel2 row | `tls_rempad_luk13`, `aes_big`, `des_tab` | `openssl_almeida:default`, `bearssl:aes_des` |

The attached table contains additional rows that are not currently represented
as repository descriptors unless they are intentionally mapped to another source
tree. These include Chronos, S-CP `cast-ssl`, Botan, the remaining PyCrypto
targets, the remaining image-table Libgcrypt targets, and the remaining
GhostRider/Raccoon rows beyond `findmax` and `matmul`.

### RSA Decryption And Unpadding

The RSA benchmark model is split into padding-only functions, internal private
operations, and full decrypt APIs. See `rsa-overview.md` for the modeling
rationale.

| Library | Status | Descriptor coverage |
| --- | --- | --- |
| Mbed TLS 3.2.1 | Implemented | `mbedtls:rsa_stages` and `mbedtls:rsa_decrypt_only`. |
| OpenSSL 1.1.1q | Implemented | `openssl:rsa_stages`. |
| BearSSL 0.6 | Planned | No RSA-stage descriptor yet. |
| Libgcrypt 1.10.1 | Planned | No RSA-stage descriptor yet. |

HACL is not listed for RSA here because the current HACL benchmark plan and
descriptor coverage are modular-exponentiation only.

### Other Safe Cryptographic Routines

This family is meant to cover cryptographic routines from the BINSEC/Rel2 and
ABACUS comparison space that are expected to be constant-time under the modeled
inputs.

| Library or source | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL 0.6 | Implemented | `bearssl:aes_des` covers `aes_big`, `aes_ct`, and `des_tab`; `aes_big` and `des_tab` are the BINSEC/Rel2 rows. |
| Libsodium | Implemented | `libsodium:curve25519` covers `curve25519_scalarmult`. |
| Monocypher | Planned | Monocypher was benchmarked by the ABACUS paper and should be benchmarked again in this repository. There is no top-level repository descriptor yet. Candidate routines from the bundled ABACUS artifact data include Chacha20, Poly1305, Argon2i, and Ed25519. |

## Current Classification Gaps

- The image table includes more historical suites than the subset currently
  implemented under `configs/benchmarks/`. If those rows are part of the final
  evaluation, they should be added as planned benchmark families rather than
  silently folded into existing selectors.
- Monocypher is part of the intended ABACUS-paper comparison set, but it is not
  yet a first-class benchmark descriptor in this repository.