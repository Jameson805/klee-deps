# Constant-Time-Claim Benchmark Models

This page documents the input models for benchmark targets that carry a
constant-time claim under the modeled inputs. The group currently includes
Monocypher, Libsodium, and the BearSSL `aes_ct` target from the broader ABACUS
and BINSEC/Rel2 comparison space. Libgcrypt and OpenSSL ECDSA targets are
planned for this family. HACL Chacha20, SHA256, and SHA512 are possible
additions after the vendored HACL package includes their generated C
implementations. The exact byte values are owned by the runner configs under
`../../../configs/runner/`; this page records what kind of values are used and
which buffers are symbolic.

## Model Summary

| Library | Target | Secret model | Public model | Main question |
| --- | --- | --- | --- | --- |
| Monocypher | `chacha20` | 32-byte key. | 8-byte nonce and 64-byte message. | Does stream encryption depend on secret key bytes beyond expected data flow? |
| Monocypher | `poly1305` | 32-byte key and 64-byte message. | None. | Does authenticator computation branch or access memory based on modeled secret bytes? |
| Monocypher | `argon2i` | 16-byte password. | 16-byte salt. | Does the password-hashing wrapper expose password-dependent behavior under fixed small cost parameters? |
| Monocypher | `ed25519` | 32-byte secret key. | 64-byte message. | Does signing expose secret-key-dependent behavior under public-message variation? |
| Libsodium | `curve25519_scalarmult` | 32-byte scalar. | 32-byte point. | Does scalar multiplication expose secret scalar behavior? |
| BearSSL | `aes_ct` | Expanded schedule prefix and data buffer are symbolic secrets. | No public buffers. | Does the constant-time AES backend branch or access memory based on modeled secret bytes? |
| Libgcrypt | Planned ECDSA signing target. | Private scalar. | Message digest and curve/domain parameters. | Does signing expose secret scalar or nonce behavior under a fixed signing model? |
| OpenSSL | Planned ECDSA signing target. | Private scalar. | Message digest and curve/domain parameters. | Does signing expose secret scalar or nonce behavior under a fixed signing model? |
| HACL Packages C | Possible Chacha20, SHA256, and SHA512 targets. | Chacha20 key; hash message only if the campaign deliberately treats messages as secret. | Chacha20 nonce/counter/message and hash length controls. | Feasible only after generated implementation C files are restored to the vendored HACL tree. |

The repository also has descriptors for additional Libsodium stream and hash
targets, but the current benchmark inventory lists `libsodium:curve25519` as the
implemented selector in the intended comparison set. The extra descriptors use
the same style documented below if they are enabled in a campaign.

BearSSL `aes_ct` is selected through `bearssl:aes_des` because it shares build
and runner plumbing with the historical `aes_big` and `des_tab` rows. It is
classified here because it is the BearSSL AES backend with a constant-time
claim.

The planned ECDSA targets belong here because signing implementations are
usually evaluated against secret private-key and signing-nonce behavior. The
HACL candidates also belong here if they are added as constant-time-claim
benchmarks rather than historical known-violation reproductions.

## Generic Inputs And Defaults

### Monocypher Chacha20

| Input | Meaning | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| `key` | Secret stream-cipher key. | All-zero ABACUS seed. | Whole 32-byte key is symbolic secret. |
| `nonce` | Public nonce. | All-zero fixed public value in `fix_pub`. | Whole 8-byte nonce is symbolic public input in `var_pub`. |
| `message` | Public plaintext/ciphertext buffer for the wrapper. | All-zero fixed public value in `fix_pub`. | Whole 64-byte message is symbolic public input in `var_pub`. |

This is close to a normal stream-cipher use case: the key is secret, while nonce
and message are public or attacker-controlled. The all-zero nonce and message
defaults are simple stable values, not recommended application values.

### Monocypher Poly1305

| Input | Meaning | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| `key` | Secret Poly1305 one-time key. | All-zero ABACUS seed. | Whole 32-byte key is symbolic secret. |
| `message` | Message authenticated by the wrapper. | All-zero ABACUS seed. | Whole 64-byte message is symbolic secret. |

This model treats the message as secret. That is stricter than many MAC use
cases, where the message may be public and only the key is secret. It is useful
for checking whether the routine has data-dependent behavior over any modeled
secret input, but findings should be interpreted with that stronger secrecy
assumption in mind.

### Monocypher Argon2i

| Input | Meaning | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| `password` | Secret password. | All-zero ABACUS seed. | Whole 16-byte password is symbolic secret. |
| `salt` | Public salt. | All-zero fixed public value in `fix_pub`. | Whole 16-byte salt is symbolic public input in `var_pub`. |
| Cost parameters | Hash length, memory blocks, and iterations. | Concrete wrapper macros: 32-byte output, 8 blocks, 1 iteration. | None. |

The model is close to the password-hashing threat split: password secret, salt
public. The cost parameters are intentionally tiny compared with production
Argon2 settings so symbolic tools can execute the wrapper.

### Monocypher Ed25519

| Input | Meaning | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| `secret_key` | Secret signing key seed. | All-zero ABACUS seed. | Whole 32-byte secret key is symbolic secret. |
| `message` | Signed message. | All-zero fixed public value in `fix_pub`. | Whole 64-byte message is symbolic public input in `var_pub`. |

This matches the ordinary signing threat split: secret key protected, message
public. The all-zero secret-key seed is only an ABACUS initialization value; the
symbolic domain covers the full secret key buffer.

### Libsodium Curve25519

| Input | Meaning | Concrete default kind | Symbolic part |
| --- | --- | --- | --- |
| `scalar` | Secret X25519 scalar. | Nonzero test-vector-style 32-byte scalar seed. | Whole scalar is symbolic secret. |
| `point` | Public curve point. | Standard Curve25519 base point shape: first byte `0x09`, remaining bytes zero. | Whole point is symbolic public input in `var_pub`; fixed in `fix_pub`. |

This is close to the ordinary scalar-multiplication threat model: scalar secret,
point public. The fixed public point is a realistic base-point default for
base-point multiplication style tests; `var_pub` broadens the public point
domain.

### BearSSL AES-CT

| Input | Meaning in the wrapper | Active benchmark value |
| --- | --- | --- |
| `skey` | Expanded AES schedule prefix consumed by the reduced-round wrapper. | 48-byte symbolic secret buffer. |
| `data` | CBC input data. | 32-byte symbolic secret buffer. |
| IV | CBC initialization vector. | Concrete all-zero value inside the wrapper; not a runner input. |
| `N_ROUND` | Reduced round count. | Concrete value `2`. |

The concrete `skey` and `data` seeds are large nonzero ABACUS initialization
values. The whole 48-byte effective schedule prefix and 32-byte data buffer are
symbolic secrets. This model preserves the existing schedule-based wrapper, not
a raw AES key schedule API; see `../../../benchmarks/bearssl/README.md` for the
schedule-prefix rationale.

### Planned Libgcrypt And OpenSSL ECDSA

The planned ECDSA benchmarks should start with signing, not verification,
because signing carries the private scalar and nonce-sensitive behavior. Use a
fixed curve and a fixed-size public message digest so findings are about the
secret signing state rather than API shape or variable digest length.

Planned generic inputs:

| Input | Meaning | Planned benchmark value |
| --- | --- | --- |
| `private_key` | ECDSA private scalar for the selected curve. | Symbolic secret scalar initialized from a valid concrete key. |
| `digest` | Message digest passed to the signing routine. | Fixed public value in `fix_pub`; symbolic public buffer in `var_pub` if public-input variation is useful. |
| Curve/domain parameters | Group selection and public curve constants. | Concrete public values, preferably a single widely supported curve. |
| Nonce controls | Per-signature nonce or library nonce callback, if exposed by the wrapper. | Prefer a deterministic, auditable model. If the nonce is secret or symbolic, document whether it is part of the leakage question. |

For Libgcrypt, prefer the smallest wrapper that reaches the real ECDSA signing
implementation while keeping S-expression setup out of the measured core where
possible. For OpenSSL, prefer the C EC/ECDSA path with assembly disabled and a
preinitialized key object. In both libraries, avoid mixing verification,
encoding, and key-generation behavior into the first benchmark unless a later
descriptor intentionally expands the API surface.

### Possible HACL Chacha20 And SHA2

HACL Chacha20, SHA256, and SHA512 are plausible benchmark additions because the
headers in the bundled HACL package expose `Hacl_Chacha20_chacha20_encrypt`,
`Hacl_Hash_SHA2_hash_256`, and `Hacl_Hash_SHA2_hash_512`. They are not
descriptor-ready in this checkout: `benchmarks/hacl-packages-c-v0.6.0/src/`
currently contains only `Hacl_Bignum.c`, `Hacl_Bignum32.c`, and
`Hacl_Bignum64.c`, and `generated/` only contains modular-exponentiation output.

If the generated C implementations are restored, use these initial models:

| Target | Secret model | Public model | Notes |
| --- | --- | --- | --- |
| `chacha20` | 32-byte key. | Nonce, counter, and message buffer public; fixed in `fix_pub`, symbolic public in `var_pub`. | Mirrors the Monocypher Chacha20 threat split. |
| `sha256` | Message is secret only if the campaign intentionally treats hash input as secret. | Otherwise the message is public or fixed. | Hash findings should state the message-secrecy assumption explicitly. |
| `sha512` | Same as SHA256, with SHA512 block and digest sizes. | Same as SHA256. | Keep message length fixed for the first descriptor. |

## Additional Libsodium Descriptor Models

The Libsodium descriptor also contains stream and hash targets that are not the
current inventory selector but follow the same modeling pattern.

| Target | Secret model | Public model | Concrete default kind |
| --- | --- | --- | --- |
| `salsa20` | 32-byte key. | 8-byte nonce and 256-byte message. | Zero key seed; zero fixed public nonce and message in `fix_pub`. |
| `chacha20` | 32-byte key. | 8-byte nonce and 256-byte message. | Zero key seed; zero fixed public nonce and message in `fix_pub`. |
| `sha256` | 256-byte message. | None. | Zero message seed. |
| `sha512` | 256-byte message. | None. | Zero message seed. |

For SHA targets, the message is modeled as secret, which is useful for checking
data-dependent behavior but is not the usual public-message hashing threat
model. For stream targets, the model matches the same key-secret,
nonce/message-public split as Monocypher Chacha20.

## Fidelity And Limits

What these models preserve:

- Library-facing wrappers around real Monocypher, Libsodium, and BearSSL
  routines.
- Planned Libgcrypt/OpenSSL ECDSA signing models with explicit private-scalar
  and public-digest roles.
- Conventional secret/public splits for stream ciphers, password hashing,
  signatures, and Curve25519 scalar multiplication.
- Fixed-public and variable-public modes where a target has public inputs.
- BearSSL `aes_ct` as the AES backend in the BearSSL selector that carries a
  constant-time claim.

What they simplify:

- Many concrete seeds are all zero. They are ABACUS initialization values, not
  recommended application test vectors.
- Argon2i uses very small cost parameters.
- Poly1305 and Libsodium hash targets treat message data as secret, which is a
  stronger model than many deployed use cases.
- BearSSL `aes_ct` models an expanded schedule prefix, not a raw AES key.
- Planned ECDSA wrappers will simplify key setup, curve selection, and nonce
  handling compared with full application signing flows.
- HACL Chacha20/SHA2 requires vendored implementation sources that are not
  present in this checkout.
- The docs describe input domains; they do not claim the wrappers cover every
  API option, key setup path, or protocol integration.

## Validation Checklist

- Confirm each wrapper calls the intended library routine directly.
- Confirm public buffers are listed as public in both descriptor and runner
  config before relying on `var_pub` comparisons.
- Revisit all-zero public defaults if they lead to degenerate output or skipped
  logic.
- For Poly1305 and hash targets, decide whether message secrecy is intentional
  for the campaign or whether a public-message variant should be added.
- For Argon2i, record that the cost parameters are solver-friendly and not
  production-strength settings.
- For BearSSL `aes_ct`, confirm the symbolic schedule length still matches the
  words consumed by `N_ROUND=2`.
- For planned Libgcrypt/OpenSSL ECDSA, validate that key objects are initialized
  from a valid concrete key before symbolization and that signing reaches the
  intended implementation path.
- For HACL Chacha20/SHA2, first restore the generated C implementation files,
  then compile a minimal wrapper before adding descriptors to the inventory.