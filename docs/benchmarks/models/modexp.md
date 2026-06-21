# Modular Exponentiation Benchmark Models

This page documents the modular-exponentiation benchmark model used by the
BearSSL, Libgcrypt, mbedTLS, and OpenSSL modular-exponentiation targets.
The exact byte values are owned by
`../../../configs/runner/modexp_runner_config.toml`; this page records what kind
of values they are and why the symbolic inputs are shaped this way.

## Model Summary

Modular exponentiation computes `base^exp mod mod`. The benchmark models the
common cryptographic setting where the exponent is private key material and the
base and modulus are public operation parameters.

| Selector target | Invoked backend shape | Repository implementation |
| --- | --- | --- |
| `bearssl:modexp` / `modexp` | BearSSL i32 modular exponentiation path. | Calls the BearSSL i32 backend with shared `exp`, `base`, and `mod` buffers. |
| `libgcrypt:default` / `modexp` | Libgcrypt MPI exponentiation path. | Calls the Libgcrypt 1.10.1 MPI exponentiation implementation. |
| `libgcrypt:sliced` / `modexp` | KLEE-CF sliced Libgcrypt exponentiation variant. | Uses the same inputs as `libgcrypt:default`; only the implementation body is sliced. |
| `mbedtls:default` / `modexp` | `mbedtls_mpi_exp_mod` wrapper. | Calls the mbedTLS 3.2.1 modular exponentiation backend. |
| `mbedtls:sliced` / `modexp` | KLEE-CF sliced mbedTLS exponentiation variant. | Uses the same inputs as `mbedtls:default`; only the implementation body is sliced. |
| `openssl:default` / `recp` | OpenSSL reciprocal modular exponentiation backend. | Selects the reciprocal backend through the wrapper define. |
| `openssl:default` / `mont` | OpenSSL Montgomery modular exponentiation backend. | Selects the Montgomery backend through the wrapper define. |
| `openssl:default` / `mont_consttime` | OpenSSL constant-time Montgomery backend. | Selects the constant-time Montgomery backend through the wrapper define. |
| `openssl:default` / `mont_word` | OpenSSL word-sized Montgomery backend. | Selects the word-sized Montgomery backend through the wrapper define. |
| `openssl:sliced` / `recp`, `mont`, `mont_word` | KLEE-CF sliced OpenSSL variants. | Uses the same inputs as `openssl:default`; `mont_consttime` is excluded from the sliced selector. |

All implemented targets intentionally use the same input model so differences
come from library code and selected backend rather than from benchmark shape.

| Generic input | Usual meaning | Active benchmark value |
| --- | --- | --- |
| `exp` | Secret exponent. | Symbolic secret buffer of width `SYM_SIZE`; ABACUS starts from the second largest prime representable in that width. |
| `base` | Public base or ciphertext/message representative. | Public buffer of width `SYM_SIZE`; concrete fixed default is a small one-byte prime; symbolic public input in `var_pub`. |
| `mod` | Public modulus. | Public buffer of width `SYM_SIZE`; concrete fixed default is the largest prime representable in that width; symbolic public input in `var_pub`. |

The current presets use `SYM_SIZE` values of 1, 2, 4, 8, and 16 bytes. These are
not intended to be realistic production RSA key sizes. They are small symbolic
models that let the tools reach exponentiation behavior while still exploring
different operand widths.

The repository-specific sliced selectors are part of this group. They use the
same secret exponent and public base/modulus inputs as the unsliced modular
exponentiation targets; only the implementation body is sliced for focused
KLEE-CF experiments.

## Detailed Input Variables

The table below names every input variable used by every modular-exponentiation
target. The concrete defaults are shared across targets and vary only by the
selected `SYM_SIZE` preset.

| Selector targets | Input variable | Kind | Size | Concrete value | Symbolic when | Rationale |
| --- | --- | --- | --- | --- | --- | --- |
| All modular-exponentiation targets | `exp` | Secret | `SYM_SIZE` bytes | Second largest prime representable in the selected width. | `fix_pub` and `var_pub`. | Starts from a nondegenerate exponent while keeping the exponent as the only secret in fixed-public runs. |
| All modular-exponentiation targets | `base` | Public | `SYM_SIZE` bytes | Small prime: `0x03` for 1 byte, `0xfb` for wider presets. | `var_pub`. | Stable public representative that avoids a zero base and does not drive secret variation. |
| All modular-exponentiation targets | `mod` | Public | `SYM_SIZE` bytes | Largest prime representable in the selected width. | `var_pub`. | Avoids invalid zero, collapsed modulus-one behavior, and small composite moduli. |

## Concrete Defaults

The fixed-public defaults are intentionally prime and nontrivial. For an
`N`-byte preset, "largest representable" means largest prime less than or equal
to `2^(8N) - 1`; "second largest" means the prime immediately below that.

| Input class | Concrete value | Symbolic when | Rationale and caveats |
| --- | --- | --- | --- |
| Exponent `exp` | Second largest prime representable in the selected width. | `fix_pub` and `var_pub`. | Avoids starting concrete replay from a degenerate zero exponent while keeping the benchmark domain symbolic. |
| Base `base` | Small one-byte prime: `0x03` for the 1-byte preset and `0xfb` for wider presets. | `var_pub`. | Gives a stable public representative without making the base the source of secret variation. |
| Modulus `mod` | Largest prime representable in the selected width. | `var_pub`. | Avoids zero, one, and easy small composite moduli; prime values are expected to keep more intermediate residues active. |

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

## Sliced Variants

Slicing is currently a modular-exponentiation feature. The sliced selectors are
therefore reported with the modular-exponentiation group rather than as a
separate repository-specific benchmark family.

| Selector | Coverage | Difference from the unsliced selector |
| --- | --- | --- |
| `libgcrypt:sliced` | Libgcrypt `modexp`. | Same input model; reduced implementation body. |
| `mbedtls:sliced` | mbedTLS `modexp`. | Same input model; reduced implementation body. |
| `openssl:sliced` | OpenSSL `recp`, `mont`, and `mont_word`. | Same input model; excludes `mont_consttime`. |

Report sliced and unsliced results together when the question is about modular
exponentiation behavior. Report them separately only when the question is about
the effect of slicing itself.

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