# ABACUS Benchmark Models

This page documents direct ABACUS benchmark targets and how the repository
models differ from ABACUS. ABACUS instruments concrete binaries with Pin and
writes selected runtime memory regions as high-input `Start` records in the
trace. The repository uses generated symbolic wrappers with explicit secret and
public buffers. Those are comparable only when the function boundary, library
version, and high/public input split line up.

## Source-Set Ambiguities

- The ABACUS artifact text in this checkout lists OpenSSL AES/DES/RSA/ECDSA,
  mbedTLS AES/DES/RSA/ECDSA, Libgcrypt RSA, and Monocypher
  Chacha20/Poly1305/Argon2i/Ed25519. The Monocypher rows are now classified as
  bounded verification benchmarks because they are function-level checks of
  routines with constant-time claims. Libgcrypt AES/DES/ECDSA are repository
  targets, but they are not ABACUS benchmark rows in this artifact.
- Mbed TLS AES/DES/ECDSA are now implemented as repository descriptors, but
  they use mbedTLS 3.2.1 and focused wrappers rather than the ABACUS 2.5/2.15
  concrete drivers.
- ABACUS often targets older library versions: mbedTLS 2.5/2.15, Libgcrypt
  1.8.5, and several OpenSSL versions. This repository currently uses mbedTLS
  3.2.1, Libgcrypt 1.10.1, and OpenSSL 1.1.1q.

## Implemented Target Summary

| Selector target | Prior ABACUS operation | Repository implementation |
| --- | --- | --- |
| `openssl:aes_encrypt` | Key setup plus one OpenSSL AES block encrypt; ABACUS records the 16-byte key. | OpenSSL 1.1.1q CBC wrapper with secret key and public plaintext/IV. |
| `openssl:des_encrypt` | Key setup plus one OpenSSL DES ECB block; ABACUS records the 8-byte key. | OpenSSL 1.1.1q CBC wrapper with secret key and public plaintext/IV. |
| `mbedtls:aes_encrypt` | `mbedtls_aes_setkey_enc` plus one CBC block; ABACUS records the 16-byte key. | mbedTLS 3.2.1 CBC wrapper with the same sizes; plaintext and IV are public inputs. |
| `mbedtls:des_encrypt` | `mbedtls_des_setkey_enc` plus one ECB block; ABACUS records the 8-byte key. | mbedTLS 3.2.1 ECB wrapper with the same key and plaintext sizes. |
| `openssl:rsa_private_decrypt_oaep` | `RSA_private_decrypt` with `RSA_PKCS1_OAEP_PADDING`; ABACUS records full CRT fields `p`, `q`, `dmp1`, `dmq1`, and `iqmp`. | OpenSSL 1.1.1q wrapper symbolizes 64-byte `dp` and `dq` only, plus public ciphertext. |
| `mbedtls:rsa_rsaes_pkcs1_v15_decrypt` | `mbedtls_rsa_pkcs1_decrypt`; ABACUS records `P`, `Q`, `DP`, `DQ`, and `QP`. | mbedTLS 3.2.1 wrapper symbolizes 64-byte `dp` and `dq` only, plus public ciphertext. |
| `libgcrypt:gcry_pk_decrypt_raw` | `gcry_pk_decrypt` after raw-data `gcry_pk_encrypt`, with trace capture at internal RSA/CRT routines; ABACUS records full private exponent and CRT fields. | Libgcrypt 1.10.1 public API wrapper symbolizes the 128-byte private exponent `d` and keeps other key fields concrete. |
| `openssl:ecdsa_sign` | OpenSSL ECDSA signing with private scalar and nonce-derived `kinv` recorded high. | OpenSSL 1.1.1q wrapper uses 24-byte private key and nonce inputs, public 20-byte digest, and local signature output. |
| `mbedtls:ecdsa_sign` | mbedTLS ECDSA signing with private scalar and internally sampled nonce recorded high. | mbedTLS 3.2.1 wrapper uses 24-byte private key and nonce inputs, public 32-byte digest, and local signature output. |
## Detailed Input Variables

The concrete values below are the values emitted by the repository runner into
the repository wrapper. The symbolic column says when the wrapper receives a
symbolic buffer instead of that concrete value. For generated RSA key material
and deterministic ECDSA nonce material, the table describes the value class
instead of copying long fixed numbers.

| Selector target | Input variable | Kind | Size | Concrete value | Symbolic when | Justification |
| --- | --- | --- | --- | --- | --- | --- |
| `openssl:aes_encrypt` | `key` | Secret | 16 bytes | Shared AES-128 key `00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee ff`. | `fix_pub` and `var_pub`. | Same concrete AES key seed as the other repository AES encryption wrappers. |
| `openssl:aes_encrypt` | `data` | Public | 16 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Fixed-public mode uses the shared nonzero plaintext; public-symbolic mode still symbolizes it. |
| `openssl:aes_encrypt` | `iv` | Public | 16 bytes | All zero. | `var_pub`. | Repository CBC wrapper receives IV directly and uses the shared zero-IV convention. |
| `openssl:des_encrypt` | `key` | Secret | 8 bytes | Shared generated DES key `40 37 d6 52 df fb d0 0e`. | `fix_pub` and `var_pub`. | Same repository-generated DES key seed as the other DES wrappers. |
| `openssl:des_encrypt` | `data` | Public | 8 bytes | First 8 bytes of the shared deterministic plaintext. | `var_pub`. | Keeps fixed-public DES data aligned with the AES plaintext source. |
| `openssl:des_encrypt` | `iv` | Public | 8 bytes | All zero. | `var_pub`. | Repository CBC wrapper receives IV directly and uses the shared zero-IV convention. |
| `mbedtls:aes_encrypt` | `key` | Secret | 16 bytes | Shared AES-128 key `00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee ff`. | `fix_pub` and `var_pub`. | Same concrete AES key seed as OpenSSL AES. |
| `mbedtls:aes_encrypt` | `data` | Public | 16 bytes | Shared deterministic plaintext beginning `4b 21 30 a3`. | `var_pub`. | Fixed-public mode uses the shared nonzero plaintext. |
| `mbedtls:aes_encrypt` | `iv` | Public | 16 bytes | All zero. | `var_pub`. | Repository CBC wrapper receives this IV directly through `iv_buf`. |
| `mbedtls:des_encrypt` | `key` | Secret | 8 bytes | Shared generated DES key `40 37 d6 52 df fb d0 0e`. | `fix_pub` and `var_pub`. | Same repository-generated DES key seed as OpenSSL DES. |
| `mbedtls:des_encrypt` | `data` | Public | 8 bytes | First 8 bytes of the shared deterministic plaintext. | `var_pub`. | Keeps fixed-public DES data aligned with the AES plaintext source. |
| `openssl:rsa_private_decrypt_oaep` and `mbedtls:rsa_rsaes_pkcs1_v15_decrypt` | `dp`, `dq` | Secret | 64 bytes each | Valid CRT exponent fields from a concrete 1024-bit key. | `fix_pub` and `var_pub`. | Tractable subset of ABACUS full CRT state that keeps private exponentiation in scope. |
| `openssl:rsa_private_decrypt_oaep` and `mbedtls:rsa_rsaes_pkcs1_v15_decrypt` | `ciphertext` | Public | 128 bytes | Generated ciphertext for the shared concrete 1024-bit RSA key. | `var_pub`. | Keeps fixed-public decrypt runs in the valid RSA domain. |
| `libgcrypt:gcry_pk_decrypt_raw` | `d` | Secret | 128 bytes | Valid private exponent from a concrete 1024-bit key. | `fix_pub` and `var_pub`. | Follows ABACUS's full-`D` high-input size while keeping `p`, `q`, and `u` concrete. |
| `libgcrypt:gcry_pk_decrypt_raw` | `ciphertext` | Public | 128 bytes | Generated ciphertext for the shared concrete 1024-bit RSA key. | `var_pub`. | Keeps fixed-public decrypt runs in the valid RSA domain. |
| `openssl:ecdsa_sign` | `private_key` | Secret | 24 bytes | Fixed valid P-192 scalar `1`, encoded as 23 zero bytes followed by `0x01`. | `fix_pub` and `var_pub`. | Matches ABACUS's 192-bit curve size while giving the concrete trace a valid long-term scalar seed. |
| `openssl:ecdsa_sign` | `nonce` | Secret | 24 bytes | Deterministic random valid P-192 scalar beginning `a2 a8 59 0c`. | `fix_pub` and `var_pub`. | Models ABACUS's nonce-derived `kinv` as high per-signature material with a nontrivial concrete seed. |
| `openssl:ecdsa_sign` | `digest` | Public | 20 bytes | Deterministic fixed digest beginning `af e3 8f 7b`. | `var_pub`. | SHA-1 digest size used by the ABACUS OpenSSL ECDSA row. |
| `mbedtls:ecdsa_sign` | `private_key` | Secret | 24 bytes | Fixed valid P-192 scalar `1`, encoded as 23 zero bytes followed by `0x01`. | `fix_pub` and `var_pub`. | Matches ABACUS's 192-bit curve size while giving the concrete trace a valid long-term scalar seed. |
| `mbedtls:ecdsa_sign` | `nonce` | Secret | 24 bytes | Deterministic random valid P-192 scalar beginning `a2 a8 59 0c`. | `fix_pub` and `var_pub`. | Models the signing nonce as high per-signature material with a nontrivial concrete seed. |
| `mbedtls:ecdsa_sign` | `digest` | Public | 32 bytes | Deterministic fixed digest beginning `af e3 8f 7b`. | `var_pub`. | SHA-256 digest size used by the ABACUS mbedTLS ECDSA row. |

Concrete fixed values should keep the repository wrapper on the intended code
path without accidentally testing only a degenerate all-zero public case. The
AES encryption defaults now use the shared AES key, shared deterministic
plaintext, and zero IV. The current repository has encrypt wrappers for the symmetric
rows; if decrypt wrappers are added, their fixed ciphertext should be generated
from the same key, plaintext, and IV used by the matching encrypt wrapper.
Padding-only RSA helpers, alternate RSA modes, repository-only Libgcrypt
AES/DES/ECDSA targets, and Monocypher bounded-verification targets are not
listed in this input table because they are not in the current ABACUS benchmark
group.

## AES And DES

The ABACUS AES and DES Pintools start tracing when the key setup routine is
entered, copy the key bytes into the trace header as the high input, and then
leave tracing enabled after the setup routine returns. The benchmark therefore
records key setup plus the later encryption routine in the concrete driver. The
plain input buffers, IVs, lengths, and modes are concrete driver values; ABACUS
does not model them as low symbolic variables.

| Library | ABACUS core operation | ABACUS high inputs | ABACUS public or constant inputs | Current repository model | Current difference from ABACUS |
| --- | --- | --- | --- | --- | --- |
| OpenSSL AES | `AES_set_encrypt_key` followed by one `AES_encrypt` block. The driver filename says CBC, but the code calls the single-block API. | Key: 16 bytes copied from the `AES_set_encrypt_key` key pointer. | `keybits`: fixed concrete `128`. Plaintext: fixed concrete stack string `"hello world!"`. Output buffer: ciphertext destination, not an input. Expanded-key object: mutable key-schedule destination derived from the key, not an input. | `openssl:aes_encrypt` uses a 16-byte secret key, 16-byte public plaintext, and 16-byte public IV. `keybits` is fixed at `128`; length and encrypt mode are fixed by the wrapper. | The repository uses CBC encryption with a public IV instead of ABACUS's single-block `AES_encrypt`. It also supports symbolic public plaintext/IV for KLEE/BINSEC, while exact ABACUS execution used concrete plaintext and no IV. |
| OpenSSL DES | `DES_set_key` followed by one `DES_ecb_encrypt` block. | Key: 8 bytes copied from the `DES_set_key` key pointer. | Key generation before `DES_set_key`: concrete driver setup. Plaintext: fixed concrete `const_DES_cblock` string `"hehehe"`. Encrypt/decrypt selector: fixed concrete `DES_ENCRYPT`. Output buffer: ciphertext destination, not an input. Key schedule: mutable schedule derived from the key, not an input. | `openssl:des_encrypt` uses an 8-byte secret key, 8-byte public plaintext, and 8-byte public IV. Encrypt mode and length are fixed by the wrapper. | The repository uses CBC encryption with a public IV instead of ABACUS's `DES_ecb_encrypt`. It also supports symbolic public plaintext/IV for KLEE/BINSEC, while exact ABACUS execution used concrete plaintext and no IV. |
| mbedTLS AES | `mbedtls_aes_setkey_enc` followed by one `mbedtls_aes_crypt_cbc` call over 16 bytes. | Key: 16 bytes copied from argument 1 of `mbedtls_aes_setkey_enc`. | `keybits`: fixed concrete `128`. Plaintext: fixed concrete 16-byte buffer filled with `0x07`. IV: fixed concrete 16-byte buffer filled with `0x01`. Length: fixed concrete `16`. Mode: fixed concrete `MBEDTLS_AES_ENCRYPT`. Context: mutable AES key-schedule/state object derived from the key, not an input. Ciphertext: output destination, not an input. | `mbedtls:aes_encrypt` uses a 16-byte key, 16-byte plaintext, 16-byte IV, fixed `keybits=128`, fixed length `16`, and fixed encrypt mode. The key is secret; plaintext and IV are public. Fixed-public repository runs use the repository AES default key, plaintext block, and IV listed above. | The repository matches ABACUS's sizes and CBC operation, but not ABACUS's concrete plaintext and IV fill bytes. Public-symbolic runs may make plaintext and IV symbolic public inputs. |
| mbedTLS DES | `mbedtls_des_setkey_enc` followed by one `mbedtls_des_crypt_ecb` block. | Key: 8 bytes copied from argument 1 of `mbedtls_des_setkey_enc`. | Plaintext: fixed concrete 8-byte buffer filled with `0x07`. Context: mutable DES key-schedule/state object derived from the key, not an input. Ciphertext: output destination, not an input. | `mbedtls:des_encrypt` uses the same 8-byte key and 8-byte plaintext with `mbedtls_des_crypt_ecb`. The key is secret; plaintext is public. There is no IV field because the ABACUS driver and repository wrapper use ECB. | The repository now matches ABACUS's size and ECB operation, but KLEE/BINSEC `var_pub` runs may make plaintext symbolic public. ABACUS used a concrete plaintext value. |

The best reconciliation is to separate exact ABACUS replay from semantic
constant-time models. Exact replay should match the high inputs copied by the
Pintool and the concrete driver values. KLEE-based tools and BINSEC can also
represent low symbolic inputs, so encryption-path defaults should usually make
plaintext and IVs symbolic public inputs rather than symbolic secrets when the
repository wrapper uses an IV-bearing mode.
Lengths, modes, key sizes, API selectors, contexts, and output buffers should
stay concrete or local unless a
specific benchmark is meant to test those dimensions.

## RSA

ABACUS RSA records full CRT key material from concrete library contexts. The
repository uses smaller symbolic exponent models to keep symbolic execution on
the intended private arithmetic path.

| Library | ABACUS boundary | ABACUS high inputs | ABACUS public or constant inputs | Current repository model | Current difference from ABACUS |
| --- | --- | --- | --- | --- | --- |
| mbedTLS | `mbedtls_rsa_pkcs1_decrypt` on a concrete 1024-bit RSA context. | 64-byte `P`, 64-byte `Q`, 64-byte `DP`, 64-byte `DQ`, and 64-byte `QP` read from the RSA context. | Ciphertext, output buffer, padding mode, RNG arguments, key size, and the remaining context fields are concrete driver values. | `mbedtls:rsa_rsaes_pkcs1_v15_decrypt` uses a concrete valid key and symbolizes only full-size 64-byte `DP` and 64-byte `DQ`; public ciphertext is 128 bytes. | Repository keeps ABACUS-sized CRT exponent fields but does not symbolize `P`, `Q`, or `QP`, because broad symbolic key setup is not solver-tractable. It also uses newer mbedTLS and explicit public ciphertext. |
| OpenSSL | `RSA_private_decrypt` with `RSA_PKCS1_OAEP_PADDING` on a concrete `RSA` object. | 64-byte `p`, 64-byte `q`, 64-byte `dmp1`, 64-byte `dmq1`, and 64-byte `iqmp` read from `RSA`. | Ciphertext, output buffer, padding selector, key size, and the remaining `RSA` fields are concrete driver values. | `openssl:rsa_private_decrypt_oaep` uses a concrete valid key and symbolizes only full-size 64-byte `dmp1` and 64-byte `dmq1`; public ciphertext is 128 bytes. | Repository invokes the low-level `RSA_private_decrypt` interface and keeps ABACUS-sized CRT exponent fields, but does not symbolize `p`, `q`, or `iqmp` for solver tractability. |
| Libgcrypt | The driver builds raw input data, calls `gcry_pk_encrypt`, and then calls `gcry_pk_decrypt`; the Pintool enables tracing at internal `rsa_decrypt` and starts instruction capture at the nested `secret_core_crt` call. | 128-byte `D`, 64-byte `P`, 64-byte `Q`, and 64-byte `U`. Libgcrypt does not store `DP`/`DQ` key fields on this path; `secret_core_crt` receives full `D` and computes `D mod (P-1)` and `D mod (Q-1)` internally before the two CRT exponentiations. | Public-key encryption input, decrypted ciphertext, S-expression structure, raw-data mode, and the remaining key/context fields are concrete driver values. | `libgcrypt:gcry_pk_decrypt_raw` uses a concrete valid key and symbolizes the full 128-byte private exponent `d`; public ciphertext is 128 bytes. | Repository uses newer Libgcrypt and a public API wrapper, with full-size `d` symbolic but concrete `p`, `q`, and `u`. That follows ABACUS's full-`D` size while avoiding full CRT key symbolic setup. |

For RSA, the recommended default remains the repository's concrete valid base
key plus ABACUS-sized symbolic exponent fields: 64-byte `DP`/`DQ` for
`mbedtls:rsa_rsaes_pkcs1_v15_decrypt`, 64-byte `dmp1`/`dmq1` for
`openssl:rsa_private_decrypt_oaep`, and 128-byte `d` for
`libgcrypt:gcry_pk_decrypt_raw`. That model is not identical to ABACUS, but it
is more tractable and keeps the benchmark focused on private exponentiation and
padding behavior. Use compatibility variants only for direct cross-tool
reproduction; for Libgcrypt, that would be one compatibility benchmark matching
the ABACUS entry-gated `secret_core_crt` trace, not separate benchmarks for
`rsa_decrypt` and `secret_core_crt`.

## ECDSA

ECDSA signing authenticates a public message digest with a long-term private
scalar and a fresh per-signature nonce. In the normal library API, the nonce is
not a separate public argument: it is sampled through the RNG path during
signing or signing setup. The private scalar must be secret across all
signatures. The nonce, or OpenSSL's precomputed nonce inverse `kinv`, must also
be secret for the signature being produced because nonce disclosure can recover
the private scalar. The message, digest, digest length, curve choice, public
key, and signature/output buffers are public or fixed inputs for the usual
signing use case. They may be symbolic public values in KLEE/BINSEC runs, but
they should not be modeled as secrets unless the experiment is deliberately
testing a nonstandard hidden-message scenario.

| Library | ABACUS boundary | ABACUS high inputs | ABACUS public or constant inputs | Current repository model | Current difference from ABACUS |
| --- | --- | --- | --- | --- | --- |
| OpenSSL | Intended operation: ECDSA signing of a SHA-1 digest. The driver first calls `ECDSA_sign_setup(key, NULL, &kinv, &rp)` to precompute nonce values, then calls `ECDSA_do_sign_ex(digest, 20, kinv, rp, key)` to sign. The nonce is sampled inside `ECDSA_sign_setup` through OpenSSL's `RAND_METHOD`; ABACUS's driver installs a fake RAND method so this path is deterministic. The Pintool starts capture at the driver-visible `ECDSA_sign_setup` call and adds a second high-input record at the later driver-visible `ECDSA_do_sign_ex` call. | Secret inputs: `EC_KEY->priv_key` limbs from argument 0 of `ECDSA_sign_setup`, and `kinv` limbs from argument 2 of `ECDSA_do_sign_ex`. `kinv` is the precomputed inverse of the per-signature nonce, so it is nonce-derived secret material recorded after nonce generation. | Public or fixed inputs: digest pointer, digest length `20`, `rp`, signature output, curve parameters, public key, and non-private `EC_KEY` fields. `rp` is the public nonce point x-coordinate/signature `r` value, not a secret. | Secret inputs: 24-byte private scalar and 24-byte nonce bytes. Public input: 20-byte digest. Fixed values/local state: `prime192v1` key setup, public key derived from the private scalar, generated `kinv`/`rp`, and signature output. The wrapper feeds raw nonce bytes to a dummy `RAND_METHOD`, calls `ECDSA_sign_setup`, then calls `ECDSA_do_sign_ex`. | Repository uses OpenSSL 1.1.1q and a focused wrapper instead of the ABACUS concrete application, but now matches ABACUS's 192-bit curve size and secret private-key/nonce split. The concrete ABACUS seeds are valid P-192 scalars; symbolic runs still do not constrain raw secret inputs before the library sees them. |
| mbedTLS | Intended operation: ECDSA signing of a SHA-256 digest. The driver hashes the message, then calls `mbedtls_ecdsa_write_signature(&ctx_sign, MBEDTLS_MD_SHA256, hash, sizeof(hash), sig, &sig_len, mbedtls_ctr_drbg_random, &ctr_drbg)`. The nonce is sampled inside the signing path from the CTR-DRBG callback. The Pintool starts capture at this driver-visible call. For the nonce record, the 2.15 Pintool watches the internal `mbedtls_ecp_mul_restartable` call under `ecdsa_sign_restartable`; the 2.5 Pintool watches internal `mbedtls_mpi_mul_mpi` under `mbedtls_ecdsa_sign`. | Secret inputs: private scalar `ctx->d` from argument 0 of `mbedtls_ecdsa_write_signature`, and nonce scalar `k` from argument 2 of the watched internal nonce-multiplication call. `k` is the per-signature ECDSA nonce recorded after the RNG path produced it. | Public or fixed inputs: hash buffer, hash length, signature output buffer, signature length output, RNG callback, RNG context, curve/group data, public point `Q`, and non-private key fields. The RNG state can contain secret entropy in a real system, but this benchmark's semantic signing secrets are `d` and the resulting nonce scalar `k`. | Secret inputs: 24-byte private scalar and 24-byte nonce bytes. Public input: 32-byte digest. Fixed values/local state: `MBEDTLS_ECP_DP_SECP192R1`, signature scalars, and dummy RNG callback fed by the raw secret nonce buffer. The wrapper calls `mbedtls_ecdsa_sign` once. | Repository uses mbedTLS 3.2.1 and the lower-level signing API so the secret nonce is supplied through a dummy RNG even though `mbedtls_ecdsa_write_signature` may use deterministic ECDSA in this version. It matches ABACUS's 192-bit curve size and secret private-key/nonce split. The concrete ABACUS seeds are valid P-192 scalars; symbolic runs still do not constrain raw secret inputs before the library sees them. |

## Reconciliation Guidance

- Use repository defaults for primary symbolic-execution campaigns because they
  have explicit secret/public roles and avoid broad symbolic key setup.
- Add `abacus_compat` targets only when direct trace-level comparison matters.
  Those targets should match ABACUS function names and high-input regions,
  even if the model is less semantically clean.
- Keep version differences visible in result labels. OpenSSL 1.1.1q is close to
  ABACUS OpenSSL 1.1.1-family rows, but mbedTLS 3.2.1 and Libgcrypt 1.10.1 are
  materially newer than ABACUS 2.15/1.8.5 rows.
- Monocypher rows now live in `bounded.md`; keep their descriptors explicit
  rather than reusing existing selectors with a different interpretation.