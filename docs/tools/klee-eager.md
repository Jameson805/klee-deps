# KLEE-Eager

KLEE-Eager is the repository's eager-mode KLEE variant. In the repository runner layer, it is exposed through a thin CLI wrapper and shares the same orchestration path as KLEE-CF and KLEE-Self-Comp.

## What It Is

The CLI wrapper in `scripts/experiments/run_klee_eager.py` dispatches into the shared implementation in `scripts/experiments/run_klee_family.py`.

That means KLEE-Eager shares:

- benchmark-local workspace preparation
- bitcode selection
- KLEE output capture
- conversion into the shared JSON format
- replay integration

The repository keeps the per-tool wrappers thin on purpose so the execution contract is explicit and comparable across KLEE variants.

## Design Model

KLEE-Eager is the eager product-program variant. It reasons about two executions of the same program throughout symbolic execution. Public symbolic inputs are shared by the two executions, while secret symbolic inputs have paired `__prime` arrays that may take different values.

Unlike KLEE-CF, KLEE-Eager does not wait until every observation to build the primed expression from scratch. It carries paired expressions through execution in `Dual` values and uses those paired expressions at branches, switches, calls, memory operations, and selected LLVM instructions.

For a public value, the two sides of the product are identical. For a secret value, the left side uses the original secret array and the right side uses the primed `__prime` array. As instructions execute, KLEE-Eager propagates both expressions together through a `Dual` representation.

This keeps relational state live as the program runs. KLEE-CF instead performs more of the relational construction lazily at observation points.

The basic invariant is:

```text
Dual(value) = { expression in the original execution,
                expression in the primed execution }
```

The two expressions should describe the same program value under two secret assignments. Public inputs and constants are identical on both sides.

## Dual Values And Lockstep Execution

KLEE-Eager augments ordinary KLEE locals with `Dual` locals. A `Dual` stores a left expression and a right expression for the same program value. Helper paths such as `evalDual`, `bindLocalDual`, and dual-aware instruction execution maintain these paired values.

When a value is definitely public or concrete, both sides are the same. When a value depends on secrets, the right side is the expression over primed secrets. Many LLVM instructions propagate dual values structurally by applying the same operation to each side.

At observable operations, KLEE-Eager checks whether the two sides can diverge under the current constraints:

- branches and switches check whether the left and right conditions can differ;
- memory loads and stores check whether the left and right addresses can differ;
- allocation sizes are forced to remain equal;
- external-call arguments are forced to remain equal before the call proceeds.

After checking an observation, KLEE-Eager adds lockstep constraints such as equality of branch conditions, memory addresses, allocation sizes, or external-call arguments. This preserves first-difference reporting: later reports are only considered after earlier observations are constrained to agree.

For a current observation with left-side value `v_L` and right-side value `v_R`, the check has this shape:

\[
    \Pi \land v_L \ne v_R.
\]

Here `Pi` is the current KLEE constraint set, including the lockstep equalities already added for earlier observations. If this formula is satisfiable, KLEE-Eager can report the current observation. If execution continues past the observation, it adds `v_L == v_R` to keep the two executions in lockstep for later checks.

## Secret Renaming Fallback

KLEE-Eager still has a `renameSecret` implementation. It currently uses per-call visited maps, not executor-wide caches. The recursion matches the corrected design used by KLEE-CF:

- replace a secret `ReadExpr` root array with its primed array;
- recursively rename the read index;
- recursively rename update-list indices and values;
- recursively rebuild non-read expression children when needed.

This fallback matters because not every KLEE instruction path necessarily computes full dual semantics. The runner-exposed `--product-program-fallback` option controls whether `bindLocal()` repairs missing or stale dual values by synthesizing the right side through `renameSecret(value)`.

When the fallback is enabled, `bindLocal()` stores the scalar value, computes the expected `Dual{value, renameSecret(value)}`, and then:

- fills an unset dual destination;
- warns once when an instruction has no explicit dual semantics;
- checks whether existing `Dual.left` or `Dual.right` can differ from the expected value under current constraints;
- repairs mismatching sides when necessary.

When the fallback is disabled, `bindLocal()` only binds the scalar value and does not repair the dual destination. This makes explicit dual coverage more visible, but it can leave instructions without dual propagation.

## Counterexample Generation

KLEE-Eager reports through `checkLogCounterexample`. The function receives a divergence condition such as `left != right`, asks the solver whether that condition may be true under current constraints, and, when it is, solves for original symbolic objects plus primed secret objects.

The emitted KTests therefore contain both `<name>` and `<name>__prime` assignments for secret inputs. Unlike KLEE-CF's concrete-model path, KLEE-Eager does not currently use the staged chosen-value candidate ladder documented for `--use-cv-model`. Its witness path is solver-backed once a possible divergence condition is identified.

## What Makes It Different Here

At the runner surface, the one KLEE-Eager-specific user-facing option exposed by the shared runner is `--product-program-fallback`.

In `klee-eager/lib/Core/Executor.cpp`, that option is described as enabling bindLocal dual fallback or repair for product-program execution when eager mode would otherwise bind only the scalar value.

This is the main eager-specific CLI distinction exposed by the repository runner today.

## How To Run It

Canonical entrypoint:

```bash
python -m scripts.experiments.run_klee_eager 1m --sym-size 4 --benchmarks bearssl:modexp
```

To enable the eager-specific fallback path:

```bash
python -m scripts.experiments.run_klee_eager 1m --sym-size 4 --product-program-fallback --benchmarks bearssl:modexp
```

## Runner Model

The shared KLEE-family runner applies the same generic execution flow used by KLEE-CF and KLEE-Self-Comp:

- benchmark-local bitcode under `benchmarks/.../artifacts/klee/...`
- shared KLEE flags for libc, kdalloc, solver backend, and output shape
- conversion through `tools.converters.klee_log_to_json`
- replay of positives through the benchmark replay executable

This keeps eager-mode comparisons close to the other KLEE variants at the runner layer.

## Important Option Surface

- `--product-program-fallback`: eager-specific fallback or repair mode surfaced by the shared runner
- `--solver-backend=...`
- `--search=...`
- `--loop-max-iterations=...`
- `--optimize-array=...`

## Implementation Notes

The main implementation anchors are:

- `klee-eager/lib/Core/Executor.cpp`: `Dual` evaluation and binding, branch/switch checks, memory checks, external-call lockstep checks, `renameSecret`, and `checkLogCounterexample`;
- `klee-eager/lib/Core/ExecutionState.h`: eager state extensions, including dual locals and dual address-space state;
- `scripts/experiments/run_klee_family.py`: runner-level exposure of `--product-program-fallback`.

These implementation files define the current eager product-program behavior. In particular, the code carries `Dual` expressions through execution instead of relying only on observation-time renaming.

## Strengths Of The Current Design

- The runner structure is simple and auditable.
- The eager-specific option surface is not buried in separate orchestration code.
- Relational expressions are available at many instruction boundaries instead of being reconstructed only at observation sites.
- Lockstep constraints are explicit at branches, switches, memory operations, allocation sizes, and external-call boundaries.

## Known Limits

- Dual semantics must be maintained across many LLVM instruction cases, so instruction coverage is easier to drift than KLEE-CF's mostly lazy observation-time renaming.
- `--product-program-fallback` is a repair path, not a substitute for auditing explicit dual semantics.
- KLEE-Eager currently lacks a focused note comparable to `../notes/klee-cf-candidate-models.md` for performance and validation details.

## Examples To Start With

Use the same benchmark entrypoints as the other KLEE-family runners first. For toy programs and local helpers, see `../../examples/README.md`.