# Modular Exponentiation Benchmark Models

This page documents the modular-exponentiation benchmark model used by the
BearSSL, HACL, Libgcrypt, mbedTLS, and OpenSSL modular-exponentiation targets.
The exact byte values are owned by
`../../../configs/runner/modexp_runner_config.toml`; this page records what kind
of values they are and why the symbolic inputs are shaped this way.

## Model Summary

Modular exponentiation computes `base^exp mod mod`. The benchmark models the
common cryptographic setting where the exponent is private key material and the
base and modulus are public operation parameters.

| Generic input | Usual meaning | Active benchmark value |
| --- | --- | --- |
| `exp` | Secret exponent. | Symbolic secret buffer of width `SYM_SIZE`; ABACUS starts from the second largest prime representable in that width. |
| `base` | Public base or ciphertext/message representative. | Public buffer of width `SYM_SIZE`; concrete fixed default is a small one-byte prime; symbolic public input in `var_pub`. |
| `mod` | Public modulus. | Public buffer of width `SYM_SIZE`; concrete fixed default is the largest prime representable in that width; symbolic public input in `var_pub`. |

The current presets use `SYM_SIZE` values of 1, 2, 4, 8, and 16 bytes. These are
not intended to be realistic production RSA key sizes. They are small symbolic
models that let the tools reach exponentiation behavior while still exploring
different operand widths.

## Concrete Defaults

The fixed-public defaults are intentionally prime and nontrivial. For an
`N`-byte preset, "largest representable" means largest prime less than or equal
to `2^(8N) - 1`; "second largest" means the prime immediately below that.

| Input class | Concrete default kind | Symbolic part | Rationale and caveats |
| --- | --- | --- | --- |
| Exponent `exp` | Second largest prime representable in the selected width. | Whole `exp` buffer is symbolic secret. | Avoids starting ABACUS from a degenerate zero exponent while keeping the actual benchmark domain symbolic. |
| Base `base` | Small one-byte prime: `0x03` for the 1-byte preset and `0xfb` for wider presets. | Whole `base` buffer is symbolic public input in `var_pub`; fixed in `fix_pub`. | Gives a stable public representative without making the base the source of secret variation. |
| Modulus `mod` | Largest prime representable in the selected width. | Whole `mod` buffer is symbolic public input in `var_pub`; fixed in `fix_pub`. | Avoids zero, one, and easy small composite moduli; prime values are expected to keep more intermediate residues active. |

The current values are:

| `SYM_SIZE` bytes | `base` small prime | `mod` largest representable prime | `exp` second largest representable prime |
| --- | --- | --- | --- |
| 1 | `0x03` | `0xfb` | `0xf1` |
| 2 | `0xfb` | `0xfff1` | `0xffef` |
| 4 | `0xfb` | `0xfffffffb` | `0xffffffef` |
| 8 | `0xfb` | `0xffffffffffffffc5` | `0xffffffffffffffad` |
| 16 | `0xfb` | `0xffffffffffffffffffffffffffffff61` | `0xffffffffffffffffffffffffffffff53` |

Validate this invariant from the active runner config with:

```sh
python -m tools.utilities.generate_modexp_defaults
```

The script uses SymPy to check primality, compute the previous primes at each
width boundary, and factor every intervening odd candidate that would otherwise
contradict the largest-prime or second-largest-prime claim.

The concrete modulus choices are especially important. A zero modulus is invalid
for most library APIs, a modulus of one collapses all residues, and small highly
composite values can hide behavior by forcing many intermediate values into a
small set. The current defaults try to keep the arithmetic path alive and varied
without making modulus validity itself the benchmark objective.

## Public Modes

`fix_pub` keeps `base` and `mod` concrete and makes only `exp` symbolic. This is
the cleanest model for private-exponent leakage because any branch or memory
difference should be attributable to the exponent under a stable public domain.

`var_pub` makes `base` and `mod` symbolic public inputs in addition to the
secret exponent. This checks whether findings survive public-parameter variation
and whether the implementation has public-input-dependent paths that interact
with secret exponent behavior. The public inputs are still public in the threat
model; the tool should not report leakage merely because behavior depends on
them.

## Library Mapping

| Selector target | Invoked backend shape | Input model |
| --- | --- | --- |
| `bearssl:modexp` / `modexp` | BearSSL i32 modular exponentiation path. | Shared `exp`, `base`, `mod` model. |
| `hacl_modexp:default` / `modexp32` | HACL 32-bit bignum modular exponentiation wrapper. | Shared `exp`, `base`, `mod` model. |
| `hacl_modexp:default` / `modexp64` | HACL 64-bit bignum modular exponentiation wrapper. | Shared `exp`, `base`, `mod` model. |
| `libgcrypt:default` / `modexp` | Libgcrypt MPI exponentiation path. | Shared `exp`, `base`, `mod` model. |
| `libgcrypt:sliced` / `modexp` | KLEE-CF sliced Libgcrypt exponentiation variant. | Same input model; implementation body is sliced. |
| `mbedtls:default` / `modexp` | `mbedtls_mpi_exp_mod` wrapper. | Shared `exp`, `base`, `mod` model. |
| `mbedtls:sliced` / `modexp` | KLEE-CF sliced mbedTLS exponentiation variant. | Same input model; implementation body is sliced. |
| `openssl:default` / `recp` | OpenSSL reciprocal modular exponentiation backend. | Shared `exp`, `base`, `mod` model. |
| `openssl:default` / `mont` | OpenSSL Montgomery modular exponentiation backend. | Shared `exp`, `base`, `mod` model. |
| `openssl:default` / `mont_consttime` | OpenSSL constant-time Montgomery backend. | Shared `exp`, `base`, `mod` model. |
| `openssl:default` / `mont_word` | OpenSSL word-sized Montgomery backend. | Shared `exp`, `base`, `mod` model. |
| `openssl:sliced` / selected targets | KLEE-CF sliced OpenSSL variants. | Same input model; `mont_consttime` is excluded from the sliced selector. |

## Fidelity And Limits

This model is close to the core side-channel question for exponentiation:
whether private exponent bits influence control flow or memory access. It is not
a full RSA private-key model.

What it preserves:

- Direct modular-exponentiation backend calls across libraries.
- A secret exponent and public base/modulus split.
- Fixed-public and variable-public modes over the same input names.
- Nontrivial concrete defaults that avoid invalid or collapsed arithmetic.

What it simplifies:

- Operand sizes are small compared with production RSA or Diffie-Hellman use.
- `mod` is public and unconstrained in `var_pub`, so symbolic public values may
  include invalid or degenerate moduli unless the wrapper normalizes or the
  library rejects them.
- The model does not prove that a complete RSA or DH operation handles key
  generation, padding, validation, and API layers safely.

## Validation Checklist

- Confirm the wrapper reaches the intended exponentiation backend for each
  library target.
- Confirm `exp` is the only secret input in `fix_pub` mode.
- Confirm `base` and `mod` become symbolic only in `var_pub` mode.
- Revisit any target where fixed `base` or `mod` causes immediate failure,
  residue collapse, or a trivial arithmetic path.
- When changing default moduli or ABACUS exponent seeds, rerun
  `python -m tools.utilities.generate_modexp_defaults` and keep this page in
  sync with the runner config.