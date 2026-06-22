# Other Benchmark Models

This page documents implemented targets that do not cleanly belong to the
modular-exponentiation, Constantine, bounded verification, or ABACUS groups.
These targets may still be useful for coverage or future comparisons, but their
primary provenance is not yet tied to one of the requested groups.

## BearSSL RSA Stages

BearSSL RSA stages use the same repository RSA modeling strategy as the other
RSA stage benchmarks, but BearSSL RSA was not identified as an ABACUS row in the
current comparison request.

| Target | Layer | Secret inputs | Public inputs | Notes |
| --- | --- | --- | --- | --- |
| `rsa_i31_private` | Private primitive. | Suffixes of `dp` and `dq`, width `SYM_SIZE`. | 128-byte ciphertext representative. | Calls `br_rsa_i31_private`. |
| `rsa_i31_oaep_decrypt` | Full OAEP decrypt. | Suffixes of `dp` and `dq`, width `SYM_SIZE`. | 128-byte ciphertext representative. | Calls BearSSL i31 OAEP decrypt with SHA1 OAEP settings. |
| `rsa_ssl_decrypt` | TLS-style full decrypt. | Suffixes of `dp` and `dq`, width `SYM_SIZE`. | 128-byte ciphertext representative. | Calls `br_rsa_ssl_decrypt`. |
| `rsa_oaep_unpad` | Padding-only helper. | 128-byte encoded block. | None. | Calls `br_rsa_oaep_unpad`. |

The model keeps a concrete valid 1024-bit base key and makes only selected CRT
exponent suffixes symbolic. This follows the repository RSA strategy: keep key
import and modulus-domain setup concrete, then test secret-dependent private
arithmetic and unpadding behavior.

Detailed inputs:

| Selector target | Input variable | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| `bearssl:rsa_i31_private`, `bearssl:rsa_i31_oaep_decrypt`, `bearssl:rsa_ssl_decrypt` | `dp`, `dq` | Secret | `SYM_SIZE` bytes each | Large prime-like suffix seeds. | `fix_pub` and `var_pub`. | Keeps the concrete base key valid while varying selected CRT exponent suffixes. |
| `bearssl:rsa_i31_private`, `bearssl:rsa_i31_oaep_decrypt`, `bearssl:rsa_ssl_decrypt` | `ciphertext` | Public | 128 bytes | Generated ciphertext for the shared concrete 1024-bit RSA key. | `var_pub`. | Keeps fixed-public decrypt runs in the valid RSA domain. |
| `bearssl:rsa_oaep_unpad` | `encoded` | Secret | 128 bytes | N/A. | `fix_pub` and `var_pub`. | Focuses directly on OAEP unpadding behavior. |

Best reconciliation: keep BearSSL RSA here unless a future comparison source
explicitly uses it. If it becomes part of an ABACUS or BINSEC comparison, add a
compatibility note in that group rather than moving the generic RSA rationale
out of this page.

## Libsodium Curve25519

The repository includes a Libsodium `curve25519_scalarmult` target with a
32-byte secret scalar and 32-byte public point. It is useful as a comparable
constant-time-claim routine, but it is not the HACL* Curve25519 benchmark from
the BINSEC paper comparison set.

| Target | Layer | Secret inputs | Public inputs | Notes |
| --- | --- | --- | --- | --- |
| `curve25519_scalarmult` | Scalar multiplication. | 32-byte scalar. | 32-byte point. | Selector `libsodium:curve25519`; do not use as an exact BINSEC input-scheme replay. |

Detailed inputs:

| Selector target | Input variable | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| `libsodium:curve25519` / `curve25519_scalarmult` | `scalar` | Secret | 32 bytes | Standard Libsodium/X25519 test scalar seed. | `fix_pub` and `var_pub`. | Models the private scalar while starting concrete replay from a valid nonzero scalar. |
| `libsodium:curve25519` / `curve25519_scalarmult` | `point` | Public | 32 bytes | Standard X25519 base point: first byte `0x09`, remaining bytes zero. | `var_pub`. | Canonical public point for fixed-public scalar-multiplication runs. |

Best reconciliation: keep Libsodium Curve25519 here unless a comparison source
explicitly uses this Libsodium wrapper. For BINSEC replay, add the matching
HACL* Curve25519 source and descriptor instead of reclassifying this target.

## HACL Bignum Modular Exponentiation

The repository includes HACL Packages C v0.6 bignum modular-exponentiation
wrappers. They use the shared modular-exponentiation input shape, but they are
not part of the primary modular-exponentiation comparison group used by the
modexp campaign configs.

| Target | Layer | Secret inputs | Public inputs | Notes |
| --- | --- | --- | --- | --- |
| `hacl_modexp:modexp32` | 32-bit HACL bignum exponentiation. | `exp`, width `SYM_SIZE`. | `base` and `mod`, each width `SYM_SIZE`. | Repository-only HACL bignum coverage. |
| `hacl_modexp:modexp64` | 64-bit HACL bignum exponentiation. | `exp`, width `SYM_SIZE`. | `base` and `mod`, each width `SYM_SIZE`. | Repository-only HACL bignum coverage. |

Detailed inputs:

| Selector target | Input variable | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| `hacl_modexp:modexp32`, `hacl_modexp:modexp64` | `exp` | Secret | `SYM_SIZE` bytes | Second largest prime representable in the selected width. | `fix_pub` and `var_pub`. | Keeps the exponent as private key material while starting concrete replay from a nondegenerate value. |
| `hacl_modexp:modexp32`, `hacl_modexp:modexp64` | `base` | Public | `SYM_SIZE` bytes | Small prime: `0x03` for 1 byte, `0xfb` for wider presets. | `var_pub`. | Stable public representative that avoids a zero base. |
| `hacl_modexp:modexp32`, `hacl_modexp:modexp64` | `mod` | Public | `SYM_SIZE` bytes | Largest prime representable in the selected width. | `var_pub`. | Avoids invalid zero, collapsed modulus-one behavior, and small composite moduli. |

Best reconciliation: keep HACL bignum modular exponentiation here unless a
future campaign explicitly includes it in the primary modexp comparison set.
When reporting the current modexp campaign configs, do not include
`hacl_modexp:modexp32` and `hacl_modexp:modexp64` in the modexp group.

## Reclassification Rule

Move a target out of this page only when the source relation is explicit enough
to support planning changes. A similar algorithm name is not enough; the
function boundary, library version, and secret/public input model should also
match or be documented as a deliberate compatibility deviation.