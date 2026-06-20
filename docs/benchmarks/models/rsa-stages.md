# RSA Stage Benchmark Models

This page documents the RSA decryption-style benchmark model. It complements
`../rsa-overview.md`, which explains the library-agnostic split between
padding-only helpers, RSA private primitives, and full decrypt APIs.

The exact target lists, wrapper sources, symbolic buffer names, and presets are
owned by the benchmark descriptors under `../../../configs/benchmarks/` and the
runner configs under `../../../configs/runner/`. This page records the modeling
rationale: what each target is meant to represent, what is symbolic, what stays
concrete, and which choices still need validation.

## Model Summary

The RSA benchmark family models decryption-side leakage at three layers.

| Layer | What is invoked | Secret input model | Public input model | Main question |
| --- | --- | --- | --- | --- |
| Private primitive | The internal RSA private operation or CRT core. | Selected private exponent material. | Ciphertext representative. | Does private-key arithmetic branch or access memory based on secret exponent bits? |
| Full decrypt API | Public or high-level decrypt entrypoints with a padding mode. | Selected private exponent material. | Ciphertext representative. | Does the library-visible decrypt path expose secret-dependent behavior from private arithmetic or postprocessing? |
| Padding-only helper | PKCS#1 v1.5, OAEP, or SSLv23 decode helper. | Encoded decrypted block. | None in the active model. | Does padding removal branch or access memory based on secret plaintext structure? |

The private-key benchmarks use a concrete 1024-bit base key and overwrite only
the selected exponent bytes before invoking the target. The fixed key gives the
library a realistic modulus, prime factors, public exponent, and recombination
parameters, while keeping symbolic complexity focused on the arithmetic that is
expected to be secret-dependent.

## Generic RSA Inputs

The private and full-decrypt wrappers start from this generic RSA private-key
shape, with library-specific names for some fields.

| Generic field | Usual meaning | Active benchmark value |
| --- | --- | --- |
| `n` | Public modulus, usually `p * q`. | Concrete 1024-bit value from the base key. |
| `e` | Public exponent. | Concrete value from the base key. |
| `d` | Full private exponent. | Concrete base-key value for mbedTLS, OpenSSL, and BearSSL; symbolic suffix for Libgcrypt full-decrypt targets. |
| `p`, `q` | RSA prime factors. | Concrete 512-bit values from the base key. |
| `dp`, `dq` | CRT exponents, normally `d mod (p - 1)` and `d mod (q - 1)`. | Concrete base-key values with symbolic low-order suffix bytes for mbedTLS, OpenSSL, and BearSSL CRT targets. |
| `qInv`, `iqmp`, `iq`, or `u` | CRT recombination coefficient. | Concrete value from the base key. |
| Ciphertext representative | Public RSA input to private or decrypt operation. | Public 128-byte buffer; all-zero concrete default in `fix_pub` and ABACUS modes; symbolic public buffer in `var_pub` mode. |
| Encoded decrypted block | Padding string plus plaintext after the RSA private operation and before unpadding. | Secret 128-byte symbolic buffer for padding-only targets. |

The library naming differs slightly. mbedTLS uses `N`, `E`, `D`, `P`, `Q`,
`DP`, `DQ`, and `QP` internally. OpenSSL stores the CRT exponents as `dmp1` and
`dmq1`, with `iqmp` as the recombination coefficient. BearSSL's private-key
struct uses `p`, `q`, `dp`, `dq`, and `iq`. Libgcrypt's public decrypt wrappers
build an S-expression with `n`, `e`, `d`, `p`, `q`, and `u`; the active
Libgcrypt model symbolizes a suffix of `d` rather than separate CRT exponent
fields.

This gives two different secret models inside the RSA family.

- Private/core/full-decrypt targets protect private key material. The attack
  goal is recovering or distinguishing the private key through secret-dependent
  arithmetic.
- Padding-only targets protect the decoded plaintext-side value. The attack goal
  is recovering plaintext through padding-oracle-style differences, so the
  encoded decrypted block is the symbolic secret even though no RSA private key
  is involved in that wrapper.

## Threat Model

These targets are constant-time benchmarks, not functional RSA test vectors.
They model an attacker who can observe control-flow or memory-access differences
during decryption-style operations.

For private and full-decrypt targets, the protected data is private-key exponent
material. The public data is the ciphertext representative. This matches common
RSA decryption and signing settings where an attacker can choose ciphertexts or
messages but should not learn key-dependent control flow.

For padding-only targets, the protected data is the decrypted encoded block: the
padding string plus plaintext that exists after the private operation and before
padding removal. In a deployed decrypt API this block is produced by the private
operation, but a padding oracle attacker learns plaintext information from
differences in how malformed or partially valid encoded blocks are processed.
Treating the encoded block as symbolic tests whether the unpadding code itself
has data-dependent behavior over that secret plaintext-side intermediate value.

## Why Keep Most Key Fields Concrete

The active model keeps the fields that define the modulus domain concrete:
modulus, prime factors, public exponent, full private exponent where the wrapper
still stores one, and recombination coefficients. This is intentional.

Those fields determine key validity, Montgomery domains, CRT recombination, and
library setup. Making them symbolic changes the benchmark from constant-time RSA
execution into symbolic key construction and validation. Prior mbedTLS
experiments with broader symbolic key models spent most of the search budget in
key reconstruction, validation, or the first large exponentiation before
reaching the behavior the benchmark is meant to compare.

The current model therefore starts from a valid key and overwrites a suffix of
the private exponent material. This keeps the benchmark on the intended code
path. The resulting key object may no longer be mathematically consistent as a
complete RSA key for every symbolic assignment. That tradeoff is accepted for
the private-exponent leakage model, but it should be remembered when interpreting
functional return values.

## Why Symbolize `dp` And `dq`

For mbedTLS, OpenSSL, and BearSSL CRT private-operation targets, the symbolic
inputs are the CRT exponents conventionally named `dp` and `dq` or the library's
equivalent fields.

This choice is narrow on purpose.

- CRT implementations perform one exponentiation modulo `p` and one modulo `q`.
- The exponent bits directly control many classic square-and-multiply or window
  exponentiation decisions.
- Concrete `p`, `q`, modulus, and recombination values avoid symbolic long
  division, symbolic modulus-domain setup, and invalid-key search.
- Keeping the public base/ciphertext concrete in `fix_pub` mode isolates leakage
  from secret exponent variation; `var_pub` mode additionally checks whether the
  same behavior depends on public ciphertext variation.

This is less realistic than importing a fully valid arbitrary RSA key, because
not every symbolic `dp`/`dq` assignment corresponds to a mathematically valid
private key. It is closer to the specific side-channel question: whether the
library's private exponentiation code treats exponent bits as control-flow or
memory-access secrets.

## Concrete Defaults

The table below records the kind of concrete value used for each active input.
It intentionally avoids copying the full byte arrays; those remain in the runner
configs.

| Input class | Concrete default kind | Symbolic part | Rationale and caveats |
| --- | --- | --- | --- |
| Base RSA key fields | One concrete 1024-bit RSA key with concrete `n`, `e`, `d`, `p`, `q`, and recombination coefficient. | None, except fields listed below. | Keeps import, CRT setup, Montgomery domains, and recombination on a realistic key-shaped path. |
| mbedTLS/OpenSSL/BearSSL CRT exponent fields | Start from the base key's concrete `dp`/`dq` values. | Low-order suffix bytes of `dp` and `dq`, with width controlled by `SYM_SIZE`. | Focuses solver effort on exponent-driven private arithmetic while avoiding symbolic key construction. |
| Libgcrypt private exponent field | Starts from the base key's concrete `d` value. | Low-order suffix bytes of `d`, with width controlled by `SYM_SIZE`. | Matches the current public-decrypt wrapper shape, which builds a key S-expression with `d` rather than separate symbolic `dp`/`dq`. |
| Ciphertext for private and full-decrypt targets | Fixed 128-byte RSA representative generated by deterministically padding a fixed random message and encrypting it with the fixed base key. Core private-operation targets may use any nondegenerate generated representative; padding-mode targets use the benchmarked padding scheme where the runner profile can distinguish it. | In `var_pub`, the whole 128-byte ciphertext buffer is symbolic public input. | The ciphertext is a stable public representative, not a promise that full decryption succeeds after `dp`, `dq`, or `d` are symbolized. Most symbolic exponent assignments do not match the key that generated the representative. |
| Padding-only encoded block | Full-width 128-byte encoded block generated by the same deterministic padding step used before RSA encryption for the matching padding scheme. | The whole encoded block is symbolic secret input. | The seed only initializes ABACUS before symbolization. The benchmark question is plaintext recovery through unpadding behavior, so the whole encoded decrypted block is secret. |

The deterministic source for these key and default values is
`tools.utilities.generate_rsa_stage_defaults`. Run it from the repository root,
for example:

```bash
python -m tools.utilities.generate_rsa_stage_defaults --format toml
python -m tools.utilities.generate_rsa_stage_defaults --format c-key
```

The generator fixes its RNG seed by default, creates a 1024-bit RSA key, pads
fixed random messages for PKCS#1 v1.5, OAEP-SHA1, OAEP-SHA256, SSLv23, and raw
representative cases, then encrypts each encoded block with the generated base
key. Padding-only ABACUS defaults should use the encoded block from the same
scheme-specific generation step rather than an unrelated hand-written seed.

The mbedTLS, OpenSSL, and BearSSL private-operation wrappers reduce or normalize
ciphertexts into the RSA modulus domain before invoking the library. Libgcrypt's
public decrypt wrapper passes the fixed-width ciphertext MPI through the public
API shape directly.

For private-operation benchmarks, the generated ciphertext default is mainly a
stable nondegenerate public representative. The security question is driven by
the symbolic private exponent suffixes, not by semantic validity of the
ciphertext as a padded RSA encryption.

For full decrypt targets, the generated ciphertext decrypts to a valid padded
block only for the concrete base key used to generate it. Once `dp`, `dq`, or
`d` are symbolized, most exponent assignments will not match that key and may
not produce valid padding. The wrappers usually treat expected padding or
verification failures as part of the modeled path so the benchmark still
observes the decrypt pipeline. This should be documented in result
interpretation: a full-decrypt target here means the full library entry path is
invoked, not that every symbolic assignment represents a successful real
application decrypt.

For padding-only targets, there is no public ciphertext input in the active
model. The wrapper starts at the unpadding boundary, so the input is the encoded
decrypted block. That block is modeled as secret because the realistic attack is
plaintext recovery from padding behavior.

## Library Mapping

### mbedTLS 3.2.1

Implemented targets:

| Target | Layer | Function shape | Symbolic model |
| --- | --- | --- | --- |
| `rsa_private` | Private primitive | Calls `mbedtls_rsa_private`. | Symbolic suffixes of `DP` and `DQ`; concrete base key; public ciphertext. |
| `rsa_rsaes_pkcs1_v15_decrypt` | Full decrypt API | Calls `mbedtls_rsa_rsaes_pkcs1_v15_decrypt`. | Same key model as `rsa_private`; public ciphertext; PKCS#1 v1.5 padding errors are accepted as modeled outcomes. |
| `rsa_rsaes_oaep_decrypt` | Full decrypt API | Calls the OAEP decrypt wrapper. | Same key model as `rsa_private`; public ciphertext. |
| `pkcs1_v15_unpadding` | Padding-only helper | Tests PKCS#1 v1.5 unpadding directly. | Full encoded block is symbolic secret; no public input. |

The mbedTLS wrappers import a valid base key, complete the key, overwrite `DP`
and `DQ`, and force the blinding values to one. This disables blinding without
removing the library's normal private-operation call. Ciphertexts are reduced
modulo the concrete modulus before use.

The active model intentionally does not call full private-key consistency checks
after overwriting the CRT exponents. Calling those checks would make the
benchmark mostly about key validity constraints rather than private arithmetic.

### OpenSSL 1.1.1q

Implemented targets:

| Target | Layer | Function shape | Symbolic model |
| --- | --- | --- | --- |
| `rsa_private_core` | Private primitive | Calls the RSA method's `rsa_mod_exp` directly. | Symbolic suffixes of `dmp1` and `dmq1`; concrete base key; public ciphertext. |
| `padding_check_pkcs1_type_2` | Padding-only helper | Calls the PKCS#1 type 2 padding check wrapper. | Full encoded block is symbolic secret. |
| `padding_check_oaep_mgf1` | Padding-only helper | Calls the OAEP MGF1 padding check wrapper. | Full encoded block is symbolic secret. |
| `padding_check_sslv23` | Padding-only helper | Calls the SSLv23 padding check wrapper. | Full encoded block is symbolic secret. |
| `pkey_rsa_pkcs1_decrypt` | Full decrypt API | Uses `EVP_PKEY_decrypt` with PKCS#1 padding. | Same CRT exponent model as `rsa_private_core`; public ciphertext. |
| `pkey_rsa_oaep_decrypt` | Full decrypt API | Uses `EVP_PKEY_decrypt` with OAEP and SHA-256 settings. | Same CRT exponent model as `rsa_private_core`; public ciphertext. |
| `pkey_rsa_sslv23_decrypt` | Full decrypt API | Uses `EVP_PKEY_decrypt` with SSLv23 padding. | Same CRT exponent model as `rsa_private_core`; public ciphertext. |
| `pkey_rsa_no_padding_decrypt` | Full decrypt API | Uses `EVP_PKEY_decrypt` with no padding. | Same CRT exponent model as `rsa_private_core`; public ciphertext. |

The OpenSSL wrappers load a concrete RSA object, overwrite the CRT exponent
suffixes, and explicitly turn blinding off. The private-core target bypasses the
EVP layer to isolate `rsa_mod_exp`; the full-decrypt targets go through EVP so
the benchmark includes public API dispatch and padding-mode handling.

This split is important because OpenSSL exposes both low-level RSA operations
and higher-level EVP APIs. A finding in the private core is about arithmetic; a
finding in an EVP-facing target may include arithmetic, padding, and API-layer
control flow.

### BearSSL 0.6

Implemented targets:

| Target | Layer | Function shape | Symbolic model |
| --- | --- | --- | --- |
| `rsa_i31_private` | Private primitive | Calls `br_rsa_i31_private`. | Symbolic suffixes of `dp` and `dq`; concrete base key; public ciphertext. |
| `rsa_i31_oaep_decrypt` | Full decrypt API | Calls BearSSL i31 OAEP decrypt. | Same CRT exponent model as `rsa_i31_private`; public ciphertext. |
| `rsa_ssl_decrypt` | Full decrypt API | Calls BearSSL TLS/SSL-style RSA decrypt. | Same CRT exponent model as `rsa_i31_private`; public ciphertext. |
| `rsa_oaep_unpad` | Padding-only helper | Calls BearSSL OAEP unpadding. | Full encoded block is symbolic secret. |

BearSSL is modeled in the same CRT-exponent style as mbedTLS and OpenSSL. This
keeps the cross-library private-operation comparison aligned: concrete modulus
domain, symbolic private exponent suffixes, and public ciphertext.

### Libgcrypt 1.10.1

Implemented targets:

| Target | Layer | Function shape | Symbolic model |
| --- | --- | --- | --- |
| `gcry_pk_decrypt_pkcs1` | Full decrypt API | Calls `gcry_pk_decrypt` with PKCS#1 flags and no blinding. | Symbolic suffix of private exponent `d`; concrete `n`, `e`, `p`, `q`, and `u`; public ciphertext. |
| `gcry_pk_decrypt_oaep` | Full decrypt API | Calls `gcry_pk_decrypt` with OAEP flags and no blinding. | Same private exponent model as PKCS#1. |
| `gcry_pk_decrypt_raw` | Full decrypt API | Calls `gcry_pk_decrypt` with raw RSA flags and no blinding. | Same private exponent model as PKCS#1. |
| `rsa_pkcs1_decode_for_enc` | Padding-only helper | Calls Libgcrypt's internal PKCS#1 decode helper. | Full encoded block is symbolic secret. |
| `rsa_oaep_decode` | Padding-only helper | Calls Libgcrypt's internal OAEP decode helper. | Full encoded block is symbolic secret. |

Libgcrypt's active full-decrypt wrappers symbolize a suffix of the full private
exponent `d` rather than separate `dp` and `dq` buffers. The concrete key still
contains the modulus, public exponent, prime factors, and recombination value.
The decrypt data explicitly requests `no-blinding`, keeping the benchmark
comparable with the other RSA-stage targets.

This is close to the public API use case because the target is `gcry_pk_decrypt`
with scheme flags. It is less isolated than a direct `secret_core_crt` benchmark,
so findings should be interpreted as public decrypt-path behavior rather than a
pure CRT-core measurement.

## Fidelity And Limits

The model is intentionally close to the side-channel question and less close to
full application semantics.

What it preserves:

- Real library RSA code paths for private arithmetic, full decrypt APIs, and
  padding helpers.
- A valid concrete modulus domain and concrete base key material.
- Attacker-controlled ciphertext as public input where the benchmark has a
  ciphertext.
- Full-width encoded blocks for padding-only tests.

What it simplifies:

- Blinding is disabled or neutralized.
- Only selected exponent suffixes are symbolic for most private-operation
  targets.
- Some symbolic key assignments do not represent mathematically valid RSA keys.
- Full-decrypt targets may observe error paths for invalid padding or failed
  verification.
- Padding-only targets skip the preceding RSA private operation.

These simplifications are acceptable when the goal is to compare constant-time
behavior under a controlled symbolic model. They are not enough, by themselves,
to claim that a complete deployed RSA stack is safe or unsafe under all valid
keys and ciphertexts.

## Validation Checklist

Use this checklist when reviewing or changing an RSA benchmark target.

- Confirm the wrapper reaches the intended function rather than stopping in key
  setup, import, or validation.
- Confirm the symbolic secret buffers are actually consumed by the target call.
- Confirm public ciphertext is reduced, normalized, or intentionally passed
  through the library's own public input handling.
- Confirm blinding is disabled, neutralized, or explicitly considered part of
  the target.
- For full decrypt APIs, record whether padding and verification failures are
  accepted as modeled outcomes.
- For padding-only targets, record whether the ABACUS seed is structurally valid
  for the padding scheme or merely a deterministic initialization value.
- Revisit the concrete ciphertext default if a target spends most execution in a
  trivial or immediate-failure path.
- When adding a broader symbolic key model, validate that solver time is not
  dominated by key reconstruction or long-division/modulus-domain setup.