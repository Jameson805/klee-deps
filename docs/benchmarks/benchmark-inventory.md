# Benchmark Inventory

This page records the benchmark families implemented in the descriptor layer and
the planned families that still need descriptors. The grouping is provenance
based so planning can distinguish benchmarks inherited from prior comparison
suites from benchmarks added for repository-specific experiments.

Implemented means there is a benchmark descriptor under `configs/benchmarks/`
and the benchmark can be selected in `library:target` form. Planned means the
benchmark is part of the intended evaluation set, appears in bundled source
trees, or appears in prior artifact data, but does not yet have a complete
selector in the repository benchmark pipeline.

Detailed model and comparison notes live under `models/`:

- `models/modexp.md` for modular-exponentiation benchmarks.
- `models/constantine.md` for Constantine-style known-violation benchmarks.
- `models/bounded.md` for bounded verification benchmarks from BINSEC/Rel2 and
  ABACUS constant-time-claim rows.
- `models/abacus.md` for direct ABACUS benchmark targets and their repository
  modeling differences.
- `models/other.md` for repository benchmarks that do not currently belong to
  the four provenance groups above.

## Grouping Rules And Ambiguities

The primary grouping is by intended comparison role, not by selector name. Each
selector is one target, so mixed former selectors are represented by multiple
precise `library:target` rows.

Known ambiguities:

- BearSSL AES/DES rows are split by role. `bearssl:aes_big` and
  `bearssl:des_tab` are counted with Constantine-style known violations;
  `bearssl:aes_ct` and `bearssl:des_ct` are counted with bounded verification.
- RSA, ECDSA, AES, and DES library targets can overlap ABACUS by algorithm and
  library family, but only direct ABACUS benchmark targets are grouped in the
  ABACUS campaign. The active repository wrappers are not exact ABACUS
  reproductions, and the differences are documented in `models/abacus.md`.
- Direction matters for symmetric and RSA rows. The active OpenSSL, mbedTLS,
  Libgcrypt, and BearSSL AES/DES wrappers listed here are encryption wrappers
  unless the target name explicitly says decrypt or unpad. RSA stage rows are
  decrypt/private-operation wrappers. This differs from parts of
  BINSEC/Rel2 and ABACUS: BINSEC/Rel2 often benchmarks decryption or internal
  expanded-schedule entry points, while several ABACUS symmetric rows trace
  encryption drivers. When the source suites disagree or use awkward trace
  boundaries, repository defaults use shared valid keys, shared fixed plaintext
  for encryption inputs, generated ciphertext for decrypt inputs, and zero IVs.
- `libsodium:curve25519` is a repository-only comparable routine, not a BINSEC
  HACL* Curve25519 replay. The HACL* replay belongs under `hacl:curve25519`.
  Keep it in the Other group unless a comparison source explicitly uses the same
  Libsodium wrapper.
- HACL Chacha20, Curve25519, SHA256, and SHA512 use the Cryspen
  `hacl-packages` `c-v0.6.0` generated C sources under
  `benchmarks/hacl-packages-c-v0.6.0/src/`.

## Current Descriptor Set

| Selector | Primary group |
| --- | --- |
| `appliedcryp:3way` | Constantine-style known violations. |
| `appliedcryp:des` | Constantine-style known violations. |
| `appliedcryp:loki91` | Constantine-style known violations. |
| `bearssl:aes_big` | Constantine-style known violations through the BINSEC/Rel2 row. |
| `bearssl:aes_ct` | Bounded verification. |
| `bearssl:des_ct` | Bounded verification. |
| `bearssl:des_tab` | Constantine-style known violations through the BINSEC/Rel2 row. |
| `bearssl:modexp` | Modular exponentiation. |
| `bearssl:rsa_i31_private` | Other RSA stage benchmark. |
| `bearssl:rsa_i31_oaep_decrypt` | Other RSA stage benchmark. |
| `bearssl:rsa_ssl_decrypt` | Other RSA stage benchmark. |
| `bearssl:rsa_oaep_unpad` | Other RSA stage benchmark. |
| `ghostrider:findmax` | Constantine-style known violations. |
| `ghostrider:matmul` | Constantine-style known violations. |
| `hacl_modexp:modexp32` | Other HACL bignum benchmark. |
| `hacl_modexp:modexp64` | Other HACL bignum benchmark. |
| `hacl:chacha20` | Bounded verification. |
| `hacl:curve25519` | Bounded verification. |
| `hacl:sha256` | Bounded verification. |
| `hacl:sha512` | Bounded verification. |
| `libg:des` | Constantine-style known violations. |
| `libgcrypt:modexp` | Modular exponentiation. |
| `libgcrypt:modexp_sliced` | Modular exponentiation. |
| `libgcrypt:gcry_pk_decrypt_pkcs1` | Repository-only Libgcrypt RSA alternate mode. |
| `libgcrypt:gcry_pk_decrypt_oaep` | Repository-only Libgcrypt RSA alternate mode. |
| `libgcrypt:gcry_pk_decrypt_raw` | Direct ABACUS RSA target. |
| `libgcrypt:rsa_pkcs1_decode_for_enc` | Repository-only Libgcrypt RSA padding helper. |
| `libgcrypt:rsa_oaep_decode` | Repository-only Libgcrypt RSA padding helper. |
| `libgcrypt:aes_encrypt` | Repository-only Libgcrypt symmetric routine. |
| `libgcrypt:des_encrypt` | Repository-only Libgcrypt symmetric routine. |
| `libgcrypt:ecdsa_sign` | Repository-only Libgcrypt ECDSA. |
| `libsodium:curve25519_scalarmult` | Other repository benchmark. |
| `libsodium:salsa20` | Bounded verification. |
| `libsodium:chacha20` | Bounded verification. |
| `libsodium:sha256` | Bounded verification. |
| `libsodium:sha512` | Bounded verification. |
| `mbedtls:modexp` | Modular exponentiation. |
| `mbedtls:modexp_sliced` | Modular exponentiation. |
| `mbedtls:rsa_private` | Repository-only mbedTLS RSA core target. |
| `mbedtls:rsa_rsaes_pkcs1_v15_decrypt` | Direct ABACUS RSA target. |
| `mbedtls:rsa_rsaes_oaep_decrypt` | Repository-only mbedTLS RSA alternate mode. |
| `mbedtls:pkcs1_v15_unpadding` | Repository-only mbedTLS RSA padding helper. |
| `mbedtls:aes_encrypt` | Direct ABACUS symmetric target. |
| `mbedtls:des_encrypt` | Direct ABACUS symmetric target. |
| `mbedtls:ecdsa_sign` | Direct ABACUS ECDSA target. |
| `monocypher:chacha20` | Bounded verification. |
| `monocypher:poly1305` | Bounded verification. |
| `monocypher:argon2i` | Bounded verification. |
| `monocypher:ed25519` | Bounded verification. |
| `openssl:recp` | Modular exponentiation. |
| `openssl:mont` | Modular exponentiation. |
| `openssl:mont_consttime` | Modular exponentiation. |
| `openssl:mont_word` | Modular exponentiation. |
| `openssl:recp_sliced` | Modular exponentiation. |
| `openssl:mont_sliced` | Modular exponentiation. |
| `openssl:mont_word_sliced` | Modular exponentiation. |
| `openssl:rsa_private_core` | Repository-only OpenSSL RSA core target. |
| `openssl:padding_check_pkcs1_type_2` | Repository-only OpenSSL RSA padding helper. |
| `openssl:padding_check_oaep_mgf1` | Repository-only OpenSSL RSA padding helper. |
| `openssl:padding_check_sslv23` | Repository-only OpenSSL RSA padding helper. |
| `openssl:rsa_private_decrypt_pkcs1` | Repository-only OpenSSL RSA alternate mode. |
| `openssl:rsa_private_decrypt_oaep` | Direct ABACUS RSA target. |
| `openssl:rsa_private_decrypt_sslv23` | Repository-only OpenSSL RSA alternate mode. |
| `openssl:rsa_private_decrypt_no_padding` | Repository-only OpenSSL RSA alternate mode. |
| `openssl:aes_encrypt` | Direct ABACUS symmetric target. |
| `openssl:des_encrypt` | Direct ABACUS symmetric target. |
| `openssl:ecdsa_sign` | Direct ABACUS ECDSA target. |
| `openssl_almeida:tls_rempad_luk13` | Constantine-style known violations through the BINSEC/Rel2 row. |
| `pycrypto:arc4` | Constantine-style known violations. |

## Benchmark Groups

### Modular Exponentiation

This group contains direct modular-exponentiation backends. It is implemented
for the libraries below. The sliced targets also belong here because the
repository currently slices only modular-exponentiation implementations.

| Library | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL 0.6 | Implemented | `bearssl:modexp`. |
| Mbed TLS 3.2.1 | Implemented | `mbedtls:modexp`; sliced target `mbedtls:modexp_sliced`. |
| Libgcrypt 1.10.1 | Implemented | `libgcrypt:modexp`; sliced target `libgcrypt:modexp_sliced`. |
| OpenSSL 1.1.1q | Implemented | `openssl:recp`, `openssl:mont`, `openssl:mont_consttime`, `openssl:mont_word`; sliced targets `openssl:recp_sliced`, `openssl:mont_sliced`, `openssl:mont_word_sliced`. |

The shared model is a secret exponent with public base and modulus. See
`models/modexp.md`.

### Constantine-Style Known Violations

This group is the historical known-violation set currently represented in the
repository. It includes the BINSEC rows that Constantine also used.

| Source group | Selectors |
| --- | --- |
| Applied Crypto | `appliedcryp:3way`, `appliedcryp:des`, `appliedcryp:loki91` |
| GhostRider | `ghostrider:findmax`, `ghostrider:matmul` |
| Image-table Libgcrypt subset | `libg:des` |
| PyCrypto | `pycrypto:arc4` |
| BINSEC/Rel2 rows also used by Constantine | `openssl_almeida:tls_rempad_luk13`, `bearssl:aes_big`, `bearssl:des_tab` |

The attached image/table data includes more historical suites than the subset
currently represented by descriptors. These include Chronos, S-CP `cast-ssl`,
Botan, remaining PyCrypto targets, remaining image-table Libgcrypt targets, and
remaining GhostRider rows beyond `findmax` and `matmul`. See
`models/constantine.md`.

### Bounded Verification Benchmarks

This group covers bounded verification of functions with constant-time claims
from the BINSEC/Rel2 and ABACUS benchmark spaces.

| Source group | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL 0.6 AES-CT | Implemented | `bearssl:aes_ct`. |
| BearSSL 0.6 DES-CT | Implemented | `bearssl:des_ct`. |
| Libsodium | Implemented | `libsodium:salsa20`, `libsodium:chacha20`, `libsodium:sha256`, and `libsodium:sha512`. |
| HACL Packages C v0.6 | Implemented | `hacl:chacha20`, `hacl:curve25519`, `hacl:sha256`, and `hacl:sha512`. |
| Monocypher 3.0.0 | Implemented | `monocypher:chacha20`, `monocypher:poly1305`, `monocypher:argon2i`, and `monocypher:ed25519`. |

The repository plan for this group is to keep fixed function boundaries and
buffer sizes while documenting where semantic secret/public roles differ from
the source wrapper input schedule. See `models/bounded.md` for the current
differences.

### ABACUS Benchmarks

This group covers benchmarks from the ABACUS comparison space. The repository
has descriptors for many corresponding algorithms and libraries, but most are
not exact ABACUS driver reproductions.

| Source group | Status | Descriptor coverage |
| --- | --- | --- |
| OpenSSL AES/DES | Implemented | `openssl:aes_encrypt` and `openssl:des_encrypt`. |
| OpenSSL ECDSA | Implemented | `openssl:ecdsa_sign`, matching the ABACUS curve size. |
| OpenSSL RSA | Implemented | `openssl:rsa_private_decrypt_oaep`; this matches the ABACUS OpenSSL RSA driver, which decrypts an OAEP ciphertext through `RSA_private_decrypt`. |
| Mbed TLS RSA | Implemented | `mbedtls:rsa_rsaes_pkcs1_v15_decrypt`; this is the direct repository target for the ABACUS mbedTLS RSA row. |
| Mbed TLS AES/DES/ECDSA | Implemented | `mbedtls:aes_encrypt`, `mbedtls:des_encrypt`, `mbedtls:ecdsa_sign`; implemented against mbedTLS 3.2.1 rather than the ABACUS 2.5/2.15 source trees. |
| Libgcrypt RSA | Implemented | `libgcrypt:gcry_pk_decrypt_raw`; this matches the ABACUS Libgcrypt driver, which encrypts raw data and calls `gcry_pk_decrypt`. |
See `models/abacus.md` for exact function-boundary, version, input, and
reconciliation notes.

### Other Repository Benchmarks

This group contains implemented benchmarks that are useful in the repository but
are not cleanly classified as one of the prior comparison groups above.

| Source group | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL RSA stages | Implemented | `bearssl:rsa_i31_private`, `bearssl:rsa_i31_oaep_decrypt`, `bearssl:rsa_ssl_decrypt`, `bearssl:rsa_oaep_unpad`. |
| HACL Packages C bignum modexp | Implemented | `hacl_modexp:modexp32`, `hacl_modexp:modexp64`. |
| Libgcrypt AES/DES/ECDSA | Implemented | `libgcrypt:aes_encrypt`, `libgcrypt:des_encrypt`, and `libgcrypt:ecdsa_sign`; repository-only comparable targets because the checked ABACUS artifact data only contains Libgcrypt RSA rows. |
| Libsodium Curve25519 | Implemented | `libsodium:curve25519_scalarmult` as a repository-only comparable routine. |

See `models/other.md` for the rationale and how these should be reported
relative to the comparison suites.

## Current Classification Gaps

- Add separate bounded-size targets for `bearssl:aes_ct` and `bearssl:des_ct`
  before claiming parity with BINSEC's input-size scalability matrix. The
  current targets implement the fixed 32-byte AES and 16-byte DES wrappers.
- Keep Libsodium, HACL, and Monocypher bounded descriptors aligned with their
  documented repository stream models. Add separate exact-parity selectors if a
  run needs to copy an external wrapper's high plaintext or output-entry
  schedule.
- Add `abacus_compat` targets if exact ABACUS parity is required for
  key-schedule-only AES/DES, full-CRT RSA, and ECDSA nonce handling.