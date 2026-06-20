# KLEE-CF

KLEE-CF is the repository's control-flow-oriented KLEE variant for constant-time analysis.

## What It Is

In this repository, KLEE-CF is one member of the shared KLEE-family runner flow. The CLI wrapper in `scripts/experiments/run_klee_cf.py` is intentionally thin and dispatches into `scripts/experiments/run_klee_family.py`.

That shared runner handles the generic orchestration. KLEE-CF contributes the executable surface, mode-specific flags, and the control-flow oriented behavior implemented in the `klee-cf/` tree.

## Design Model

KLEE-CF implements an on-the-fly product-program analysis for constant-time checking. The analysis reasons about two executions of the same program. Public symbolic inputs are shared by the two executions, while secret symbolic inputs may take different values.

An observation is a value visible to the timing side-channel policy: currently a branch decision or a memory address used by a load or store. A finding is a pair of assignments where every earlier observation can be kept equal, but the current observation can differ. This makes the reported location the first distinguishable point for that pair of executions.

KLEE-CF keeps the execution mostly in the shape of ordinary KLEE. It does not execute two full copies of the program. Instead, it tracks each secret symbolic object together with a primed counterpart and checks relational divergence when a branch or memory observation is reached.

The core state is:

- an original symbolic object for each `klee_make_symbolic_sc(..., is_secret=1)` input;
- a primed `__prime` `Array` for each secret object;
- ordinary unprimed arrays for public objects;
- path constraints for the current execution;
- renamed constraints that mirror the current path over the primed secret objects;
- optional state-local concrete assignments used by the concrete-model optimization.

The core query shape is:

\[
    \pi \land \operatorname{PRIME}(\pi) \land
    o \ne \operatorname{PRIME}(o).
\]

Here `pi` is the current path condition, `PRIME(pi)` is the same path condition after secret arrays have been renamed to their `__prime` arrays, and `o` is the branch condition or memory address being checked. Public arrays are unchanged by renaming, so both executions agree on public inputs.

## Secret And Prime Array Creation

KLEE-CF extends symbolic input creation in `Executor::executeMakeSymbolic`. Public symbolic objects behave like ordinary KLEE arrays. Secret symbolic objects are created with `Array::isSecret` set, and KLEE-CF immediately creates a second array whose name appends `__prime`.

The executor keeps a `prime` map from the original secret array name to the primed array. When the concrete-model path is enabled, it also initializes a binding for the prime array, because CT checks and renamed constraints can mention both sides of the relational execution.

The user-facing input API is `klee_make_symbolic_sc`. It behaves like `klee_make_symbolic`, but the final `is_secret` argument controls whether the array participates in relational renaming.

Runner configs can still describe input constraints such as `top_bit_set` and `odd`, and the artifact generator keeps support for turning them into KLEE assumptions. Current benchmark configs do not use those constraints because the matching BINSEC cfg assumptions are not generated yet. Keeping them inactive preserves a single input domain when comparing KLEE-CF against the other tools.

## Recursive Secret Renaming

The current `Executor::renameSecret` is the critical implementation point. It transforms an expression into the expression for the primed execution and returns whether any secret-dependent component changed.

For a `ReadExpr`, KLEE-CF currently renames all of these pieces:

- the update-list root array, when the root is marked secret;
- the read index expression, so `A[secret_index]` becomes `A[secret_index']` when the index depends on a secret;
- every update-list node's `index` and `value`, so writes such as `A[public] = secret_value` are mirrored correctly;
- the update-list `next` chain, so older writes are preserved in the primed expression.

For non-read expressions, KLEE-CF recursively renames each child and rebuilds the expression only when at least one child changed. Constants are returned unchanged.

The executor keeps `renameSecretCache` and `renameSecretUpdateCache` in `Executor.h`. These executor-wide caches map original expression and update nodes to renamed results, preventing repeated traversal of large expression DAGs. They are cleared when a new secret array is introduced, because the prime map has changed.

This recursion is necessary because KLEE expressions are DAGs whose secret dependencies may appear below array reads, inside read indices, or inside update lists. Replacing only the read root would miss expressions such as public arrays indexed by secret values or arrays updated with secret-derived values.

## Relational Counterexample Check

When KLEE-CF checks an observable expression, it first calls `renameSecret(cond)`. If renaming does not find a secret dependency, the expression is not reported as non-CT.

If a secret dependency exists, KLEE-CF asks whether the original expression and the primed expression can differ under the current path constraints plus the renamed path constraints. In code, the core divergence condition is `cond != renamedCond`.

KLEE-CF maintains lockstep constraints as execution proceeds. Earlier branch and memory decisions are constrained to match between original and primed secrets. A later report therefore has to satisfy the prefix constraints before it can witness divergence at the current observation.

When a witness is found, KLEE-CF writes assignments for public arrays, original secret arrays, and primed secret arrays. Secret-dependent values appear as `<name>` and `<name>__prime`.

## Concrete-Model Optimization

The current KLEE-CF implementation also includes a concrete-model path controlled by `--use-cv-model`. This is documented in more detail in `../notes/klee-cf-candidate-models.md`.

Each live `ExecutionState` carries a `concreteModel` assignment that must satisfy the state's current constraints. After constraints change, KLEE-CF repairs the model with deterministic candidate assignments or falls back to solver-generated initial values. If the model cannot be repaired, KLEE-CF terminates that state with an execution error rather than continuing with stale model data.

For non-CT checks, the concrete-model path uses an escalation ladder:

1. keep current public inputs and original secrets fixed, then search alternate primed secrets;
2. keep current public inputs fixed, then search both original and primed secrets;
3. leave public inputs symbolic too, then search or solve for public, original secret, and primed secret values.

At each level, KLEE-CF tries explicit concrete candidates before the corresponding solver query. The candidate order is the current state model, then fixed one-byte `1`, then all `0xff`, then deterministic pseudo-random whole-state assignments controlled by `--cv-model-random-candidates`. The current default is `1` deterministic pseudo-random whole-state candidate.

The optimization is a witness-finding shortcut, not a replacement for relational solving. If the cheap candidates fail, KLEE-CF falls back to the solver for the same stage.

## Fork And Path Handling

KLEE-CF's normal execution still forks through KLEE's `Executor::fork` machinery. With `--use-cv-model`, fork handling first evaluates the branch under the current concrete model to identify one feasible side cheaply. It then tries candidate assignments, and finally the solver, to discover the opposite side.

If both sides are found, KLEE-CF forks. If only the current-model side can be supported under the configured limits, it continues that side and records the skipped side through `DeferredForks` and `InhibitedForks`. This approximates model-guided progress; it is not yet a real deferred-work queue.

Selective concretization is related but distinct. It handles solver timeouts by fixing public inputs to model values so execution can continue through expensive public-input arithmetic. The concrete-model path is more local: it tries to answer branch and CT witness questions with concrete assignments before escalating.

## What It Reports

The KLEE-family converter normalizes KLEE output into the shared JSON schema. KLEE-CF can emit branch and memory findings through that flow.

Important outputs include:

- source filename, line, and column
- finding kind
- visit and non-CT counts when present
- replay-linked artifacts through the benchmark replay executable

## How To Run It

Canonical entrypoint:

```bash
python -m scripts.experiments.run_klee_cf 1m --sym-size 4 --benchmarks bearssl:default
```

The runner uses `python -m ...` entrypoints from the repository root and accepts benchmark selectors in `library:variant` form.

## Runner Model

KLEE-CF shares the common runner implementation in `scripts/experiments/run_klee_family.py`.

That shared implementation handles:

- benchmark-local workspace isolation
- bitcode selection
- common KLEE flags such as libc mode, kdalloc settings, solver backend, searchers, batching, istats write intervals, and output capture
- conversion through `tools.converters.klee_log_to_json`
- replay of positives after conversion

KLEE-CF's mode-specific runner flag is `--use-cv-model`.

## Important Option Surface

- `--use-cv-model=true|false`: enable or disable the concrete-model optimization path
- `--cv-model-random-candidates=N`: number of deterministic pseudo-random whole-state candidates tried after the current-model probe and the fixed `1` and `-1` assignments; default `1`
- `--use-batching-search=true|false`: enable or disable KLEE batching in the shared runner; default `true`
- `--batch-instructions=N`: batching instruction budget used when batching is enabled; default `1000`
- `--batch-time=T`: batching time budget used when batching is enabled; default `0s`, which leaves the instruction budget as the active batching limit
- `--optimize-concrete-object-state-reads=true|false`: enable or disable the direct read path for fully concrete `ObjectState` byte ranges; default `true`
- `--istats-write-interval=T`: control how often KLEE writes `run.istats`; default `0s`, which keeps only the shutdown write
- `--solver-backend=...`: choose the KLEE solver backend
- `--search=...`: set one or more KLEE search strategies
- `--loop-max-iterations=...`: control loop-limiter preprocessing when configured by the benchmark

The repository runner keeps the option surface intentionally narrow. Detailed tool semantics belong in the tool implementation and supporting notes, not in duplicated wrapper logic.

## Implementation Notes

The main implementation anchors are:

- `klee-cf/lib/Core/Executor.cpp`: symbolic input creation, `renameSecret`, relational witness checks, concrete-model repair, and fork handling;
- `klee-cf/lib/Core/Executor.h`: the prime map and rename caches;
- `klee-cf/lib/Core/Memory.cpp`: the concrete `ObjectState::read` fast path controlled by `--optimize-concrete-object-state-reads`;
- `../notes/klee-cf-candidate-models.md`: concrete-model and chosen-value details.

These implementation files define the exact recursion, cache behavior, and witness-search order documented above.

## Known Strengths

- Fits naturally into the shared benchmark and replay pipeline.
- Can report findings that are easy to witness concretely even when full solver-backed progress is expensive.
- Shares one orchestration path with KLEE-Eager and KLEE-Self-Comp, which keeps comparisons fairer and runner behavior easier to audit.

## Known Limits

- Detailed behavior depends on the modified `klee-cf/` tree, not just the thin runner wrapper.
- The concrete-model fork path counts skipped opposite sides but does not maintain a deferred exploration queue.
- The product-program check is implemented inside modified KLEE executor logic, so changes to symbolic object creation, constraint addition, or expression representation can affect CT semantics.

## Examples To Start With

- `../../examples/cf_symbolic_mod_chain_branch.c`
- `../../examples/cf_favored_branch_maze_cross_tool.c`

For the current concrete paths, see `../notes/klee-cf-candidate-models.md` and `../../examples/README.md`.