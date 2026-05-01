BearSSL Runner Integration
==========================

This directory contains two BearSSL CBC benchmarks integrated with the shared
runner artifact generator:

- `binsec_aes_big`, configured by `configs/runner/bearssl_aes_big_runner_config.toml`
- `appliedcryp_des`, configured by `configs/runner/bearssl_des_tab_runner_config.toml`

The integration intentionally preserves the original benchmark shape as closely
as possible while reducing unnecessary symbolic state.

Configuration Choices
---------------------

The original Binsec benchmark wrappers treated only the expanded key schedule
and the input data as secret inputs. They did not model public symbolic inputs.

The runner-based integration keeps that structure.

- `skey_buf` is secret.
- `data_buf` is secret.
- There are no public symbolic inputs.
- The IV stays fixed to all-zero bytes.
- `N_ROUND` stays fixed at `2`.
- Each benchmark currently exposes exactly one preset, named `default`.

This means the generated fix-pub and var-pub artifacts still exist for tooling
uniformity, but there are no public buffers that differ between those modes.

Why Use The Effective Length Of `ctx.skey`
------------------------------------------

The original wrappers made the full `ctx.skey` storage symbolic.

- `aes_big` stores `uint32_t skey[60]`, which is 240 bytes.
- `des_tab` stores `uint32_t skey[96]`, which is 384 bytes.

That is larger than what the current wrappers actually read, because both
wrappers hardcode `N_ROUND=2`.

For `aes_big`, the encryption path consumes only 12 schedule words when
`num_rounds == 2`.

- 4 words for the initial AddRoundKey
- 4 words for the one middle-round key
- 4 words for the final-round key

That is 12 `uint32_t` values, or 48 bytes.

This is exactly what the code does in `br_aes_big_encrypt(...)`.

- It first xors `skey[0]` through `skey[3]` into the state.
- The loop `for (u = 1; u < num_rounds; u++)` runs once when `num_rounds == 2`
	and consumes `skey[4]` through `skey[7]`.
- The final round then consumes `skey[8]` through `skey[11]`.

For `des_tab`, the block-processing loop advances the schedule pointer by 32
words per round block. With `num_rounds == 2`, the wrapper reads 64 schedule
words.

- 2 round blocks
- 32 `uint32_t` words per block

That is 64 `uint32_t` values, or 256 bytes.

Again, this follows directly from the implementation.

- `br_des_tab_process_block(...)` calls `process_block_unit(&l, &r, skey)`.
- After each call it advances the schedule pointer with `skey += 32`.
- With `num_rounds == 2`, the loop runs twice, so the code reads two distinct
	32-word schedule blocks.

The integration therefore makes only the effective prefix symbolic and copies
that prefix into `ctx.skey` with `runner_copy_bytes(...)`. The remainder stays
zero because the context is zero-initialized before the copy.

This reduces unnecessary symbolic bytes for KLEE, BINSEC, and ABACUS without
changing the part of the schedule that the current wrappers actually use.

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

For `aes_big` at `N_ROUND=2`:

- 48 bytes covers all 12 schedule words that the wrapper actually reads.
- 16 bytes would cover only the first 4 words, i.e. only the initial
	AddRoundKey.
- The next 8 words used by the middle and final rounds would stay zero because
	the context is zero-initialized.
- 4 bytes would cover only one of those 12 words.

For `des_tab` at `N_ROUND=2`:

- 256 bytes covers all 64 schedule words that the wrapper actually reads.
- 16 bytes would cover only the first 4 words of the first 32-word schedule
	block.
- The remaining 60 words actually consumed by the two-round wrapper would stay
	zero.
- 4 bytes would cover only one of the 64 consumed words.

So 4-byte or 16-byte schedule buffers are not wrong in the sense of C memory
safety if copied into a zero-initialized `ctx.skey`, but they define a very
different benchmark: most of the schedule used by the cipher becomes fixed zero
instead of symbolic.

If the goal is to use small semantic key sizes such as 16-byte AES keys or
8-byte DES keys, then the benchmark should switch to a raw-key model and call
the library key-schedule initialization functions. That is a different design
from the current schedule-based benchmark and was intentionally not mixed into
this integration.

Chosen Sizes
------------

The single presets currently use these macro values.

- `aes_big`: `EFFECTIVE_SKEY_LEN=48`, `DATA_LEN=32`, `N_ROUND=2`
- `des_tab`: `EFFECTIVE_SKEY_LEN=256`, `DATA_LEN=16`, `N_ROUND=2`

The data lengths intentionally keep the original wrapper values.

- `aes_big` keeps 32 bytes, which is two AES blocks.
- `des_tab` keeps 16 bytes, which is two DES blocks.

The IV is not configurable in the current presets because the original wrappers
used an all-zero IV and did not mark it as symbolic.

Why Only One Preset
-------------------

These benchmarks currently have one supported materialization each.

- The schedule width is derived from the effective prefix consumed at `N_ROUND=2`.
- The data length is inherited from the original wrapper.
- There are no public defaults to vary.
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

`build.sh` emits target-local generated artifacts because the two wrappers do
not share one concrete materialization.

- `generated/binsec_aes_big/runner_config.generated.h`
- `generated/appliedcryp_des/runner_config.generated.h`
- target-local BINSEC cfgs under the same directories when BINSEC mode is built

This keeps the two wrapper integrations isolated while still using the same
generic generator and `runner.h` runtime contract.
