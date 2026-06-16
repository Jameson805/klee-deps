# Expr Compare Findings

This note summarizes the profiling work on the toy ARC4-like reproducer in `klee-self-comp` and the comparison run against `klee-cf`.

## Profiling Workflow Used

The analysis in this document was built from three profiling layers on the same toy workload:

1. Runtime compare counters emitted by instrumented `Expr::compare` paths.
2. Per-callsite scoped attribution around higher-level code paths.
3. Callgrind instruction profiling for hotspot confirmation.

The toy workload source is `examples/toy_selfcomp_arc4_like.c` in this workspace.

### Build + Run Pattern

The run pattern was intentionally consistent across iterations:

- build `klee-self-comp`
- compile the toy file to bitcode with clang-16
- run KLEE with deterministic allocator slices
- stop with a timed interrupt to force profile emission

Representative command shape:

```bash
cd /dkucc/home/yl925/klee-deps-self-comp-trace-overhead && source ./activate-workspace.sh
OUT=/tmp/klee_selfcomp_profile_taggedX
clang-16 /dkucc/home/yl925/klee-deps-new/examples/toy_selfcomp_arc4_like.c -g -emit-llvm -O0 -Xclang -disable-O0-optnone -c -I klee-self-comp/include -o "$OUT/toy.bc"
timeout --foreground --signal=INT --kill-after=30s 10s build/klee-self-comp/bin/klee --output-dir="$OUT/klee-out" --kdalloc --kdalloc-constants-size=1 --kdalloc-globals-size=1 --kdalloc-heap-size=1 --kdalloc-stack-size=1 --write-no-tests --max-time=3900s "$OUT/toy.bc" >"$OUT/klee.log" 2>&1
grep -nE '^KLEE: expr-compare profile|^KLEE:   |^KLEE:     ' "$OUT/klee.log"
```

### Callgrind Confirmation

Callgrind was used to verify that counter hotspots matched instruction-level hotspots:

```bash
cd /dkucc/home/yl925/klee-deps-self-comp-trace-overhead && source ./activate-workspace.sh
OUT=/tmp/klee_selfcomp_callgrind
clang-16 /dkucc/home/yl925/klee-deps-new/examples/toy_selfcomp_arc4_like.c -g -emit-llvm -O0 -Xclang -disable-O0-optnone -c -I klee-self-comp/include -o "$OUT/toy.bc"
timeout --foreground --signal=INT --kill-after=30s 10s valgrind --tool=callgrind --trace-children=no --callgrind-out-file="$OUT/callgrind.out" build/klee-self-comp/bin/klee --output-dir="$OUT/klee-out" --kdalloc --kdalloc-constants-size=1 --kdalloc-globals-size=1 --kdalloc-heap-size=1 --kdalloc-stack-size=1 --write-no-tests --max-time=3900s "$OUT/toy.bc" >"$OUT/klee.log" 2>&1
callgrind_annotate --auto=yes "$OUT/callgrind.out"
```

### Attribution Evolution

The callsite tagging proceeded in rounds:

1. initial tags: `renameSecret`, canonicalization
2. solver cache tags: cex key/search/getAssignment + cache map paths
3. constraint tags: simplify/rewrite/add internal
4. independent-solver factoring tags

This progressively reduced the `unknown` bucket from dominant to tiny.

## Main Result

Expression comparison is a major cost center in `klee-self-comp`.

On the toy reproducer, the hottest work is concentrated in `Expr::compare` and its memoization machinery, especially the pair lookup and insert paths over the expression equivalence set. The same pattern appears in `klee-cf`, but `klee-self-comp` does substantially more of it.

## What The Callsite Tagging Showed

The first round of tags showed that the obvious high-level paths were only a small part of the work:

- `renameSecret` was real, but small.
- solver query canonicalization was tiny.
- `ExecutionState::merge` and switch-expression ordering did not show up on this toy run.

The remaining untagged traffic was then split further. That revealed that most of the remaining compare activity was not coming from one single caller, but from solver-side cache and constraint-processing paths:

- counterexample cache lookup key construction
- counterexample cache search and assignment lookup
- constraint simplification
- independent-solver factorization

After those tags were added, the `unknown` bucket became very small, which meant the main higher-level sources had been identified.

## Why `klee-self-comp` Calls Expr Compare More Often

The extra compare work is not just one function calling `Expr::compare` more often. It comes from the fact that self-composition forces KLEE to manage more symbolic structure and more canonicalization work around the same program.

In this reproducer, `klee-self-comp` spends more time in compare-heavy logic because it repeatedly:

- builds and normalizes solver queries,
- constructs and reuses counterexample-cache keys,
- rewrites and simplifies constraints,
- factors expressions for independence,
- and orders expressions inside maps and sets.

Those are all places where `ref<Expr>` is used as an ordered or hashed key, so structural comparison and memoization become hot.

In practice, the self-comp path is doing more compare work because it has more solver/cache bookkeeping around the same semantic query flow, not because `renameSecret` itself is the dominant caller.

## Measured Takeaway

The final picture from the toy run is:

- `constraintSimplifyExpr` is the largest named high-level caller.
- `cexCacheGetAssignment`, `cexCacheLookupKey`, and `cexCacheSearch` are the next biggest solver-side buckets.
- `renameSecret` is secondary.
- the residual `unknown` bucket is now tiny.

In the final tagged run, `unknown` was approximately 0.24% of top-level compare calls, so most high-level callsites were successfully identified.

That makes the next optimization targets much clearer: reduce compare churn in constraint simplification and counterexample-cache handling before spending effort on the rename path.

## Next Optimization Targets

If we keep going, the most promising places to look are:

1. constraint simplification and equality rewriting in `klee-self-comp/lib/Expr/Constraints.cpp`
2. counterexample cache key construction and lookup in `klee-self-comp/lib/Solver/CexCachingSolver.cpp`
3. solver-side factoring in `klee-self-comp/lib/Solver/IndependentSolver.cpp`

Those are the paths most likely to shrink the remaining compare hot spots in a way that matters for `klee-self-comp`.
