# Benchmark Inventory

This page records the benchmark families implemented in the descriptor layer and
the planned families that still need descriptors. The grouping is provenance
based so planning can distinguish benchmarks inherited from prior comparison
suites from benchmarks added for repository-specific experiments.

Implemented means there is a benchmark descriptor under `configs/benchmarks/`
and the benchmark can be selected in `library:variant` form. Planned means the
benchmark is part of the intended evaluation set, appears in bundled source
trees, or appears in prior artifact data, but does not yet have a complete
selector in the repository benchmark pipeline.

Detailed model and comparison notes live under `models/`:

- `models/modexp.md` for modular-exponentiation benchmarks.
- `models/constantine.md` for Constantine-style known-violation benchmarks.
- `models/bounded.md` for bounded verification benchmarks from BINSEC/Rel2 and
  ABACUS constant-time-claim rows.
- `models/abacus.md` for ABACUS-overlap benchmarks.
- `models/other.md` for repository benchmarks that do not currently belong to
  the four provenance groups above.

## Grouping Rules And Ambiguities

The primary grouping is by intended comparison role, not by selector name. A
single selector may contain targets from more than one group.

Known ambiguities:

- `bearssl:aes_des` spans groups. `aes_big` and `des_tab` are counted with the
  Constantine-style known-violation rows because Constantine uses these BINSEC
  rows. `aes_ct` is counted with the bounded verification group because it was
  a bounded constant-time-claim benchmark in BINSEC.
- `bearssl:default` is a legacy combined selector and spans modular
  exponentiation, Constantine, and bounded verification roles. Prefer focused
  selectors for new campaigns.
- RSA, ECDSA, AES, and DES library targets overlap ABACUS by algorithm and
  library family, but the active repository wrappers are not exact ABACUS
  reproductions. They are grouped as ABACUS-overlap benchmarks and the
  differences are documented in `models/abacus.md`.
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

| Selector | Targets | Primary group |
| --- | --- | --- |
| `appliedcryp:default` | `3way`, `des`, `loki91` | Constantine-style known violations. |
| `bearssl:default` | `aes_big`, `aes_ct`, `des_ct`, `modexp`, `des_tab` | Legacy mixed selector; use focused selectors. |
| `bearssl:aes_des` | `aes_big`, `aes_ct`, `des_ct`, `des_tab` | Mixed: Constantine for `aes_big`/`des_tab`; bounded verification for `aes_ct`/`des_ct`. |
| `bearssl:modexp` | `modexp` | Modular exponentiation. |
| `bearssl:rsa_stages` | `rsa_i31_private`, `rsa_i31_oaep_decrypt`, `rsa_ssl_decrypt`, `rsa_oaep_unpad` | Other RSA stage benchmarks; related to ABACUS RSA by algorithm but not an ABACUS suite row. |
| `ghostrider:default` | `findmax`, `matmul` | Constantine-style known violations. |
| `hacl_modexp:default` | `modexp32`, `modexp64` | Other HACL bignum benchmark. |
| `hacl:chacha20` | `chacha20` | Bounded verification. |
| `hacl:curve25519` | `curve25519` | Bounded verification. |
| `hacl:sha256` | `sha256` | Bounded verification. |
| `hacl:sha512` | `sha512` | Bounded verification. |
| `libg:default` | `des` | Constantine-style known violations. |
| `libgcrypt:default` | `modexp` | Modular exponentiation. |
| `libgcrypt:aes_des` | `aes_encrypt`, `des_encrypt` | Repository-only Libgcrypt symmetric routines; ABACUS source-set caveat below. |
| `libgcrypt:ecdsa` | `ecdsa_sign` | Repository-only Libgcrypt ECDSA; ABACUS source-set caveat below. |
| `libgcrypt:rsa_stages` | `gcry_pk_decrypt_pkcs1`, `gcry_pk_decrypt_oaep`, `gcry_pk_decrypt_raw`, `rsa_pkcs1_decode_for_enc`, `rsa_oaep_decode` | ABACUS-overlap RSA. |
| `libgcrypt:sliced` | `modexp` | Modular exponentiation. |
| `libsodium:chacha20` | `chacha20` | Bounded verification. |
| `libsodium:curve25519` | `curve25519_scalarmult` | Other repository benchmark. |
| `libsodium:salsa20` | `salsa20` | Bounded verification. |
| `libsodium:sha256` | `sha256` | Bounded verification. |
| `libsodium:sha512` | `sha512` | Bounded verification. |
| `mbedtls:default` | `modexp`, `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | Mixed: modular exponentiation plus ABACUS-overlap RSA. |
| `mbedtls:rsa_stages` | `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | ABACUS-overlap RSA. |
| `mbedtls:rsa_decrypt_only` | `rsa_private`, `rsa_rsaes_pkcs1_v15_decrypt`, `rsa_rsaes_oaep_decrypt`, `pkcs1_v15_unpadding` | ABACUS-overlap RSA. |
| `mbedtls:aes_des` | `aes_encrypt`, `des_encrypt` | ABACUS-overlap library symmetric routines. |
| `mbedtls:ecdsa` | `ecdsa_sign` | ABACUS-overlap ECDSA. |
| `mbedtls:sliced` | `modexp` | Modular exponentiation. |
| `monocypher:argon2i` | `argon2i` | Bounded verification. |
| `monocypher:chacha20` | `chacha20` | Bounded verification. |
| `monocypher:ed25519` | `ed25519` | Bounded verification. |
| `monocypher:poly1305` | `poly1305` | Bounded verification. |
| `openssl:default` | `recp`, `mont`, `mont_consttime`, `mont_word` | Modular exponentiation. |
| `openssl:aes_des` | `aes_encrypt`, `des_encrypt` | ABACUS-overlap library symmetric routines. |
| `openssl:ecdsa` | `ecdsa_sign` | ABACUS-overlap ECDSA. |
| `openssl:rsa_stages` | `rsa_private_core`, `padding_check_pkcs1_type_2`, `padding_check_oaep_mgf1`, `padding_check_sslv23`, `rsa_private_decrypt_pkcs1`, `rsa_private_decrypt_oaep`, `rsa_private_decrypt_sslv23`, `rsa_private_decrypt_no_padding` | ABACUS-overlap RSA. |
| `openssl:sliced` | `recp`, `mont`, `mont_word` | Modular exponentiation. |
| `openssl_almeida:default` | `tls_rempad_luk13` | Constantine-style known violations through the BINSEC/Rel2 row. |
| `pycrypto:default` | `arc4` | Constantine-style known violations. |

## Benchmark Groups

### Modular Exponentiation

This group contains direct modular-exponentiation backends. It is implemented
for the libraries below. The sliced variants also belong here because the
repository currently slices only modular-exponentiation implementations.

| Library | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL 0.6 | Implemented | `bearssl:modexp` and the legacy `bearssl:default` selector. |
| Mbed TLS 3.2.1 | Implemented | `mbedtls:default`; sliced variant in `mbedtls:sliced`. |
| Libgcrypt 1.10.1 | Implemented | `libgcrypt:default`; sliced variant in `libgcrypt:sliced`. |
| OpenSSL 1.1.1q | Implemented | `openssl:default`; sliced variant in `openssl:sliced`. |

The shared model is a secret exponent with public base and modulus. See
`models/modexp.md`.

### Constantine-Style Known Violations

This group is the historical known-violation set currently represented in the
repository. It includes the BINSEC rows that Constantine also used.

| Source group | Implemented targets | Selector |
| --- | --- | --- |
| Applied Crypto | `3way`, `des`, `loki91` | `appliedcryp:default` |
| GhostRider | `findmax`, `matmul` | `ghostrider:default` |
| Image-table Libgcrypt subset | `des` | `libg:default` |
| PyCrypto | `arc4` | `pycrypto:default` |
| BINSEC/Rel2 rows also used by Constantine | `tls_rempad_luk13`, `aes_big`, `des_tab` | `openssl_almeida:default`, `bearssl:aes_des` |

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
| BearSSL 0.6 AES-CT | Implemented | `bearssl:aes_des` includes `aes_ct`. |
| BearSSL 0.6 DES-CT | Implemented | `bearssl:aes_des` includes `des_ct`. |
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
| OpenSSL AES/DES | Implemented | `openssl:aes_des` covers AES-128 block encryption and single-DES encryption. |
| OpenSSL ECDSA | Implemented | `openssl:ecdsa` covers 192-bit ECDSA signing, matching the ABACUS curve size. |
| OpenSSL RSA | Implemented | `openssl:rsa_stages`. |
| Mbed TLS RSA | Implemented | `mbedtls:rsa_stages` and `mbedtls:rsa_decrypt_only`. |
| Mbed TLS AES/DES/ECDSA | Implemented | `mbedtls:aes_des` and `mbedtls:ecdsa`; implemented against mbedTLS 3.2.1 rather than the ABACUS 2.5/2.15 source trees. |
| Libgcrypt RSA | Implemented | `libgcrypt:rsa_stages`. |
| Libgcrypt AES/DES/ECDSA | Repository-only overlap | `libgcrypt:aes_des` and `libgcrypt:ecdsa` exist, but the checked ABACUS artifact data only contains Libgcrypt RSA rows. Keep this provenance caveat visible when reporting them. |
See `models/abacus.md` for exact function-boundary, version, input, and
reconciliation notes.

### Other Repository Benchmarks

This group contains implemented benchmarks that are useful in the repository but
are not cleanly classified as one of the prior comparison groups above.

| Source group | Status | Descriptor coverage |
| --- | --- | --- |
| BearSSL RSA stages | Implemented | `bearssl:rsa_stages` covers BearSSL RSA primitive, full decrypt, and OAEP unpadding stages. |
| HACL Packages C bignum modexp | Implemented | `hacl_modexp:default` covers 32-bit and 64-bit bignum modular exponentiation targets. |
| Libsodium Curve25519 | Implemented | `libsodium:curve25519` covers `curve25519_scalarmult` as a repository-only comparable routine. |

See `models/other.md` for the rationale and how these should be reported
relative to the comparison suites.

## Current Classification Gaps

- Add separate bounded-size selectors for `bearssl:aes_ct` and `bearssl:des_ct`
  before claiming parity with BINSEC's input-size scalability matrix. The
  default selector implements the fixed 32-byte AES and 16-byte DES wrappers.
- Keep Libsodium, HACL, and Monocypher bounded descriptors aligned with their
  documented repository stream models. Add separate exact-parity selectors if a
  run needs to copy an external wrapper's high plaintext or output-entry
  schedule.
- Add `abacus_compat` selectors if exact ABACUS parity is required for
  key-schedule-only AES/DES, full-CRT RSA, and ECDSA nonce handling.