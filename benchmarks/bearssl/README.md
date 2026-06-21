BearSSL Runner Integration
==========================

This directory contains four BearSSL CBC benchmarks integrated with the shared
runner artifact generator:

- `aes_big`, the original table-based AES benchmark, configured by `configs/runner/bearssl_aes_big_runner_config.toml`
- `aes_ct`, the constant-time AES benchmark, configured by `configs/runner/bearssl_aes_ct_runner_config.toml`
- `des_tab`, configured by `configs/runner/bearssl_des_tab_runner_config.toml`
- `des_ct`, configured by `configs/runner/bearssl_des_ct_runner_config.toml`

The integration keeps the original schedule-and-data input shape while using
target-specific schedule widths for the local benchmark model.

Configuration Choices
---------------------

The original Binsec benchmark wrappers treated only the expanded key schedule
and the input data as secret inputs. They did not model public symbolic inputs.

The runner-based integration keeps the same key-schedule focus, but uses public
symbolic data and IV inputs for the repository model.

- `skey_buf` is secret.
- `data_buf` is public.
- `iv_buf` is public.
- `N_ROUND` stays fixed at `2`.
- Each benchmark currently exposes exactly one preset, named `default`.

This means the generated fix-pub and var-pub artifacts still exist for tooling
uniformity, and var-pub makes the public data and IV buffers symbolic.

Schedule Input Widths
---------------------

The original wrappers made the full `ctx.skey` storage symbolic.

- `aes_big` stores `uint32_t skey[60]`, which is 240 bytes.
- `aes_ct` stores `uint32_t skey[60]`, which is 240 bytes.
- `des_tab` stores `uint32_t skey[96]`, which is 384 bytes.
- `des_ct` stores `uint32_t skey[96]`, which is 384 bytes.

The runner uses the full `ctx.skey` storage for all four CBC targets. This keeps
the schedule input width aligned with the Constantine/BINSEC wrappers instead of
optimizing away schedule words that the reduced-round execution does not read.

Why Use Full Expanded Schedules
-------------------------------

The wrappers expose expanded schedule storage directly. They do not call the
library key-schedule initializers, so `skey_buf` is not a raw AES or DES key.

The fixed `N_ROUND=2` execution may consume only a prefix of that schedule, but
the source benchmark model marks the full storage as high input. The repository
therefore keeps the full 240-byte AES schedule and full 384-byte DES schedule
for parity with the external model while still treating data and IV as public
repository inputs.

Why Not Reuse Mod-Exp Style Sizes Like 4 Or 16 Bytes
----------------------------------------------------

This is the key difference from the modular-exponentiation benchmarks.

In the mod-exp benchmarks, `SYM_SIZE` is the width of the real input buffers.
If `SYM_SIZE=4`, then all 4 bytes of `exp_buf`, `base_buf`, and `mod_buf` are
the intended benchmark inputs, and the code consumes those buffers directly as
big-endian integers.

That is not what `ctx.skey` means in the BearSSL wrappers.

- `ctx.skey` is not a raw AES or DES key.
- It is the expanded schedule storage used internally by the cipher code.
- The current wrappers do not call the key-schedule initializers.
- They directly expose schedule words to the benchmark.

Because of that, choosing 4 or 16 bytes for `skey_buf` would not give a
smaller but equivalent benchmark. It would give a partially symbolic schedule
and force the rest of the schedule words to stay zero.

For AES at `N_ROUND=2`:

- 240 bytes matches the full `uint32_t skey[60]` source model.
- 48 bytes would cover all 12 schedule words that `aes_big` actually reads,
	but it would no longer match the Constantine/BINSEC high-input size.
- 16 bytes would cover only the first 4 words, i.e. only the initial
	AddRoundKey.
- The next 8 words used by the middle and final rounds would stay zero because
	the context is zero-initialized.
- 4 bytes would cover only one of those 12 words.

For DES at `N_ROUND=2`:

- 384 bytes matches the full `uint32_t skey[96]` source model.
- 256 bytes would cover all 64 schedule words that `des_tab` actually reads,
	but it would no longer match the Constantine/BINSEC high-input size.
- 16 bytes would cover only the first 4 words of the first 32-word schedule
	block.
- The remaining 60 words actually consumed by the two-round wrapper would stay
	zero.
- 4 bytes would cover only one of the 64 consumed words.

So 4-byte or 16-byte schedule buffers are not wrong in the sense of C memory
safety if copied into a zero-initialized `ctx.skey`, but they define a very
different benchmark: most of the schedule used by the cipher becomes fixed zero
instead of symbolic.

For `aes_ct` and `des_ct`, smaller schedule buffers would also stop matching the
BINSEC-style full-schedule high input.

If the goal is to use small semantic key sizes such as 16-byte AES keys or
8-byte DES keys, then the benchmark should switch to a raw-key model and call
the library key-schedule initialization functions. That is a different design
from the current schedule-based benchmark and was intentionally not mixed into
this integration.

Chosen Sizes
------------

The single presets currently use these macro values.

- `aes_big`: `SKEY_LEN=240`, `DATA_LEN=32`, `IV_LEN=16`, `N_ROUND=2`
- `aes_ct`: `SKEY_LEN=240`, `DATA_LEN=32`, `N_ROUND=2`
- `des_tab`: `SKEY_LEN=384`, `DATA_LEN=16`, `IV_LEN=8`, `N_ROUND=2`
- `des_ct`: `SKEY_LEN=384`, `DATA_LEN=32`, `N_ROUND=2`

The data lengths are fixed per target for the default materialization.

- `aes_big` keeps 32 bytes, which is two AES blocks.
- `aes_ct` uses 32 bytes, the smallest BINSEC bounded data length for this
	target. Other BINSEC sources also use 48, 64, 80, and 96 bytes.
- `des_tab` keeps 16 bytes, which is two DES blocks.
- `des_ct` uses 32 bytes, one of the BINSEC bounded data lengths for this
	target. Other BINSEC sources also use 16, 24, and 40 bytes.

The IV has a public runner buffer. The default and fix-pub materializations keep
it all zero, matching the original wrappers; var-pub can make it symbolic for
repository comparisons that treat IV as public input.

Why Only One Preset
-------------------

These benchmarks currently have one supported materialization each.

- The schedule widths match the full BINSEC-style high schedule input.
- The data length is fixed per target; `aes_ct` chooses the smallest BINSEC
	bounded length, and `des_ct` chooses the 32-byte bounded length.
- Public data and IV defaults are fixed by the single preset and become symbolic
	in var-pub mode.
- Smaller `size_N` labels such as 4 or 16 would be misleading because, in this
	benchmark model, they would mean partially symbolic schedule prefixes rather
	than semantic AES or DES key sizes.

Because of that, a single `default` preset is easier to read and less
misleading than introducing synthetic `size_N` names that do not correspond to
the original wrappers.

ABACUS Seed Values
------------------

ABACUS requires concrete seed bytes before `abacus_make_symbolic(...)` is
called. The BearSSL presets therefore use deterministic large prime values that
fit within each secret buffer width.

The exact numeric value is not semantically important. The goal is simply to
start from a non-trivial concrete secret instead of an all-zero or
uninitialized buffer.

Generated Artifacts
-------------------

The generic benchmark builder emits target-local generated artifacts because
the wrappers do not all share one concrete materialization.

- `generated/aes_big/runner_config.generated.h`
- `generated/aes_ct/runner_config.generated.h`
- `generated/des_tab/runner_config.generated.h`
- `generated/des_ct/runner_config.generated.h`
- target-local BINSEC cfgs under the same directories when BINSEC mode is built
- built executables and bitcode under `artifacts/<mode>/<target>/`

This keeps the wrapper integrations isolated while still using the same
generic generator and `runner.h` runtime contract.
