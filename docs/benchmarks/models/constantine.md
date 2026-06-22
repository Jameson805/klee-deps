# Constantine Benchmark Models

This page documents the Constantine-style known-violation group. The group
includes historical rows from Applied Crypto, GhostRider/Raccoon-style
microbenchmarks, the image-table Libgcrypt subset, PyCrypto, and the BINSEC/Rel2
rows that Constantine reused. Those reused rows are grouped here rather than in
`bounded.md` so each benchmark has one primary planning home.

## Implemented Set

| Selector | Targets | Model |
| --- | --- | --- |
| `appliedcryp:3way`, `appliedcryp:des`, `appliedcryp:loki91` | Historical cipher wrappers with key and data secret. |
| `ghostrider:findmax`, `ghostrider:matmul` | Data-dependent microbenchmarks with the whole data array secret. |
| `libg:des` | Historical image-table Libgcrypt DES row, distinct from real Libgcrypt 1.10.1. |
| `pycrypto:arc4` | Historical ARC4 key-dependent benchmark. |
| `bearssl:aes_big`, `bearssl:des_tab` | BINSEC/Rel2 rows reused by Constantine; reduced-round CBC wrappers. |
| `openssl_almeida:tls_rempad_luk13` | BINSEC/Rel2 TLS padding row reused by Constantine. |

## Detailed Input Variables

All rows in this group keep the historical known-violation framing: the data
that prior suites treated as high is still high unless the repository has an
explicit compatibility reason to split public and secret roles. The table below
describes the input buffers that the repository wrapper receives from the
repository runner. The symbolic column says when the wrapper receives symbolic
bytes instead of the listed concrete value.

| Selector target | Input variable | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| `appliedcryp:3way` | `key` | Secret | 12 bytes | First 12 bytes of the shared AES key. | `fix_pub` and `var_pub`. | Historical all-secret cipher wrapper. |
| `appliedcryp:3way` | `data` | Secret | 12 bytes | First 12 bytes of the shared deterministic plaintext. | `fix_pub` and `var_pub`. | Prior wrapper treats data as high, so the repository keeps it high. |
| `appliedcryp:des` | `key` | Secret | 24 bytes | Shared generated 3DES key. | `fix_pub` and `var_pub`. | Historical all-secret DES wrapper. |
| `appliedcryp:des` | `data` | Secret | 8 bytes | First 8 bytes of the shared deterministic plaintext. | `fix_pub` and `var_pub`. | Prior wrapper treats data as high. |
| `appliedcryp:loki91` | `key` | Secret | 24 bytes | Shared generated 3DES key. | `fix_pub` and `var_pub`. | Historical all-secret LOKI91 wrapper. |
| `appliedcryp:loki91` | `data` | Secret | 8 bytes | First 8 bytes of the shared deterministic plaintext. | `fix_pub` and `var_pub`. | Prior wrapper treats data as high. |
| `ghostrider:findmax` | `data` | Secret | 2000 bytes | Repeated `0x5a` concrete trace seed. | `fix_pub` and `var_pub`. | Data-dependent microbenchmark; the whole array is the high input. |
| `ghostrider:matmul` | `data` | Secret | 32768 bytes | Repeated `0x5a` concrete trace seed. | `fix_pub` and `var_pub`. | Data-dependent microbenchmark; the whole matrix buffer is high. |
| `libg:des` | `key` | Secret | 24 bytes | Shared generated 3DES key. | `fix_pub` and `var_pub`. | Historical image-table Libgcrypt DES row, not real Libgcrypt 1.10.1. |
| `libg:des` | `data` | Secret | 64 bytes | Shared deterministic plaintext prefix, repeated to 64 bytes. | `fix_pub` and `var_pub`. | Historical image-table row treats the data buffer as high. |
| `pycrypto:arc4` | `key` | Secret | 32 bytes | Shared deterministic stream-cipher key. | `fix_pub` and `var_pub`. | ARC4 key-dependent benchmark; there is no public input. |
| `bearssl:aes_big` | `skey` | Secret | 240 bytes | Valid AES expanded schedule generated from the shared AES-128 key. | `fix_pub` and `var_pub`. | Matches the full Constantine/BINSEC schedule size while starting ABACUS from schedule-shaped bytes. |
| `bearssl:aes_big` | `data` | Public | 32 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Repository wrapper receives public CBC data; fixed mode avoids an all-zero block. |
| `bearssl:aes_big` | `iv` | Public | 16 bytes | All zero. | `var_pub`. | Repository wrapper receives IV as public input. |
| `bearssl:des_tab` | `skey` | Secret | 384 bytes | Valid 3DES expanded schedule generated from the shared generated 3DES key. | `fix_pub` and `var_pub`. | Matches the full Constantine/BINSEC schedule size while starting ABACUS from schedule-shaped bytes. |
| `bearssl:des_tab` | `data` | Public | 16 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Repository wrapper receives public CBC data; fixed mode avoids an all-zero block. |
| `bearssl:des_tab` | `iv` | Public | 8 bytes | All zero. | `var_pub`. | Repository wrapper receives IV as public input. |
| `openssl_almeida:tls_rempad_luk13` | `data` | Secret | 63 bytes | `0x0f` pattern seed. | `fix_pub` and `var_pub`. | Matches the high TLS record-data input shape. |
| `openssl_almeida:tls_rempad_luk13` | `options` | Public | 4 bytes | `0`. | `var_pub`. | Canonical fixed-public TLS options baseline. |
| `openssl_almeida:tls_rempad_luk13` | `s3_flags` | Public | 4 bytes | `0`. | `var_pub`. | Canonical fixed-public SSL state flag baseline. |
| `openssl_almeida:tls_rempad_luk13` | `flags` | Public | 4 bytes | `0`. | `var_pub`. | Wrapper control is public; fixed mode keeps it stable. |
| `openssl_almeida:tls_rempad_luk13` | `slicing_cheat` | Public | 4 bytes | `0`. | `var_pub`. | Public sliced-wrapper control; fixed mode disables it. |
| `openssl_almeida:tls_rempad_luk13` | `mac_size` | Public | 4 bytes | `20`. | `var_pub`. | SHA-1 MAC length for the Lucky13 TLS padding scenario. |
| `openssl_almeida:tls_rempad_luk13` | `block_size` | Public constant | 4 bytes | `16`. | Never. | TLS block size is an internal constant, not a runner public input. |

## Historical Cipher And Microbenchmark Inputs

| Target group | Inputs | Secret inputs | Public inputs | Notes |
| --- | --- | --- | --- | --- |
| Applied Crypto `3way` | 12-byte key, 12-byte data. | Key and data. | None. | All-zero ABACUS seed values; symbolic domain is the full listed buffers. |
| Applied Crypto `des` | 24-byte key, 8-byte data. | Key and data. | None. | Historical all-secret model. |
| Applied Crypto `loki91` | 24-byte key, 8-byte data. | Key and data. | None. | Historical all-secret model. |
| `libg:des` | 24-byte key, 64-byte data. | Key and data. | None. | Represents the old image-table Libgcrypt row, not the real Libgcrypt tree. |
| `pycrypto:arc4` | 32-byte key. | Key. | None. | Preserves the historical ARC4 key-dependent benchmark shape. |
| GhostRider `findmax` | 2000-byte data array. | Whole data array. | None. | Non-cryptographic data-dependent kernel; ABACUS concrete trace seed is repeated `0x5a`. |
| GhostRider `matmul` | 32768-byte data array. | Whole data array. | None. | Non-cryptographic data-dependent kernel; ABACUS concrete trace seed is repeated `0x5a`. |

These targets intentionally follow older benchmark conventions. They often mark
all data that can drive control flow or memory access as secret, even when a
deployed API would distinguish key material from public or attacker-controlled
message data.

## BearSSL `aes_big` And `des_tab`

These are Constantine rows in this taxonomy. Constantine reuses the BINSEC
BearSSL table-driven wrappers directly for these two targets.

| Target | Invoked algorithm | Constantine/BINSEC inputs | Repository difference |
| --- | --- | --- | --- |
| `aes_big` | `br_aes_big_cbcenc_run`, `N_ROUND=2`, CBC data length 32 bytes. | Secret `ctx.skey` is declared as 240 bytes; secret `data` is 32 bytes; IV is fixed zero stack data. | Same function, round count, data length, and schedule size. Repository treats `data` and IV as public inputs. |
| `des_tab` | `br_des_tab_cbcenc_run`, `N_ROUND=2`, CBC data length 16 bytes. | Secret `ctx.skey` is declared as 384 bytes; secret `data` is 16 bytes; IV is fixed zero stack data. | Same function, round count, data length, and schedule size. Repository treats `data` and IV as public inputs. |

Repository input details:

| Target | Input | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| `aes_big` | `skey` | Secret | 240 bytes | Valid BearSSL AES expanded schedule from the shared AES-128 key. | `fix_pub` and `var_pub`. | Matches the full `ctx.skey` size in the Constantine/BINSEC wrapper while giving concrete replay a schedule-shaped starting point. |
| `aes_big` | `data` | Public | 32 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Nonzero fixed-public baseline. |
| `aes_big` | IV | Public | 16 bytes | All zero. | `var_pub`. | Repository wrapper receives IV as a public input. |
| `des_tab` | `skey` | Secret | 384 bytes | Valid BearSSL 3DES expanded schedule from the shared generated 3DES key. | `fix_pub` and `var_pub`. | Matches the full `ctx.skey` size in the Constantine/BINSEC wrapper while giving concrete replay a schedule-shaped starting point. |
| `des_tab` | `data` | Public | 16 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Nonzero fixed-public baseline. |
| `des_tab` | IV | Public | 8 bytes | All zero. | `var_pub`. | Repository wrapper receives IV as a public input. |

The full schedule sizes keep the repository aligned with the Constantine/BINSEC
wrappers. Treating CBC data and IV as public keeps the BearSSL AES/DES rows
aligned with the repository's non-Constantine symmetric setup. `fix_pub` fixes
the public inputs to the listed concrete values; it does not fix secret inputs.
ABACUS still needs a concrete seed for each secret input before symbolization;
the schedule seeds above are generated with
`python -m tools.utilities.generate_bearssl_schedule_defaults`.
Use secret data and fixed stack IV only for an exact replay experiment.

Runner configuration: these targets use benchmark-local runner profiles because
their inputs are expanded schedule buffers, not raw semantic AES or DES keys.
Each target has one `default` preset with full schedule widths and target-local
generated artifacts under the BearSSL benchmark directory. Mod-exp-style
`size_N` presets would describe partial schedule prefixes, so they are avoided.

## OpenSSL Almeida `tls_rempad_luk13`

This row is also a BINSEC/Rel2 source, but it is grouped here because
Constantine reused it.

| Input | Kind | Size | Concrete value | Symbolic when | External BINSEC model | Difference |
| --- | --- | --- | --- | --- | --- | --- |
| `data` | Secret | 63 bytes | N/A. | `fix_pub` and `var_pub`. | 63-byte high input. | Same size and secrecy. |
| `options` | Public | 4 bytes | `0`. | `var_pub`. | 4-byte low input. | Public-symbolic runs match the low input; fixed-public runs use zero. |
| `s3_flags` | Public | 4 bytes | `0`. | `var_pub`. | 4-byte low input. | Public-symbolic runs match the low input; fixed-public runs use zero. |
| `flags` | Public | 4 bytes | `0`. | `var_pub`. | 4-byte low input. | Public-symbolic runs match the low input; fixed-public runs use zero. |
| `slicing_cheat` | Public | 4 bytes | `0`. | `var_pub`. | 4-byte low input. | Public-symbolic runs match the low input; fixed-public runs use zero. |
| `block_size` | Public constant | 4 bytes | `16`. | Never. | Fixed `16`. | Same. This is not a runner public input. |
| `mac_size` | Public | 4 bytes | `20`. | `var_pub`. | 4-byte low input. | Public-symbolic runs match the low input; fixed-public runs use the SHA-1 MAC length from the Lucky13 TLS padding scenario. |

Best reconciliation: keep both modes, but report the mode precisely. `fix_pub`
fixes the public inputs to the concrete values listed above. `var_pub` matches
the external high/low-input split while keeping `block_size` fixed at 16, as in
the external wrapper.

The all-zero `fix_pub` values for `options`, `s3_flags`, `flags`, and
`slicing_cheat` are a reasonable canonical fixed-public baseline for this sliced
wrapper, not a claim that zero is representative of every TLS configuration.
With `options=0`, the OpenSSL padding-bug compatibility branch is disabled;
`s3_flags` matters only in that branch in this wrapper. The sliced function body
does not otherwise use `flags`, `slicing_cheat`, or `mac_size`, but they remain
public inputs in `var_pub` to match the external low-input shape. Use `var_pub`
when the comparison should include those public controls.

Runner configuration: this target uses a benchmark-local runner profile because
its input shape is a secret record buffer plus fixed-width public TLS control
scalars, not the shared modular-exponentiation buffer shape. It has one
`default` preset for the Lucky13 scenario described above.

## Reconciliation Guidance

- Keep Constantine rows small and source-faithful. Their value is historical
  comparison, not clean modern API modeling.
- For BearSSL `aes_big` and `des_tab`, keep the Constantine/BINSEC schedule
  sizes with public CBC data and IV as the default. The fixed-public plaintexts
  come from the shared deterministic crypto defaults. Prefer
  `var_pub` for public-input coverage. Add explicit exact-BINSEC replay targets
  only if results must be compared byte-for-byte with the external wrappers.
- For `tls_rempad_luk13`, report whether the campaign uses `fix_pub` or
  `var_pub`. `var_pub` matches the original BINSEC high/low-input split;
  `fix_pub` intentionally fixes the low inputs to the concrete values listed in
  the table.
- Do not merge `libg:des` with `libgcrypt:aes_encrypt`,
  `libgcrypt:des_encrypt`, or Libgcrypt RSA targets. The former is a
  historical source snapshot; the
  latter use the real Libgcrypt 1.10.1 tree.