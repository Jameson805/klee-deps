# Symmetric And Known-Violation Benchmark Models

This page documents the input models for the symmetric-routine benchmarks that
are treated as historical known-violation or comparison rows. These targets are
more varied than the RSA and modular-exponentiation families: some model
cryptographic library routines, while others intentionally preserve old
benchmark shapes from constant-time comparison suites. BearSSL `aes_ct` shares
the AES wrapper input shape, but is documented with the functions carrying
constant-time claims in `constant-time-claims.md`.

The exact byte values are owned by the runner configs under
`../../../configs/runner/`. This page records the kind of values used and which
inputs are symbolic.

## Model Summary

| Family | Targets | Secret model | Public model | Main question |
| --- | --- | --- | --- | --- |
| BearSSL AES/DES CBC | `aes_big`, `des_tab` | Expanded schedule prefix and data buffer are symbolic secrets. | No public buffers. | Do table-driven symmetric routines branch or access memory based on modeled secret bytes? |
| Libgcrypt AES/DES | Planned AES and DES targets. | Raw key and one-block data buffer should be symbolic secrets unless the descriptor deliberately models public plaintext. | No public buffers in the first planned model. | Compare real Libgcrypt cipher implementations with the historical image-table Libgcrypt DES row. |
| OpenSSL AES/DES | Planned AES and DES targets. | Raw key and one-block data buffer should be symbolic secrets unless the descriptor deliberately models public plaintext. | No public buffers in the first planned model. | Compare OpenSSL C cipher implementations with existing AES/DES benchmark rows. |
| Applied Crypto | `3way`, `des`, `loki91` | Key and data are symbolic secrets. | No public buffers. | Reproduce known or expected leakage from historical cipher code. |
| GhostRider | `findmax`, `matmul` | Whole data array is symbolic secret. | No public buffers. | Exercise known data-dependent microbenchmark behavior. |
| Image-table Libgcrypt subset | `des` | Key and data are symbolic secrets. | No public buffers. | Preserve the historical Libgcrypt DES benchmark row represented by `benchmarks/libg`. |
| PyCrypto | `arc4` | Key is symbolic secret. | No public buffers. | Preserve the historical ARC4 key-dependent benchmark shape. |
| OpenSSL Almeida TLS padding | `tls_rempad_luk13` | TLS record data is symbolic secret. | Public control scalars can be fixed or symbolic. | Model TLS record padding removal with secret record contents and public protocol controls. |

Most of these wrappers intentionally do not distinguish secret key from secret
message data. They model the older benchmark convention where all data that can
drive leakage is treated as secret. That is useful for reproducing historical
tool comparisons, but it is less precise than a deployed cryptographic API
threat model.

## BearSSL AES/DES CBC

This section covers `aes_big` and `des_tab` as historical comparison rows.
BearSSL `aes_ct` uses the same reduced-round AES wrapper input shape as
`aes_big`, but is grouped with the constant-time-claim routines.

Generic inputs:

| Input | Meaning in the wrapper | Active benchmark value |
| --- | --- | --- |
| `skey` | Expanded cipher schedule prefix consumed by the reduced-round wrapper. | Symbolic secret buffer. AES uses 48 bytes; DES uses 256 bytes. |
| `data` | CBC input data. | Symbolic secret buffer. AES uses 32 bytes; DES uses 16 bytes. |
| IV | CBC initialization vector. | Concrete all-zero value inside the wrapper; not a runner input. |
| `N_ROUND` | Reduced round count. | Concrete value `2`. |

Concrete defaults:

| Input class | Concrete default kind | Symbolic part | Rationale and caveats |
| --- | --- | --- | --- |
| AES schedule prefix | Large nonzero ABACUS seed covering the 48 bytes actually consumed. | Whole prefix is symbolic secret. | Models the existing schedule-based wrapper, not a raw AES key schedule API. |
| DES schedule prefix | Large nonzero ABACUS seed covering the 256 bytes actually consumed. | Whole prefix is symbolic secret. | Avoids making unused schedule storage symbolic while still covering consumed words. |
| Data buffer | Large nonzero ABACUS seed sized to the two-block input. | Whole buffer is symbolic secret. | Keeps the historical secret-data model. |
| Public inputs | None. | None. | `fix_pub` and `var_pub` exist for runner uniformity but have no public buffers for these targets. |

The important fidelity limitation is that `skey` is an expanded internal
schedule, not a semantic AES or DES key. A realistic raw-key model would call the
library key-schedule setup functions and make the raw key symbolic. The current
model preserves the original benchmark wrappers and makes only the schedule
prefix consumed at `N_ROUND=2` symbolic. See
`../../../benchmarks/bearssl/README.md` for the detailed schedule-prefix
rationale.

## Planned Libgcrypt And OpenSSL AES/DES

The planned Libgcrypt and OpenSSL AES/DES benchmarks should model real library
entrypoints, not the historical `libg:default` image-table row. Start with a
small encryption wrapper for each library and cipher, using a fixed operation
shape so tool results are comparable across libraries.

Planned generic inputs:

| Input | Meaning | Planned benchmark value |
| --- | --- | --- |
| `key` | Raw AES or DES key supplied to the library setup path. | Symbolic secret buffer. AES should start with a 16-byte key; DES should use the library's single-DES key width. |
| `data` | One block of plaintext or ciphertext consumed by the encryption path. | Symbolic secret buffer in the first model, matching the historical all-secret symmetric benchmark convention. |
| IV or mode controls | Public mode data if a block mode is used. | Prefer no IV by using a direct block or ECB-like wrapper; if CBC is needed, keep the IV concrete public. |

For Libgcrypt, the wrapper can either use the public `gcry_cipher_*` API or the
smallest direct cipher entrypoint that avoids unrelated dispatch while preserving
the same key setup and encryption behavior. For OpenSSL, build with assembly
disabled as the existing OpenSSL descriptor does, and use the C AES/DES
implementation paths.

The first descriptor should keep AES and DES in a focused selector per library.
Do not fold these targets into `libgcrypt:default` or `openssl:default`, because
those selectors currently identify modular-exponentiation campaigns.

## Applied Crypto, Libg DES, And PyCrypto

Generic inputs:

| Target group | Input model | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| Applied Crypto `3way` | 12-byte key plus 12-byte data. | All-zero ABACUS seeds. | Key and data are symbolic secrets. |
| Applied Crypto `des` | 24-byte key plus 8-byte data. | All-zero ABACUS seeds. | Key and data are symbolic secrets. |
| Applied Crypto `loki91` | 24-byte key plus 8-byte data. | All-zero ABACUS seeds. | Key and data are symbolic secrets. |
| `libg:default` / `des` | 24-byte key plus 64-byte data. | All-zero ABACUS seeds. | Key and data are symbolic secrets. |
| `pycrypto:default` / `arc4` | 32-byte key. | All-zero ABACUS seed. | Key is symbolic secret. |

These are historical benchmark models rather than carefully reconstructed modern
API use cases. The all-zero concrete seeds are ABACUS initialization values; the
actual symbolic domain is the full listed secret buffer. Because there are no
public buffers, `var_pub` does not add meaningful public variation for these
targets.

## GhostRider Microbenchmarks

Generic inputs:

| Target | Input model | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| `findmax` | 2000-byte data array. | All-zero ABACUS seed. | Whole data array is symbolic secret. |
| `matmul` | 32768-byte data array. | All-zero ABACUS seed. | Whole data array is symbolic secret. |

These targets are not cryptographic APIs. They are included to preserve known
data-dependent benchmark behavior from the comparison space. The realistic
attack story is therefore weaker than for RSA or TLS padding; the main value is
testing whether tools catch obvious secret-dependent control or memory behavior
in large data-oriented kernels.

## OpenSSL Almeida TLS Record Padding

Generic inputs:

| Input | Meaning | Active benchmark value |
| --- | --- | --- |
| `data` | TLS record payload and padding bytes. | 63-byte symbolic secret buffer. |
| `options` | Public OpenSSL/TLS option flags. | 4-byte public scalar; fixed zero in `fix_pub`, symbolic public in `var_pub`. |
| `s3_flags` | Public SSLv3/TLS state flags. | 4-byte public scalar; fixed zero in `fix_pub`, symbolic public in `var_pub`. |
| `flags` | Public record or context flags. | 4-byte public scalar; fixed zero in `fix_pub`, symbolic public in `var_pub`. |
| `slicing_cheat` | Public benchmark control used by the wrapper. | 4-byte public scalar; fixed zero in `fix_pub`, symbolic public in `var_pub`. |
| `block_size` | Public cipher block size. | Fixed to 16 in `fix_pub`, symbolic public in `var_pub`. |
| `mac_size` | Public MAC size. | Fixed to 20 in `fix_pub`, symbolic public in `var_pub`. |

The concrete secret seed is a repeated nonzero byte pattern. The public defaults
model an AES-CBC/HMAC-SHA1-like setting: 16-byte block size and 20-byte MAC,
with the other public control flags cleared. In `var_pub`, the public controls
are symbolic public inputs, so findings should be interpreted as leakage only
when behavior differs on the secret record data after accounting for public
control variation.

## Fidelity And Limits

What these models preserve:

- Historical benchmark input widths and wrapper shapes.
- Planned Libgcrypt/OpenSSL AES and DES benchmarks as real library models, not
  aliases for the historical image-table Libgcrypt row.
- Secret schedule/key/data buffers used by the original comparison targets.
- TLS rempad public controls that affect record-padding behavior.

What they simplify:

- Several targets make message data secret even when a deployed encryption API
  would treat some message bytes as public or attacker-controlled.
- Most historical targets use all-zero ABACUS seeds, which are initialization
  values rather than realistic concrete test vectors.
- BearSSL AES/DES models expanded schedules, not raw keys.
- Planned Libgcrypt/OpenSSL AES and DES models should use raw keys, so their
  findings will not be directly equivalent to BearSSL schedule-prefix findings.
- GhostRider targets are microbenchmarks, not cryptographic use cases.

## Validation Checklist

- Confirm whether a target is intended as a realistic library model or a
  historical benchmark reproduction.
- For BearSSL AES/DES, confirm the symbolic schedule length still matches the
  words consumed by `N_ROUND=2`.
- For planned Libgcrypt/OpenSSL AES and DES, confirm the wrapper reaches the
  intended C implementation path and does not silently select assembly,
  hardware acceleration, or unrelated dispatch code.
- For all-secret historical targets, record that `var_pub` does not add public
  input variation unless the descriptor defines public buffers.
- For TLS rempad, confirm fixed public defaults still represent the intended
  protocol setting and do not force a trivial branch.
- Revisit all-zero seeds if a target appears to execute only degenerate behavior
  before symbolization takes effect in a tool.