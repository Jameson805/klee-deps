# RSA Benchmarking Overview

This document records the current benchmarking model for RSA decryption-style
code across libraries, starting with mbedTLS and OpenSSL 1.1.1q. It is meant
to grow as additional RSA implementations such as BearSSL and libgcrypt are
added.

## Library-Agnostic RSA Decryption Structure

At a high level, RSA decryption code is usually split into three layers.

1. Padding or encoding logic.
   - Examples: PKCS#1 v1.5 type 2 decoding, OAEP decoding, SSLv23 decoding.
   - These routines interpret the decrypted block and recover the message.

2. RSA private primitive.
   - Computes the private-key operation on the ciphertext representative.
   - In software implementations this is often a CRT-based routine built from
     two secret modular exponentiations and one recombination step.

3. Public or high-level API.
   - Exposes full decryption to callers.
   - Often performs input checks, chooses padding mode, invokes the private
     primitive, and dispatches to padding removal.

The core benchmarking question is which layer is being measured:

1. A padding-only utility.
2. The internal RSA private primitive.
3. The complete decrypt API.

## Benchmarking Approach

The benchmark set is intended to separate these layers instead of collapsing
 them into one target.

For RSA decryption-style code we currently use three target families.

1. Padding-only targets.
   - Benchmark only the decoding or unpadding function.
   - No RSA private key operation is executed.

2. Private-primitive targets.
   - Benchmark the internal RSA private operation directly.
   - This isolates the CRT exponentiation and recombination logic from the API
     layer and from higher-level scheme handling.

3. Full decrypt targets.
   - Benchmark the complete public or EVP-facing decrypt path.
   - This captures the real library-visible control flow, including padding
     selection and any API-specific preprocessing or postprocessing.

This split is useful because different libraries place scheme logic in
different places. For example, some libraries perform OAEP removal inside the
low-level RSA decrypt routine, while others split the raw private operation and
OAEP decode at a higher API layer.

## Public APIs And Internal Calls

The public API is the function family exposed to applications. The internal
call chain is the concrete implementation chosen underneath.

Typical public layers include:

1. Low-level algorithm-specific RSA APIs.
   - Examples: `mbedtls_rsa_private`, `mbedtls_rsa_rsaes_*_decrypt`,
     `RSA_private_decrypt`.

2. Higher-level generic public-key APIs.
   - Example: OpenSSL EVP via `EVP_PKEY_decrypt`.

Typical internal layers include:

1. Internal RSA private primitive.
   - Example: OpenSSL `rsa_ossl_mod_exp`.

2. Generic modular exponentiation backend.
   - Example: OpenSSL `BN_mod_exp_mont` and
     `BN_mod_exp_mont_consttime`.

3. Padding helpers.
   - Examples: `RSA_padding_check_PKCS1_type_2`,
     `RSA_padding_check_PKCS1_OAEP_mgf1`,
     `RSA_padding_check_SSLv23`.

## Current Library Mapping

### mbedTLS

Current RSA benchmarks are split into:

1. `modexp`
   - Core modular exponentiation only.

2. `rsa_private`
   - Internal private operation benchmark.

3. `rsa_rsaes_pkcs1_v15_decrypt`
   - Full PKCS#1 v1.5 decrypt benchmark.

4. `rsa_rsaes_oaep_decrypt`
   - Full OAEP decrypt benchmark.

5. `pkcs1_v15_unpadding`
   - Padding-only benchmark.

The active model uses a valid concrete 1024-bit key with symbolic CRT
exponents `DP` and `DQ` and disables blinding locally.

### OpenSSL 1.1.1q

OpenSSL RSA decryption has the following relevant layers.

1. Public low-level API.
   - `RSA_private_decrypt`.

2. Default software decrypt implementation.
   - `rsa_ossl_private_decrypt`.

3. Internal private primitive.
   - `rsa_ossl_mod_exp`.

4. Generic exponentiation backend.
   - `BN_mod_exp_mont` and `BN_mod_exp_mont_consttime`.

5. Padding utilities.
   - `RSA_padding_check_PKCS1_type_2`.
   - `RSA_padding_check_PKCS1_OAEP_mgf1`.
   - `RSA_padding_check_SSLv23`.

6. Higher-level public-key API.
   - EVP decrypt through `EVP_PKEY_decrypt`, which reaches the RSA method via
     `pkey_rsa_decrypt`.

The OpenSSL RSA benchmark set mirrors the same split:

1. Padding-only utility targets.
2. Internal private-primitive target through `rsa->meth->rsa_mod_exp`.
3. Full EVP-facing decrypt targets.

### Libgcrypt 1.10.1

Libgcrypt now follows the same three-stage model in the repository descriptor
layer, with one deliberate difference from the long-term ideal split.

1. Full decrypt API target.
   - Use the public RSA decrypt entrypoint `gcry_pk_decrypt` (or its internal
     helper `_gcry_pk_decrypt`) as the top-level benchmark target.
   - This matches the public API layer in the other libraries and captures
     padding-choice and decoding dispatch.

2. Internal private-primitive target.
    - A direct `secret_core_crt` benchmark remains the natural private-core
       analogue and is still the clearest next extension if a Libgcrypt-only CRT
       comparison becomes necessary.
    - The current repository implementation does not add that extra target.
       Instead, it covers Libgcrypt through `gcry_pk_decrypt` modes plus the
       internal padding helpers.
    - This keeps the current Libgcrypt selector smaller while still exposing
       the public decrypt path and the unpadding helpers that match the other
       libraries.

3. Padding-only targets.
   - Use `_gcry_rsa_pkcs1_decode_for_enc` and
     `_gcry_rsa_oaep_decode` as the two unpadding benchmark targets.
   - These are the libgcrypt equivalents of the PKCS#1 v1.5 and OAEP padding
     helpers used in the other libraries.

The current Libgcrypt benchmark set therefore mirrors the same overall layering
as mbedTLS and OpenSSL, with the private arithmetic observed through the public
decrypt path rather than a separate CRT-only target:

1. A padding-only benchmark for PKCS#1 v1.5 and OAEP decoding.
2. A full public decrypt benchmark through the libgcrypt RSA decrypt API.

This keeps the Libgcrypt measurement split aligned with the rest of the RSA
benchmark family while accounting for its built-in blinding behavior and the
current repository scope.

## Simplifications Used In Benchmarks

The RSA benchmarks intentionally simplify several aspects of the production
implementations.

### Blinding Is Disabled

We disable blinding in key-using private-operation benchmarks.

Why:

1. Blinding introduces extra randomness and extra exponentiation work that is
   orthogonal to the secret-dependent control flow we want to compare.
2. It adds noise across libraries because blinding is integrated differently in
   each implementation.
3. The benchmark goal here is stable comparison of the private primitive and
   decrypt pipeline, not evaluation of randomness-dependent countermeasures.

### Concrete Modulus-Domain Key Fields

We keep the fields that define the RSA modulus and CRT recombination concrete.

These include, depending on the library:

1. The modulus `N`.
2. Prime factors `P` and `Q` when the implementation uses CRT.
3. CRT recombination coefficients such as `QP` or `iqmp`.
4. Public exponent `E` when it is used for verification or API setup.

Why:

1. These fields control key validity, Montgomery setup, reduction domains, and
   CRT recombination.
2. Making them symbolic shifts the benchmark toward key reconstruction and key
   validity logic instead of the intended secret exponentiation logic.
3. Keeping them concrete makes the target operate on a valid RSA key and keeps
   the benchmark comparable across libraries.

### Symbolic Exponent Material Only

We make only the exponent material that directly drives the private operation
symbolic.

Examples:

1. mbedTLS: symbolic `DP` and `DQ`.
2. OpenSSL CRT private primitive: symbolic `dmp1` and `dmq1`.

Why:

1. This focuses the symbolic complexity on the private exponentiation loops.
2. It avoids spending search budget on key completion and key derivation.
3. It matches the stable model that already worked for mbedTLS.

### Concrete Valid Base Key

We load a valid concrete base key and overwrite only the selected symbolic
fields.

Why:

1. It preserves a valid modulus, factorization, and public key structure.
2. It avoids benchmark time being dominated by key import or reconstruction.
3. It keeps the benchmark anchored in the intended private operation.

## Justification From Prior Experiments

The mbedTLS exploratory models are archived in
`benchmarks/mbedtls-3.2.1/examples/rsa_full_pipeline_attempts/README.md`.

Those experiments showed that broader symbolic key models were not a good fit
for the current benchmark objective.

Observed problems included:

1. Key reconstruction dominating the search.
2. Search getting stuck before reaching the intended private-operation work.
3. Full symbolic-key variants concentrating almost entirely inside the first
   large CRT exponentiation.

That is why the active model is now:

1. valid concrete key,
2. symbolic exponent material only,
3. blinding disabled,
4. separate padding-only benchmarks.

## What Is Benchmarked And What Is Not

Benchmarked:

1. Padding checks themselves.
2. Internal private RSA primitives.
3. Full decrypt entry points.

Not benchmarked directly:

1. Key generation.
2. Key reconstruction from symbolic primes.
3. Blinding randomness generation and maintenance.
4. Broader certificate or protocol plumbing around RSA.

## Planned Extension Points

This document is intended to also cover:

1. BearSSL.
2. libgcrypt.
3. any future RSA implementation added to the benchmark suite.

When adding a new library, the same questions should be answered.

1. What is the public decrypt API?
2. What is the internal private primitive?
3. What are the padding-only utilities?
4. Which key fields must remain concrete to keep the target meaningful?
5. Which exponent fields can be made symbolic while keeping the benchmark
   focused on the intended secret-dependent work?