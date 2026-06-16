# KLEE-CF candidate models and chosen-value checks

This change adds a lightweight, state-local concrete model controlled by `--use-cv-model` and uses it in two places where KLEE-CF previously paid for hard solver queries before it could report or continue:

- chosen-value CT checking tries BINSEC-style concrete witnesses before falling back to solver-backed relational queries.
- model-directed fork uses the current state model before branch feasibility asks the solver, then probes the opposite side with concrete candidates before falling back to the solver for that same opposite-side request.

The intent is not to replace solver-backed checking. These options provide a fast witness path for bugs that are easy to demonstrate concretely but expensive to prove symbolically.

## Rationale

The motivating minimal example is `examples/cf_symbolic_mod_chain_branch.c`. With `MOD_ROUNDS=2`, the program builds a symbolic modular chain and then branches on the final low bit. The baseline KLEE-CF run timed out in the non-CT branch query and then timed out again in `fork()`, so it produced no non-CT report and ended with one partially completed path.

On the same toy, BINSEC with only its CV optimization enabled reported the first control-flow leak quickly. The reason is that the leak has a cheap concrete witness: keep public inputs fixed, assign two simple secret values, and compare the resulting branch condition values. The relational SMT query over the full symbolic modulo expression is much harder than this witness search.

The earlier branch-maze toy, `examples/cf_favored_branch_maze_cross_tool.c`, shows the same shape from another angle. BINSEC's model-directed path exploration can reach a first non-CT point quickly when its current concrete model follows the relevant branch. KLEE-CF was stricter at fork points: if feasibility timed out, the state could stop before the CT check became useful.

Two simpler experiments were useful negative controls. A direct symbolic division toy was too easy for KLEE-CF, and a hand-written long-division toy mostly created path explosion rather than the specific hard solver timeout pattern. The symbolic modular-chain toy is the cleaner reproducer for this optimization.

## Implementation

Each `ExecutionState` now carries an `Assignment concreteModel`. New symbolic arrays are initialized to zero bytes in the model, and secret arrays also initialize zero-valued prime-secret bindings because KLEE-CF stores renamed CT path constraints in the same state constraint set. The model is copied with the state. After path constraints are added, KLEE-CF tries to repair the model with deterministic candidate assignments and then with `getInitialValues`.

When `--use-cv-model=true`, the implementation treats this as an invariant: every live state must have a concrete model that satisfies its current path constraints, including renamed prime-secret path constraints. If KLEE-CF adds a constraint and cannot repair the model, it stops with an error instead of continuing with a stale model. Fork-time model checks can therefore use the model directly rather than revalidating it before every use.

The candidate set is explicit in the implementation. For code paths that enable candidate search, KLEE-CF tries candidates in this order:

- the state's current concrete model;
- scalar `0`, encoded as all-zero object bytes;
- scalar `1`, encoded as little-endian object bytes `{0x01, 0x00, ...}`;
- scalar `-1`, encoded as all-`0xff` object bytes;
- a whole-state byte pattern of `0x55`;
- a whole-state byte pattern of `0xaa`;
- `--cv-model-random-candidates=N` deterministic pseudo-random whole-state assignments, defaulting to 10.

For CT checking, `--use-cv-model` starts with the fixed current public/current secret1 fallback level. At that level it first tries chosen alternate secret2 values for the renamed side, then asks the solver for secret2 if the candidates fail. If both expressions become constants and differ, KLEE-CF reports the non-CT issue immediately.

For branch handling, `--use-cv-model` runs before the normal fork query. KLEE-CF evaluates the branch condition under the current model. That model gives one side. KLEE-CF then tries the fixed and deterministic random candidates for the opposite side before asking the solver for an opposite-side model. If an opposite side is found, KLEE-CF forks. If no opposite side is found, KLEE-CF continues the current-model side and counts the opposite side with `DeferredForks` and `InhibitedForks`.

## Counterexample checks, from cheapest to most expensive

For non-CT branch and memory checks, KLEE-CF now runs a clear escalation ladder inside `getCounterexample()`. The stages are intentionally ordered by expected cost.

1. Fixed current public/current secret1, candidate or solver-chosen secret2.

KLEE-CF fixes all original-side objects to the current model. It first tries chosen alternate values for the prime secret arrays. If no candidate makes the renamed expression differ from the fixed original expression, KLEE-CF adds `cond != renamedCond` and asks the solver only for prime secret values. The fixed/random candidate list is the cheap probe immediately before this solver call, not a separate fallback stage.

2. Fixed current public, candidate or solver-chosen secret1 and secret2.

If fixing the original secret is too restrictive, KLEE-CF keeps only public objects fixed to the current model. Before invoking the solver, it tries fixed/random candidates for original secrets and, for each of those, fixed/random candidates for prime secrets. If those probes fail, it asks the solver for both secret sides under the fixed-public constraints plus `cond != renamedCond`.

3. Symbolic public, candidate or solver-chosen public, secret1, and secret2.

As the most general fallback, KLEE-CF leaves public inputs symbolic too. It first tries fixed/random candidates for original public and secret values paired with fixed/random prime-secret candidates. If those probes fail, it adds `cond != renamedCond` under the path constraints and asks the solver for every original symbolic object and every prime secret object.

This ordering matters because the fixed/random candidates are used as cheap probes just before each increasingly expensive solver query. They are not an independent proof stage. The solver fallback grows from only alternate secrets, to both secret sides, to full public-and-secret divergence.

## CLI options

`--use-cv-model=true|false`

This single option controls the whole concrete-model optimization and defaults to `true`. When enabled, KLEE-CF maintains `state.concreteModel`, uses chosen-value CT witnesses, and uses model-directed fork handling.

`--cv-model-random-candidates=N`

This option controls how many deterministic pseudo-random assignments are tried after the fixed candidate values. It defaults to `10`. Setting it to `0` keeps only the fixed `0`, `1`, `-1`, `0x55`, and `0xaa` candidates.

After a new constraint is added, KLEE-CF checks whether the existing `concreteModel` still satisfies the state's path constraints. If not, it tries to repair that model first with the explicit candidate list above and then, only if those candidates fail, with `solver->getInitialValues(...)`.

For CT checks, the option adds chosen-value probes before each solver fallback level. The first probe keeps current public values and current original secrets fixed while substituting alternate values only for prime secret arrays. Later probes relax that fixed context: first allowing chosen original-secret values with public values still fixed, then allowing chosen public and original-secret values in the symbolic-public stage.

This is a witness-finding optimization, not a proof optimization. If no concrete witness is found, KLEE-CF still falls back to a solver query for the same stage.

For forks outside seed and replay modes, the option changes normal `fork()` handling. KLEE-CF first evaluates the branch under the current concrete model. It then tries the explicit candidate list for the opposite branch value before falling back to a solver query for that opposite side. If both sides have models, KLEE-CF creates both states. If only the current-model side is feasible or the opposite-side solver request fails, KLEE-CF continues that side and records the other side as deferred.

Each local candidate probe uses the same fixed order: scalar `0`, scalar `1`, scalar `-1`, `0x55`, `0xaa`, then the configured deterministic pseudo-random assignments. Fork handling additionally tries the current model before that explicit candidate list because it needs a concrete branch side to continue.

The optimization is enabled by default:

```sh
klee program.bc
```

Disable it for a solver-first baseline:

```sh
klee --use-cv-model=false program.bc
```

## Stats

`CandidateModelQueries`

This counts how many local yes/no assignment queries were routed through `findCandidateAssignment()`. It is the denominator for interpreting `CandidateModelHits`.

`CandidateModelHits`

This counts how many times one of the explicit concrete candidates was enough to answer a local yes/no question without making the corresponding solver query. In the current implementation that includes:

- CT witness discovery in the chosen-value probes inside `getCounterexample()`;
- opposite-side discovery in the model-directed fork path;
- model repair when a candidate assignment already satisfies the updated path constraints.

The name does not mean every hit avoided all solver activity for the entire state. It means that a specific local decision was settled by an explicit candidate instead of a fresh solver call for that decision.

`DeferredForks`

This counts branch alternatives that were not explored because model-directed fork continued only the current-model side. Right now that is closer to "skipped opposite side" than to a real deferred-work queue.

`InhibitedForks`

This is an existing upstream KLEE stat. It counts any case where KLEE chose not to split a fork, including upstream fork-inhibition paths such as fork limits. `DeferredForks` is narrower: it counts only the new model-directed case where KLEE-CF skipped the opposite side after candidate probing. Every `DeferredForks` increment also increments `InhibitedForks`, but not every `InhibitedForks` increment is a `DeferredForks` increment.

## Validation result

The latest focused validation was run on 2026-06-14. Raw commands and logs are under `results/cv-model-validation-20260614/`. KLEE-CF used `--solver-backend=stp`, `--max-solver-time=1s`, DFS search, and a 20 second outer timeout. BINSEC used `-fml-solver z3`, `-smt-solver z3`, one second formula/SMT timeouts, `-sse-timeout 20`, `-sse-heuristics nurs`, and `-checkct-no-cv` for the CV-off runs. The BINSEC configs replace `klee_make_symbolic_sc` and mark the passed memory range as secret, so both global and stack-local toy inputs are handled consistently.

| Example | Tool/options | First non-CT report | Final status | Notes |
| --- | --- | ---: | --- | --- |
| `cf_symbolic_mod_chain_branch.c` with `-DMOD_ROUNDS=2` | KLEE-CF `--use-cv-model=false` | none | exit 1 at 2.15s | CT validity and fork feasibility timed out. |
| `cf_symbolic_mod_chain_branch.c` with `-DMOD_ROUNDS=2` | KLEE-CF `--use-cv-model=true` | 0.073390s, line 36 | exit 0 at 2.10s | Reports the leak, then later test generation loses one hard test case after an STP timeout. |
| `cf_symbolic_mod_chain_branch.c` with `-DMOD_ROUNDS=2` | BINSEC CV off | 0.050s, `0x401219` | insecure at 1.061s | With the hook-based config, BINSEC finds this toy in both CV modes. |
| `cf_symbolic_mod_chain_branch.c` with `-DMOD_ROUNDS=2` | BINSEC CV on | 0.051s, `0x401219` | insecure at 1.062s | Same result as CV off for this run. |
| `cf_favored_branch_maze_cross_tool.c` | KLEE-CF `--use-cv-model=false` | none | exit 0 at 2.43s | Solver-first CT check times out, then the assertion path is still reached. |
| `cf_favored_branch_maze_cross_tool.c` | KLEE-CF `--use-cv-model=true` | 0.006930s, line 37 | exit 0 at 2.62s | Chosen-value CT check reports before the assertion. |
| `cf_favored_branch_maze_cross_tool.c` | BINSEC CV off | none | unknown at 2.081s | Exploration remains incomplete under the one second solver timeout. |
| `cf_favored_branch_maze_cross_tool.c` | BINSEC CV on | 0.061s, `0x4011f6` | insecure at 1.071s | CV sampling finds the control-flow leak quickly. |

This matrix confirms the intended KLEE-CF behavior on the two focused examples: enabling the concrete-model path produces the early CT report that the solver-first KLEE-CF run misses under the same timeout.

## Comparison with BINSEC CV

BINSEC's CV optimization uses the current path model for public values and compares the original expression with mirrored secret values drawn from simple patterns such as zeros, ones, fill bytes, and random values. It is a concrete witness search, not a proof that the program is constant-time.

The KLEE-CF implementation follows that same idea for the cheapest CT reports: keep the current public and original-secret model concrete, vary the renamed secret side, and report when the two concrete expression values differ. It then escalates by relaxing the fixed context before falling back to solver-backed relational queries. The main difference is that KLEE-CF also needs a state-local model and model-first fork handling, because the original failure mode on the modular-chain toy happened both in the CT query and later in `fork()`.

BINSEC can also continue along model-supported paths while leaving other feasibility questions unresolved. The current KLEE-CF fork path approximates this by continuing the model-supported side and counting the other side as deferred when candidate and solver probing do not find an opposite-side model, but it does not yet keep a deferred worklist.

## Further improvements

- Keep a real deferred-fork worklist instead of dropping the opposite side when local opposite-side probing cannot find a model.
- Add byte-local and constraint-directed model repair before falling back to solver-generated initial values.
- Use the counterexample cache as an additional source of candidate assignments.
- Add richer CT tiers: current public/current secret, current public/alternate secret, solver-generated alternate secret, and finally the existing relational query.
- Expose clearer stats for CV hits and deferred fork outcomes in user-facing summaries.
- Add an explicit proof mode that disables chosen-value reporting and model-directed fork recovery for users who want only solver-backed completeness semantics.