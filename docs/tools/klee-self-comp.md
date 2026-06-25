# KLEE-Self-Comp

KLEE-Self-Comp is the repository's self-composition-oriented KLEE variant.

## What It Is

The CLI wrapper in `scripts/experiments/run_klee_self_comp.py` is intentionally thin and dispatches into the shared implementation in `scripts/experiments/run_klee_family.py`.

This means KLEE-Self-Comp shares the same benchmark-local build, execution, conversion, and replay shape as KLEE-CF and KLEE-Eager.

## Design Model

KLEE-Self-Comp implements self-composition inside KLEE's executor. It reasons about two executions of the same program with shared public inputs and different secret inputs. An observation is a branch decision or a memory address used by a load or store. A finding is a pair of executions whose observations are equal up to some index and differ at that index.

The implementation is not a syntactic transformation that duplicates the LLVM bitcode into two sequential program copies. It executes ordinary KLEE paths, records observable traces, renames completed traces over primed secrets, and compares completed traces for localized divergences.

Public symbolic objects are shared between the two executions. Secret symbolic objects have primed `__prime` counterparts. During normal execution, KLEE explores paths using original symbols and records observable events. When a path completes, the completed trace can be compared with a primed version of itself and with primed versions of earlier completed traces.

This differs from KLEE-CF and KLEE-Eager in timing:

- KLEE-CF checks relational divergence on the fly at the current observation;
- KLEE-Eager propagates paired `Dual` values during execution and checks them at observations;
- KLEE-Self-Comp delays relational comparison until traces have completed.

That delayed comparison is why self-composition is simpler conceptually but more expensive in practice: it must retain traces and compare aligned observations across completed paths.

For notation used below, let:

- `i` and `j` be two completed traces;
- `k` be the event index being checked;
- `pi_i^{<k}` be the constraints needed for trace `i` to reach event `k`;
- `pi_j^{<k}` be the constraints needed for trace `j` to reach event `k`;
- `PRIME(e)` be expression or constraint `e` with every secret array renamed to its `__prime` array;
- `omega_i[h]` be the observed value at event index `h` in trace `i`;
- `omega'_j[h]` be the observed value at event index `h` in the primed version of trace `j`;
- `v` and `v'` be the two observed values at the current event `k`.

The localized witness query has this shape:

\[
    \pi_i^{<k}
    \land \operatorname{PRIME}(\pi_j^{<k})
    \land \bigwedge_{h < k}(\omega_i[h] = \omega'_j[h])
    \land v \ne v'.
\]

The prefix equalities require the two executions to be indistinguishable before event `k`. The final inequality requires the current event to be the first differing observation.

## Observable Trace Recording

Each `ExecutionState` carries `selfCompTrace`, a vector of observable events. The trace is copied when states fork, so a completed state keeps the exact observation sequence that led to its terminal path.

The current implementation records:

- branch events, with the branch instruction id and the raw symbolic condition;
- memory load events, with the load site and symbolic address;
- memory store events, with the store site and symbolic address.

The code intentionally records the raw branch condition rather than `taken ? condition : !condition`. This matters because later relational comparison checks equality or inequality of observed values under path-prefix constraints. Recording only the path-specific taken expression can make branch divergence tautological and can produce false witnesses on public-only branches.

Each event stores a `prefixConstraintIndex`. Rather than materializing a full path condition for every observation, KLEE-Self-Comp stores the completed path's `ConstraintSet` once and lets each event point to the constraint prefix that was active when the event was recorded.

## Secret Renaming Over Completed Data

KLEE-Self-Comp uses the same corrected renaming shape as the product-program variants. `renameSecret(expr)` replaces secret array reads with primed reads, traverses read indices and update-list indices and values, and rebuilds ordinary expression children when they contain renamed secrets. The traversal is iterative and cached so large completed traces do not overflow the native stack while being prepared for relational queries.

It also provides overloads for full constraint sets and completed traces:

- `renameSecret(ConstraintSet)` renames each path constraint;
- `renameSecret(CompletedTrace)` renames every recorded event value and the trace's path constraints.

The self-comp implementation uses executor-wide rename caches, cleared when new primed secret arrays are created, so repeated comparisons against completed traces can reuse previous renaming results.

## Completed Trace Comparison

When a state completes, KLEE-Self-Comp compares completed traces through `findDivergences`. The comparison walks two event sequences by index and maintains one accumulated relational prefix constraint set.

Before comparing events, the solver query includes a secret-inequality guard from `buildSecretInequality`. This requires at least one original secret byte to differ from its primed counterpart, preventing equal-secret witnesses.

For each aligned event index, the implementation:

1. appends the left and right path-constraint slices needed to reach that event;
2. checks that the accumulated prefix is feasible;
3. treats different event kinds, different sites, or length mismatch as unlocalizable divergence cases;
4. checks whether the current observed values can differ under the matched prefix;
5. records a branch or memory side-channel when the difference is feasible;
6. adds equality of the current observed values before advancing, so later reports preserve the first-difference criterion.

This is the code-level completed-trace self-composition check: earlier observations must be equal, then the current branch decision or memory address may differ.

## Counterexample Emission

Localized divergences are logged through `logSelfCompDivergence`. The implementation emits at most one finding per divergence kind and instruction site, keeping output aligned with the shared KLEE-family reporting contract.

For a localized branch or memory divergence, `getSelfCompCounterexampleSolution` solves the stored witness constraints directly over both original symbolic arrays and primed secret arrays. This is important because ordinary KLEE test generation only serializes `state.symbolics`; self-composition counterexamples need both `<name>` and `<name>__prime` assignments.

The shared converter normalizes these `non_ct` records. The current repository runner documentation previously described branch findings as the main supported path, but the current executor code can log both localized branch and localized memory side-channels. Whether a benchmark flow surfaces both kinds depends on the generated records and converter support.

## Analysis Model In This Repository

The shared runner treats KLEE-Self-Comp as another KLEE-family mode with a distinct executable artifact. The conversion path in `tools.converters.klee_log_to_json` explicitly supports the `non_ct` records emitted by `klee_self_comp` so the repository can normalize all three KLEE variants through one JSON schema path.

## How To Run It

Canonical entrypoint:

```bash
python -m scripts.experiments.run_klee_self_comp 1m --sym-size 4 --benchmarks bearssl:modexp
```

## Runner Model

The shared KLEE-family runner handles:

- benchmark-local workspace isolation
- bitcode and replay artifact selection
- common KLEE flags such as libc mode, kdalloc settings, solver backend, and output capture
- conversion through `tools.converters.klee_log_to_json`
- replay of positives through the benchmark replay executable

KLEE-Self-Comp does not currently add a dedicated runner-level flag analogous to KLEE-CF's `--use-cv-model` or KLEE-Eager's `--product-program-fallback`.

## Freestanding Runtime Support

KLEE-Self-Comp now loads the same focused freestanding `RuntimeExplicitBzero` archive as the other KLEE variants. The archive provides `explicit_bzero` as symbolic byte-zeroing runtime support, so secure-wipe code stays inside KLEE instead of falling back to the expensive external-call path that would concretize symbolic buffers.

## Performance And Profiling Notes

The current focused repository note for self-composition is `../notes/expr-compare-findings.md`.

That note shows a concrete pattern that matters for this tool variant in this repository:

- `Expr::compare` activity is a major cost center
- compare-heavy work shows up in constraint simplification, counterexample-cache handling, and solver-side factoring
- the self-composition path does substantially more compare-heavy bookkeeping than KLEE-CF on the toy profiling workload

That note is not a replacement for a tool overview, but it is the most concrete current implementation writeup.

The design explains the profiling result: self-composition performs more solver/cache and expression-ordering work because it stores, renames, and compares completed traces under accumulated prefix constraints. The profiling note found `renameSecret` to be real but secondary; constraint simplification and counterexample-cache paths are larger costs on the toy workload.

## Known Limits

- The delayed comparison model can require many completed traces before it reports what KLEE-CF may find on the fly.
- Trace pairing creates solver/cache pressure around constraint simplification and counterexample-cache handling.
- Unlocalizable length, kind, site, and prefix-infeasible mismatches are intentionally not emitted as normal non-CT findings.
- Some profiling helpers still need cleanup as the examples tree is reorganized.

## Examples To Start With

- the ARC4-like toy and profiling helper tracked from `../notes/expr-compare-findings.md`
- additional toy programs in `../../examples/README.md`