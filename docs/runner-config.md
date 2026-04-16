# Runner Config

A runner config describes the benchmark buffers and preset values that are materialized into generated runner artifacts at build time.

The current shared modular-exponentiation config lives at `configs/runner/modexp_runner_config.json`. Mbed TLS, Libgcrypt, and OpenSSL 1.1.1q all consume this same config and emit benchmark-local artifacts under their own `generated/` directories.

Not every benchmark needs to share one config source. BearSSL `aes_big` and `des_tab` use benchmark-local configs in `configs/runner/bearssl_aes_big_runner_config.json` and `configs/runner/bearssl_des_tab_runner_config.json` because they keep different effective schedule sizes while still using the same generator and `runner.h` contract. See `benchmarks/bearssl/README.md` for the rationale behind those choices.

The file is parsed as a Python literal instead of strict JSON. This is intentional: it keeps byte arrays and large integers readable with `0x...` literals and plain `True`/`False` values.

## Build Model

Each build materializes exactly one preset.

Most benchmark build scripts still pass `--preset NAME` explicitly. If a config defines exactly one preset, the generator can select it implicitly and the build script may omit `--preset`.

Higher-level experiment runners may still keep an internal `sym_size` setting and translate it to `--preset size_N` at the build-script boundary when a benchmark family exposes size-based presets.

The generator then:

- emits `generated/runner_config.generated.h` inside the benchmark being built, or a target-local variant such as `generated/<target>/runner_config.generated.h` when one build script owns multiple wrappers with different materializations
- optionally emits generated BINSEC cfgs such as `generated/binsec_fix_pub.cfg` and `generated/binsec_var_pub.cfg`, again optionally under a target-local generated subdirectory
- defines the preset macros such as `SYM_SIZE` directly in the generated header
- emits zero or one set of public default values per public input
- emits exactly one set of ABACUS secret seeds
- includes `runner.h`, which provides the generic runner logic

The runner artifact generator is `tools/generate_runner_artifacts.py`.

For BINSEC, the checked-in shared prelude lives in `configs/binsec/binsec_base.cfg`. The generator concatenates that shared base with mode-specific declarations derived from `inputs` and `mode_policy`, then appends the common BINSEC trailer. The old checked-in `binsec_fix_pub.cfg` and `binsec_var_pub.cfg` files are gone; builds now rely on benchmark-local generated cfg outputs only.

This means the compiler command line should not redefine preset-owned macros such as `SYM_SIZE`.

## Top-Level Fields

`inputs`

- List of benchmark buffers.
- Each input must have:
  - `id`: C identifier used for the generated global buffer
  - `name`: symbolic label used by KLEE, ABACUS, replay extraction, and emitted counterexamples
  - `kind`: `"secret"` or `"public"`
  - `size`: integer byte length or a macro name defined by the selected preset
- `id` and `name` are both required and must be unique within the config.
- Optional `constraints` currently supports:
  - `top_bit_set`
  - `odd`

`mode_policy`

- Documents and constrains the supported runner modes.
- Current generator expectations are:
  - `var_pub.public_symbolic == True`
  - `fix_pub.public_symbolic == False`
  - `abacus.public_fixed == True`
  - `abacus.secret_inputs` must list every secret input
- These checks keep the descriptor aligned with the runner implementation instead of letting stale metadata drift silently.
- BINSEC declaration generation uses `var_pub.public_symbolic` and `fix_pub.public_symbolic` to decide whether public globals belong in the generated cfg.

`presets`

- Map from preset name to one concrete materialization.
- Prefer semantic names such as `size_1`, `size_2`, and so on.

## Preset Fields

`macros`

- Macro values defined directly in the generated header for that preset.
- Example:

```python
"macros": {
  "SYM_SIZE": 16
}
```

`vars`

- Concrete defaults for public inputs.
- Every public input must be present.
- If a benchmark has no public inputs, `vars` may be an empty dictionary.
- Each value may be either:
  - one non-negative integer, expanded big-endian to the buffer width
  - a full byte list

Examples:

```python
"vars": {
  "base_buf": 0xfb,
  "mod_buf": 0xffffffffffffffffffffffffffffff61
}
```

```python
"vars": {
  "base_buf": [0x00, 0xfb],
  "mod_buf": [0xff, 0xf1]
}
```

`abacus_secrets`

- Concrete seed values for secret inputs in ABACUS mode.
- Every secret input listed in `mode_policy.abacus.secret_inputs` must be present.
- Uses the same value formats as `vars`.
- These values are copied into the secret buffers before `abacus_make_symbolic(...)` is called, because ABACUS expects a valid starting secret rather than an uninitialized buffer.

## Generated BINSEC Configs

For benchmarks that opt into this flow, the generator can also emit BINSEC cfg files.

- The shared allocator and libc replacement logic lives in `configs/binsec/binsec_base.cfg`.
- The generated fix-pub cfg declares only secret inputs.
- The generated var-pub cfg declares secret inputs and public inputs.
- Public default bytes are still owned by the generated header and executable, not by the BINSEC cfg.
- Even when the config source is shared, the emitted BINSEC cfgs stay benchmark-local so build products remain isolated and easy to inspect.

## Benchmark-Specific Notes

Some benchmark integrations intentionally use benchmark-local macros and sizes instead of one shared `SYM_SIZE` abstraction.

- BearSSL `aes_big` and `des_tab` keep the original wrappers' fixed zero IV and original `DATA_LEN` values.
- Those BearSSL wrappers now make only the effective prefix of `ctx.skey` symbolic, not the full backing array, because the wrappers hardcode `N_ROUND=2` and never read the unused tail.
- For BearSSL, mod-exp-style `size_4` or `size_16` presets would be misleading: unlike `SYM_SIZE` in the modular-exponentiation benchmarks, `ctx.skey` is an expanded internal schedule, not a raw semantic key buffer. Smaller widths there would produce partially symbolic schedules with the remaining consumed words fixed to zero.
- They therefore use a single `default` preset per target instead of exposing a family of `size_N` presets.
- They also currently model only secret inputs, so `vars` is empty and the generated fix-pub and var-pub artifacts differ only by mode plumbing, not by any extra public buffers.

## Example

In this example, `id` keeps the generated C buffer names stable while `name`
matches the symbolic object names expected by the replay and counterexample
tooling, and the same `inputs` section is also used to generate BINSEC secret or public declarations.

```python
{
  "inputs": [
    {"id": "exp_buf", "name": "exp", "kind": "secret", "size": "SYM_SIZE"},
    {"id": "base_buf", "name": "base", "kind": "public", "size": "SYM_SIZE"},
    {"id": "mod_buf", "name": "mod", "kind": "public", "size": "SYM_SIZE", "constraints": ["top_bit_set", "odd"]}
  ],
  "mode_policy": {
    "var_pub": {"public_symbolic": True},
    "fix_pub": {"public_symbolic": False},
    "abacus": {
      "secret_inputs": ["exp_buf"],
      "public_fixed": True
    }
  },
  "presets": {
    "size_1": {
      "macros": {"SYM_SIZE": 1},
      "vars": {
        "base_buf": 0x03,
        "mod_buf": 0xfb
      },
      "abacus_secrets": {
        "exp_buf": 0xf1
      }
    }
  }
}
```
