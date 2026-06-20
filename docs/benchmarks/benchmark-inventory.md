# Benchmark Inventory

This page records the benchmark families that are currently implemented in the
descriptor layer and the families that are planned but do not yet have complete
repository descriptors.

Implemented means there is a benchmark descriptor under `configs/benchmarks/`
and the benchmark can be selected in `library:variant` form. Planned means the
benchmark is part of the intended evaluation set, or appears in bundled source
trees or prior artifact data, but does not yet have a complete selector in the
repository benchmark pipeline.

This inventory was checked against the current workspace state. Monocypher,
BearSSL RSA stages, and Libgcrypt RSA stages are implemented in this
repository. Libgcrypt and OpenSSL AES, DES, and ECDSA benchmark descriptors are
planned but not yet implemented in this checkout. HACL Chacha20, SHA256, and
SHA512 are feasible benchmark candidates only after the matching generated HACL
C implementations are added to the vendored source tree; this checkout
currently has the public headers but only the bignum C sources under
`benchmarks/hacl-packages-c-v0.6.0/src/`.

Detailed benchmark-model rationale belongs in focused pages under `models/`.
Start with `models/rsa-stages.md` for the RSA input model, defaults, fidelity
limits, and validation checklist.

## Current Descriptor Set

| Selector | Targets | Benchmark family |
| --- | --- | --- |
| `appliedcryp:default` | `3way`, `des`, `loki91` | Constantine-style known-violation subset from Applied Crypto sources. |
| `bearssl:default` | `aes_big`, `aes_ct`, `modexp`, `des_tab` | Legacy combined BearSSL selector. Use focused selectors when possible. |
| `bearssl:aes_des` | `aes_big`, `aes_ct`, `des_tab` | BearSSL AES/DES selector spanning known-violation rows and the `aes_ct` constant-time-claim routine. |
| `bearssl:modexp` | `modexp` | BearSSL 0.6 modular exponentiation. |
| `bearssl:rsa_stages` | `rsa_i31_private`, `rsa_i31_oaep_decrypt`, `rsa_ssl_decrypt`, `rsa_oaep_unpad` | BearSSL 0.6 RSA private core, full decrypt, and OAEP unpadding stages. |
| `ghostrider:default` | `findmax`, `matmul` | Constantine-style known-violation subset from GhostRider/Raccoon-style microbenchmarks. |
| `hacl_modexp:default` | `modexp32`, `modexp64` | HACL Packages C v0.6 modular exponentiation. |
| `libg:default` | `des` | Constantine image-table `libgcrypt` row as represented by `benchmarks/libg`; this is distinct from the real Libgcrypt 1.10.1 tree. |
| `libgcrypt:default` | `modexp` | Libgcrypt 1.10.1 modular exponentiation. |
| `libgcrypt:rsa_stages` | `gcry_pk_decrypt_pkcs1`, `gcry_pk_decrypt_oaep`, `gcry_pk_decrypt_raw`, `rsa_pkcs1_decode_for_enc`, `rsa_oaep_decode` | Libgcrypt 1.10.1 RSA decrypt and padding decode stages. |
| `libgcrypt:sliced` | `modexp` | KLEE-CF sliced Libgcrypt modular exponentiation variant. |
| `libsodium:curve25519` | `curve25519_scalarmult` | Libsodium routine with a constant-time claim from the broader BINSEC/Rel2 and ABACUS comparison space. |
| `mbedtls:default` | `modexp`, `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Mbed TLS 3.2.1 modular exponentiation plus RSA stages. |
| `mbedtls:rsa_stages` | `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Focused Mbed TLS RSA stage selector. |
| `mbedtls:rsa_decrypt_only` | `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Focused Mbed TLS RSA decrypt campaign selector. |
| `mbedtls:sliced` | `modexp` | KLEE-CF sliced Mbed TLS modular exponentiation variant. |
| `monocypher:argon2i` | `argon2i` | Monocypher 3.0.0 Argon2i routine from the ABACUS comparison space. |
| `monocypher:chacha20` | `chacha20` | Monocypher 3.0.0 Chacha20 routine from the ABACUS comparison space. |
| `monocypher:ed25519` | `ed25519` | Monocypher 3.0.0 Ed25519 routine from the ABACUS comparison space. |
| `monocypher:poly1305` | `poly1305` | Monocypher 3.0.0 Poly1305 routine from the ABACUS comparison space. |
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

### Symmetric Library Routines

This family is planned for real Libgcrypt and OpenSSL library routines rather
than the historical image-table Libgcrypt subset represented by `libg:default`.
The initial plan is to keep AES and DES in focused selectors so they can be
compared with the existing BearSSL AES/DES rows without changing modular
exponentiation or RSA campaigns.

| Library | Status | Descriptor coverage |
| --- | --- | --- |
| Libgcrypt 1.10.1 | Planned | Add AES and DES encryption targets using the real Libgcrypt cipher API or the smallest direct cipher implementation entrypoint that preserves the same key/data model. |
| OpenSSL 1.1.1q | Planned | Add AES and DES encryption targets using OpenSSL C implementations built with assembly disabled, matching the current OpenSSL descriptor style. |

### RSA Decryption And Unpadding

The RSA benchmark model is split into padding-only functions, internal private
operations, and full decrypt APIs. See `rsa-overview.md` for the modeling
rationale.

| Library | Status | Descriptor coverage |
| --- | --- | --- |
| Mbed TLS 3.2.1 | Implemented | `mbedtls:rsa_stages` and `mbedtls:rsa_decrypt_only`. |
| OpenSSL 1.1.1q | Implemented | `openssl:rsa_stages`. |
| BearSSL 0.6 | Implemented | `bearssl:rsa_stages` covers the i31 private core, OAEP full decrypt, TLS-style PKCS#1 v1.5 full decrypt, and OAEP unpadding. |
| Libgcrypt 1.10.1 | Implemented | `libgcrypt:rsa_stages` covers public `gcry_pk_decrypt` modes and internal PKCS#1/OAEP decode helpers. |

HACL is not listed for RSA here because the current HACL benchmark plan and
descriptor coverage are modular-exponentiation only.

### Functions With Constant-Time Claims

This family is meant to cover functions from the BINSEC/Rel2 and ABACUS
comparison space that carry a constant-time claim under the modeled inputs.
They are grouped by that claim, not by whether this repository has already
validated the claim.

| Library or source | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL 0.6 | Implemented | `bearssl:aes_des` includes `aes_ct`; only `aes_ct` is treated as the constant-time-claim routine in this selector. |
| HACL Packages C v0.6 | Possible after source expansion | Chacha20, SHA256, and SHA512 have headers in the bundled HACL tree, but the matching generated C implementation files are not present in this checkout. Add these only after restoring the generated C sources and validating a small wrapper build. |
| Libgcrypt 1.10.1 | Planned | Add an ECDSA signing target with a secret private scalar and public message digest. |
| Libsodium | Implemented | `libsodium:curve25519` covers `curve25519_scalarmult`. |
| Monocypher | Implemented | `monocypher:chacha20`, `monocypher:poly1305`, `monocypher:argon2i`, and `monocypher:ed25519`. |
| OpenSSL 1.1.1q | Planned | Add an ECDSA signing target around the OpenSSL EC/ECDSA implementation with fixed curve parameters, a secret private key, and public message digest. |

## Current Classification Gaps

- The image table includes more historical suites than the subset currently
  implemented under `configs/benchmarks/`. If those rows are part of the final
  evaluation, they should be added as planned benchmark families rather than
  silently folded into existing selectors.
- Libgcrypt and OpenSSL AES, DES, and ECDSA descriptors are planned but do not
  yet exist under `configs/benchmarks/`.
- HACL Chacha20, SHA256, and SHA512 are possible benchmark additions, but this
  checkout lacks their generated C implementation files. Do not add descriptors
  until the vendored HACL source set is expanded beyond the current bignum-only
  `src/` contents.
