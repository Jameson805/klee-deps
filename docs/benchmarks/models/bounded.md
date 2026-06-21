# Bounded Verification Benchmark Models

This page documents bounded verification benchmarks: functions with
constant-time claims that came from the BINSEC/Rel2 and ABACUS benchmark
families. These are mostly safe or intended-constant-time routines, so the
campaign shape is bounded verification over fixed function boundaries and input
sizes rather than unbounded bug-finding over whole programs.

## Bounded Verification Set

| Source benchmark | Repository status | Selector or path |
| --- | --- | --- |
| BearSSL `aes_ct` | Implemented. | `bearssl:aes_des` / target `aes_ct`. |
| BearSSL `des_ct` | Implemented. | `bearssl:aes_des` / target `des_ct`. |
| Libsodium Salsa20 | Implemented descriptor. | `libsodium:salsa20`. |
| Libsodium Chacha20 | Implemented. | `libsodium:chacha20`. |
| Libsodium SHA256 | Implemented. | `libsodium:sha256`. |
| Libsodium SHA512 | Implemented. | `libsodium:sha512`. |
| HACL Chacha20 | Implemented. | `hacl:chacha20`. |
| HACL Curve25519 | Implemented. | `hacl:curve25519`. |
| HACL SHA256 | Implemented. | `hacl:sha256`. |
| HACL SHA512 | Implemented. | `hacl:sha512`. |
| Monocypher Chacha20 | Implemented. | `monocypher:chacha20`. |
| Monocypher Poly1305 | Implemented. | `monocypher:poly1305`. |
| Monocypher Argon2i | Implemented. | `monocypher:argon2i`. |
| Monocypher Ed25519 public-key derivation | Implemented. | `monocypher:ed25519`. |

The BINSEC/Rel2 side contributes Libsodium Salsa20, Chacha20, SHA256, and
SHA512; HACL* Chacha20, Curve25519, SHA256, and SHA512; and BearSSL bounded
AES/DES constant-time backends. The ABACUS side contributes the Monocypher
constant-time-claim routines. Keep repository-only comparable targets, such as
Libsodium Curve25519, outside this bounded verification set.

The external reference wrappers used for this page are in the local Rel2
artifact tree at `/dkucc/home/yl925/rel_bench`. The fixed-size wrappers are:

- `src/bearssl/aes_ct_wrapper.c`
- `src/bearssl/des_ct_wrapper.c`
- `src/libsodium/salsa20_wrapper.c`
- `src/libsodium/chacha20_wrapper.c`
- `src/libsodium/sha256_wrapper.c`
- `src/libsodium/sha512_wrapper.c`
- `src/hacl/chacha20_wrapper.c`
- `src/hacl/curve25519_wrapper.c`
- `src/hacl/sha256_wrapper.c`
- `src/hacl/sha512_wrapper.c`

The size-sweep copies are under
`scalability_vs_input_size/src/{bearssl,libsodium,hacl}`. Those files use the
same wrapper structure but leave `DATA_LEN` or `MESSAGE_LEN` to the experiment
matrix.

## Detailed Input Variables

This table records the inputs that the repository wrappers receive from the
repository runner. The Rel2 comparison source is the actual `HIGH_INPUT` and
`LOW_INPUT` calls in `/dkucc/home/yl925/rel_bench`, not only source comments;
those calls explain the BINSEC/Rel2 comparison notes. The Monocypher comparison
source is the ABACUS artifact in this checkout. The concrete and symbolic
columns below describe repository behavior.

| Selector target | Input variable | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| `bearssl:aes_des` / `aes_ct` | `skey` | Secret | 240 bytes | Valid AES expanded schedule generated from the shared AES-128 key. | `fix_pub` and `var_pub`. | Repository wrapper receives the full schedule-sized buffer. |
| `bearssl:aes_des` / `aes_ct` | `data` | Public | 32 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Repository wrapper models CBC data as public while keeping the fixed Rel2 length. |
| `bearssl:aes_des` / `aes_ct` | `iv` | Public | 16 bytes | All zero. | `var_pub`. | Repository wrapper receives IV as public input. |
| `bearssl:aes_des` / `des_ct` | `skey` | Secret | 384 bytes | Valid 3DES expanded schedule generated from the shared generated 3DES key. | `fix_pub` and `var_pub`. | Repository wrapper receives the full schedule-sized buffer. |
| `bearssl:aes_des` / `des_ct` | `data` | Public | 16 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Repository wrapper models CBC data as public while keeping the fixed Rel2 length. |
| `bearssl:aes_des` / `des_ct` | `iv` | Public | 8 bytes | All zero. | `var_pub`. | Repository wrapper receives IV as public input. |
| `libsodium:salsa20` / `salsa20` | `key` | Secret | 32 bytes | Shared deterministic stream-cipher key. | `fix_pub` and `var_pub`. | Repository wrapper receives a symbolic key after concrete trace seeding. |
| `libsodium:salsa20` / `salsa20` | `message` | Public | 256 bytes | Shared deterministic stream message. | `var_pub`. | Repository convention treats plaintext/message as public input and uses fixed-public mode for the concrete trace. |
| `libsodium:salsa20` / `salsa20` | `nonce` | Public | 8 bytes | All zero. | `var_pub`. | Repository wrapper makes the normally public nonce explicit. |
| `libsodium:chacha20` / `chacha20` | `key` | Secret | 32 bytes | Shared deterministic stream-cipher key. | `fix_pub` and `var_pub`. | Repository wrapper receives a symbolic key after concrete trace seeding. |
| `libsodium:chacha20` / `chacha20` | `message` | Public | 256 bytes | Shared deterministic stream message. | `var_pub`. | Same input convention as Salsa20. |
| `libsodium:chacha20` / `chacha20` | `nonce` | Public | 8 bytes | All zero. | `var_pub`. | Repository wrapper makes the normally public nonce explicit. |
| `libsodium:sha256` / `sha256` | `message` | Secret | 256 bytes | Shared deterministic digest message. | `fix_pub`. | Repository wrapper treats digest storage as local output. |
| `libsodium:sha512` / `sha512` | `message` | Secret | 256 bytes | Shared deterministic digest message. | `fix_pub`. | Same as SHA256 with a 64-byte local digest output. |
| `hacl:chacha20` / `chacha20` | `key` | Secret | 32 bytes | Shared deterministic stream-cipher key. | `fix_pub` and `var_pub`. | Repository wrapper receives a symbolic key after concrete trace seeding. |
| `hacl:chacha20` / `chacha20` | `message` | Public | 256 bytes | Shared deterministic stream message. | `var_pub`. | Same input convention as Salsa20 and Libsodium Chacha20. |
| `hacl:chacha20` / `chacha20` | `nonce` | Public | 12 bytes | All zero. | `var_pub`. | Repository wrapper receives nonce as explicit public input and fixes the counter to zero. |
| `hacl:curve25519` / `curve25519` | `scalar` | Secret | 32 bytes | Standard X25519 scalar seed. | `fix_pub`. | Repository models the private scalar as high. |
| `hacl:curve25519` / `curve25519` | `point` | Public | 32 bytes | Standard X25519 base point. | `var_pub`. | Repository follows the conventional public-point model instead of Rel2's mistaken high marking. |
| `hacl:sha256` / `sha256` | `message` | Secret | 256 bytes | Shared deterministic digest message. | `fix_pub`. | Repository wrapper models the effective high input as the message. |
| `hacl:sha512` / `sha512` | `message` | Secret | 256 bytes | Shared deterministic digest message. | `fix_pub`. | Same as SHA256 with a 64-byte local digest output. |
| `monocypher:chacha20` / `chacha20` | `key` | Secret | 32 bytes | Shared deterministic stream-cipher key. | `fix_pub` and `var_pub`. | Concrete trace seed is valid key material; symbolic runs still make it high. |
| `monocypher:chacha20` / `chacha20` | `nonce` | Public | 8 bytes | All zero. | `var_pub`. | Repository wrapper treats nonce as public and uses the shared zero-nonce convention. |
| `monocypher:chacha20` / `chacha20` | `message` | Public | 128 bytes | Shared deterministic stream message. | `var_pub`. | Fixed-public mode uses nonzero public data. |
| `monocypher:poly1305` / `poly1305` | `key` | Secret | 32 bytes | All zero concrete trace seed. | `fix_pub` and `var_pub`. | Concrete runs seed secret inputs before symbolization. |
| `monocypher:poly1305` / `poly1305` | `message` | Public | 64 bytes | First 64 bytes of the shared fixed random stream message, beginning `c4 37 33 bd`. | `var_pub`. | Public message input for the Poly1305 wrapper, aligned with the shared stream-message defaults. |
| `monocypher:argon2i` / `argon2i` | `password` | Secret | 5 bytes | All zero concrete trace seed. | `fix_pub` and `var_pub`. | Concrete runs seed secret inputs before symbolization. |
| `monocypher:argon2i` / `argon2i` | `salt` | Public | 16 bytes | All zero. | `var_pub`. | Salt is public in the semantic password-hashing model. |
| `monocypher:ed25519` / `ed25519` | `secret_key` | Secret | 32 bytes | All zero concrete trace seed. | `fix_pub` and `var_pub`. | Concrete runs seed secret inputs before symbolization. |

The fixed public values are intentionally simple zeros except for the BearSSL
CBC data blocks. Public nonces and IVs are public protocol controls, so zero is
a stable baseline in fixed-public runs; public-symbolic runs check whether
public variation changes tool behavior. The BearSSL data blocks avoid all-zero
CBC inputs while keeping the original fixed wrapper sizes.

## BearSSL Bounded AES/DES Targets

| Target | Repository model | External BINSEC bounded model | Difference |
| --- | --- | --- | --- |
| `aes_ct` | `br_aes_ct_cbcenc_run`, `N_ROUND=2`, full 240-byte `ctx.skey` secret schedule, 32-byte public data, and 16-byte public IV. | Same function, round count, and full 240-byte high schedule. The fixed wrapper uses `DATA_LEN=32`; the scalability wrapper sweeps 16, 32, 48, 64, 80, and 96. | Repository matches the fixed wrapper's 32-byte data length, but treats data and IV as public inputs for consistency with the Abacus-style AES/DES setup. It does not cover the scaling sweep. |
| `des_ct` | `br_des_ct_cbcenc_run`, `N_ROUND=2`, full 384-byte `ctx.skey` secret schedule, 16-byte public data, and 8-byte public IV. | Same function and round count. The fixed wrapper uses `DATA_LEN=16`; the scalability wrapper sweeps 8, 16, 24, 32, 40, and 48. | Repository matches the fixed wrapper's 16-byte data length, but treats data and IV as public inputs for consistency with the Abacus-style AES/DES setup. It does not cover the scaling sweep. |

The best default is not a full unbounded campaign. These are safe routines, so
bounded verification should keep a fixed round count and fixed buffer sizes;
additional explicit size presets can be added if reproducing the scaling matrix.

Runner configuration: the BearSSL bounded AES/DES targets use benchmark-local
runner profiles because their secret input is expanded schedule storage rather
than a raw cipher key. Each target has one `default` preset with the full
schedule width and target-local generated artifacts. Mod-exp-style `size_N`
presets would mean partial schedule prefixes, not semantic key sizes, so they
are not used for the default comparison model.

## Libsodium Stream And Hash Targets

BINSEC has Libsodium wrappers for Salsa20, Chacha20, SHA256, and SHA512. For
those four benchmarks, the repository model follows the same high buffers and
fixed lengths as the BINSEC input schedule by default. For stream ciphers, the
repository also models the nonce as a public symbolic input so attacker-chosen
nonce behavior is covered explicitly.
When a BINSEC wrapper marks an output buffer high, that buffer is part of the
entry state: it is initialized as a high symbolic buffer before the call even if
the cryptographic routine overwrites it. The repository records that external
fact for comparison, but the active repository wrappers use local destination
storage for stream and hash outputs.

For Salsa20 and Chacha20, the nonce selects the keystream together with the key.
It must not repeat for a fixed key in real protocols, but it is normally public:
attackers often know or choose nonces, and secrecy should not depend on hiding
them. Making the nonce a symbolic public input is useful when the benchmark asks
whether behavior is independent of attacker-controlled nonce values. BINSEC's
fixed wrappers declare the nonce as a stack buffer and do not call `LOW_INPUT` or
`HIGH_INPUT` on it. The repository deliberately makes the nonce a public
symbolic input rather than inheriting uninitialized ordinary stack state. This
adds the public nonce dimension while keeping the key as the stream-cipher
secret and treating the message as public input.

The high output or digest entry buffer means the memory passed as the destination
starts with high symbolic bytes before the call. It is still the output storage
for the cryptographic operation, not an extra logical input to the algorithm. For
Libsodium hashes, the repository intentionally does not copy the external
wrapper's high digest destination behavior; it keeps only the message high and
uses local digest output storage, matching the HACL SHA model below. One possible
reason for the external high-destination choice is wrapper uniformity: all
buffers passed to the function are initialized through the same symbolic-input
mechanism, even when a buffer is expected to be overwritten.
Another is robustness: if the implementation accidentally reads destination
memory before fully writing it, the analysis can observe that dependence instead
of silently relying on concrete or uninitialized bytes. A third possibility is
declassification bookkeeping: the buffer starts as private entry state and later
becomes output. For correct one-shot encrypt and hash APIs, the routine should
overwrite the full output range, so the initial high contents should not affect
the final result.

| Target | Repository model | External BINSEC model | Difference |
| --- | --- | --- | --- |
| `salsa20` | Calls `crypto_stream_salsa20_xor`; 32-byte high key, 256-byte public message, local output buffer, and 8-byte public symbolic nonce. | Calls `crypto_stream_salsa20_xor`; 32-byte high key; 256-byte high message; high output entry buffer; nonce is an ordinary stack buffer with no `HIGH_INPUT` or `LOW_INPUT` call. | Same function, key size, and message length. The repository uses the semantic stream-cipher model: key secret, message and nonce public, output local. |
| `chacha20` | Calls `crypto_stream_chacha20_xor`; 32-byte high key, 256-byte public message, local output buffer, and 8-byte public symbolic nonce. | Calls `crypto_stream_chacha20_xor`; 32-byte high key; 256-byte high message; high output entry buffer; nonce is an ordinary stack buffer with no `HIGH_INPUT` or `LOW_INPUT` call. | Same function, key size, and message length. The repository uses the semantic stream-cipher model: key secret, message and nonce public, output local. |
| `sha256` | Calls `crypto_hash_sha256`; 256-byte high message and local digest output storage. | Calls `crypto_hash_sha256`; 256-byte high message; high digest destination entry buffer. | Same input length. The repository avoids the high digest destination because it is output storage and keeps only the message as a high symbolic input. |
| `sha512` | Calls `crypto_hash_sha512`; 256-byte high message and local digest output storage. | Calls `crypto_hash_sha512`; 256-byte high message; high digest destination entry buffer. | Same as SHA256, with a 64-byte output destination. |

For stream ciphers, the BINSEC input schedule is not the usual key-leakage
threat model because it treats plaintext and output entry buffers as high. The
repository documents that external schedule, but the active wrappers use the
semantic stream-cipher model: the key is secret, the message and nonce are
public, and the destination buffer is local output.
For Libsodium hashes, the external BINSEC schedule is a secret-message model with
a digest output buffer that also starts as high entry state. The repository uses
the consistent hash model instead: the message is high, and the digest is output
storage. This intentionally differs from the external Libsodium wrapper and
matches the HACL SHA wrappers below.

## HACL* Chacha20, Curve25519, And SHA2

The BINSEC paper comparison covers HACL* Chacha20, Curve25519, SHA256, and
SHA512. The external Chacha20 wrapper uses a 32-byte high key, high
plaintext/output, public length `256`, and nonce/counter stack values that are
not passed to `LOW_INPUT` or `HIGH_INPUT`. The repository makes the HACL
Chacha20 message and nonce public symbolic inputs and keeps the counter fixed at
zero. For HACL SHA256 and SHA512, the repository marks only the 256-byte message
as high and uses local digest output storage. HACL* Curve25519 should be modeled
from the matching HACL* wrapper, not from the repository's Libsodium Curve25519
target.

The same nonce and output-buffer rationale applies to HACL* Chacha20. The nonce
and counter determine which Chacha20 block stream is used, and they are normally
public protocol values. They would be good public symbolic inputs for a semantic
attacker-controlled-nonce campaign. The repository therefore treats the nonce as
public symbolic input, while the external wrapper leaves nonce and counter as
ordinary stack values with no `LOW_INPUT` or `HIGH_INPUT` call. The repository
also keeps the output buffer local, rather than preserving the external
high-entry destination state.

For HACL* Curve25519, the cryptographic roles are: `secret` is the private
scalar, `basepoint` is the public input point, and `mypublic` is the output. The
Rel2 wrapper comments say the same thing for `basepoint`, but the actual wrapper
calls `HIGH_INPUT(SIZE)(basepoint)`. The repository uses the semantic
Curve25519 model instead: scalar high, point public, and output local.

Replace the bundled HACL* tree with Cryspen `hacl-packages` tag `c-v0.6.0`.
That tag matches the vendored headers and existing bignum sources, and provides
the generated implementation C files needed for Chacha20, Curve25519, and SHA2.
With those sources present, the repository can run the same HACL* functions
while documenting where its semantic input roles differ from the external
BINSEC wrappers.

| Target | Repository model | External BINSEC model | Difference |
| --- | --- | --- | --- |
| HACL Chacha20 | Calls the matching HACL* Chacha20 wrapper with a 32-byte high key, 256-byte public plaintext, local output buffer, concrete public length `256`, 12-byte public symbolic nonce, and fixed zero counter. | 32-byte high key; 256-byte high plaintext; high output entry buffer; public concrete length `256`; nonce/counter are ordinary stack values with no `LOW_INPUT` or `HIGH_INPUT` call. | Same function, key size, and message length. The repository uses public message and nonce inputs and local output storage. |
| HACL Curve25519 | Calls `Hacl_Curve25519_51_scalarmult` with a 32-byte high X25519 private scalar, a public base point, and local output storage. | Calls `Hacl_Curve25519_crypto_scalarmult`; the wrapper calls `HIGH_INPUT(32)` on output, secret scalar, and basepoint. The source comment labels basepoint public, but the actual input call marks it high. | The repository uses the HACL package's 51-bit Curve25519 entry point and the semantic X25519 input roles. The word scalar means the private X25519 key material, not an arbitrary integer parameter. |
| HACL SHA256 | Calls the matching HACL* SHA256 operation with one 256-byte high message input and a local digest destination. | Calls `Hacl_SHA2_256_hash`; the effective high input set is the message buffer only, and `hash1` is output storage. | The Rel2 wrapper redundantly applies its second `HIGH_INPUT` call to `input` instead of `hash1`. The repository avoids that redundant marking and models the effective input schedule directly. |
| HACL SHA512 | Calls the matching HACL* SHA512 operation with one 256-byte high message input and a local digest destination. | Calls `Hacl_SHA2_512_hash`; the effective high input set is the message buffer only, and `hash1` is output storage. | Same as SHA256: the repository avoids the Rel2 wrapper's redundant second high mark and keeps only the message high. |

## Monocypher Constant-Time-Claim Targets

The ABACUS artifact includes Monocypher Chacha20, Poly1305, Argon2i, and
Ed25519 public-key derivation rows. They are grouped here because they are
bounded function-level checks of routines with constant-time claims. The
repository keeps the ABACUS function boundaries visible while using explicit
secret/public roles for semantic constant-time modeling.

| Target | ABACUS boundary | ABACUS high inputs | ABACUS public or constant inputs | Current repository model | Current difference from ABACUS |
| --- | --- | --- | --- | --- | --- |
| Chacha20 | The property-test driver calls `crypto_chacha20(out_full, plain, 128, key, nonce)`, then calls `crypto_chacha20_ctr` on two 64-byte chunks and compares the outputs. The Pintool is keyed to the driver-visible `crypto_chacha20` call. | 32-byte `key` and 8-byte `nonce` written as `Start` records by the Pintool. | `plain` is a concrete 128-byte driver input buffer, `text_size` is fixed concrete `128`, and `out_full` is a 128-byte output buffer. The plaintext capture code is present but commented out in the Pintool. | Secret input: 32-byte `key`. Public inputs: 8-byte `nonce` and 128-byte `message`. Fixed value: `text_size=128`. Local output: 128-byte `ciphertext`. The wrapper calls `crypto_chacha20` once. | Repository treats nonce as public and includes message as public input. ABACUS records nonce bytes as high inputs for trace replay, but that is not the usual semantic role of a ChaCha20 nonce. |
| Poly1305 | The property-test driver first computes an incremental MAC with `crypto_poly1305_init`, `crypto_poly1305_update`, and `crypto_poly1305_final`, then calls `crypto_poly1305(mac_whole, input, INPUT_SIZE, key)` and compares the two MACs. The Pintool is keyed to the driver-visible `crypto_poly1305` call. | 32-byte `key` and the initial 16 bytes at the `mac` output pointer written as `Start` records by the Pintool. The `key` argument is the Poly1305 secret key. The `mac` pointer is an output destination, so the recorded 16 bytes are pre-call output-buffer contents, not a Poly1305 input. | `input` is a concrete 64-byte driver input buffer, `INPUT_SIZE` is fixed concrete `64`, and `mac_whole` is a 16-byte output buffer. | Secret input: 32-byte one-time Poly1305 `key`. Public input: 64-byte `message`. Fixed value: `message_size=64`. Local output: 16-byte `mac`. The wrapper calls `crypto_poly1305` once. | Repository models the usual Poly1305 use: the one-time key is secret, the authenticated message is public, and the MAC/tag output is local. ABACUS records the output buffer for trace replay, which is not a cryptographic secret input to Poly1305. |
| Argon2i | The driver allocates `work_area`, sets `password = pass`, then calls `crypto_argon2i(hash, 32, work_area, nb_blocks, nb_iterations, password, password_size, salt, 16)`. The Pintool is keyed to the driver-visible `crypto_argon2i` call and also emits markers around selected libc calls while tracing. | The Pintool receives argument 5, `password`, and argument 6, `password_size`, but its callback overwrites the recorded length with 32 before writing the `Start` record. In the concrete ABACUS driver, `password` points to `pass` and `password_size` is 5. | `hash` is a 32-byte output buffer, `hash_size` is fixed concrete `32`, `work_area` is `8 * 1024` bytes, `nb_blocks` is fixed concrete `8`, `nb_iterations` is fixed concrete `1`, `salt` is a 16-byte concrete driver input buffer, and `salt_size` is fixed concrete `16`. | Secret input: 5-byte `password`. Public input: 16-byte `salt`. Fixed values: `hash_size=32`, `nb_blocks=8`, `nb_iterations=1`, and `salt_size=16`. Local outputs/workspace: 32-byte `hash` and `8 * 1024`-byte `work_area`. The wrapper calls `crypto_argon2i` once. | Repository uses an explicit password-secret/salt-public split and solver-friendly cost parameters. It matches the ABACUS driver sizes for password length, salt length, hash length, block count, and iteration count, but does not model the Pintool's hard-coded 32-byte password record. |
| Ed25519 | The driver fills `sk[32]`, then calls `crypto_key_exchange_public_key(pk, sk)`. The Pintool is keyed to this driver-visible key-exchange call. | 32-byte `secret_key` argument 1. In the driver this variable is named `sk`. | `pk` is a 32-byte public-key output buffer. There is no message, signature, or signing nonce in this ABACUS row. The driver fills `sk` with concrete byte values before the call. | Secret input: 32-byte `secret_key`. Local output: 32-byte `public_key`. There are no public message inputs. The wrapper calls `crypto_key_exchange_public_key` once. | Repository now matches the ABACUS key-exchange/public-key derivation function instead of the earlier Ed25519 signing wrapper. |

## Bounded Verification Setup

To mirror bounded-verification use, add explicit descriptor presets rather than
implicit tool options. The bounded preset should fix the buffer lengths at the
source-level sizes, keep loop counts and round counts concrete, and avoid adding
public symbolic dimensions unless they are part of the documented repository
model for that benchmark.

For safe constant-time-claim routines, the campaign shape is:

1. Use the source benchmark input schedule as the default for benchmarks in this
   group, with documented semantic deviations where the source marks outputs or
   public values high.
2. Keep semantic alternatives, such as key-secret and message-public stream
   cipher models, outside the bounded comparison group unless they are the
   documented repository model for that selector.
3. A bounded size matrix for `aes_ct` and `des_ct` only when reproducing the
   external input-size scalability cases; the repository defaults choose the
   32-byte data case for simplicity.

Do not mix semantic alternatives into this group. A mismatch between a
key-leakage threat model and the source input schedule is a benchmark-model
difference, not an implementation bug.