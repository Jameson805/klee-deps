LoopLimiter
====================

Overview
--------
LoopLimiter is an LLVM function pass that instruments loops to limit the number of iterations explored by KLEE. When a loop exceeds a configured iteration bound the pass inserts a call to klee_silent_exit(1) (or branches to an after-loop target when possible) to terminate that execution path.

It effectively does the following:
```c
int loop_counter = 0;
while (condition) {
  if (loop_counter >= MAX_ITERATIONS)
    klee_silent_exit(1); // or branch out of loop when using --break

  // loop body

  loop_counter++;
}
```

What the pass actually does in IR terms
--------------------------------------
- Create an alloca for the counter in the function entry block (so it is visible to all blocks).
- Insert a store 0 into the counter at the loop preheader (so the counter resets on loop entry).
- Split the loop header so PHI nodes remain in the header and the body starts in a new block.
- Create an ExitBB that either calls klee_silent_exit(1) and then unreachable, or (when using --break and a valid after-loop target exists) branches to that after-loop target.
- Replace the header terminator with a conditional branch:
  - if counter >= MaxIterations -> ExitBB (or branch to after-loop target)
  - else -> loop body
- Insert a counter increment (load/add/store) in each loop latch immediately before the back-edge is taken.

Limitations and behavior
------------------------
- The pass instruments only loops that have:
  - a canonical single preheader, and
  - a header block (loops without a header or preheader are skipped and a warning is emitted).
- Multiple latches (multiple back-edges) are supported: the pass will increment the counter in every latch.
- The check uses >= MaxIterations before executing the body. That means when MaxIterations == N the body will not run for the (N+1)-th iteration; adjust logic if you prefer different semantics (e.g., check after increment to allow exactly N iterations).
- Break mode (--break): when enabled, the pass will try to select a sensible after-loop target so that, instead of calling klee_silent_exit, it branches to code after the loop. The selection strategy:
  1) Prefer the loop's unique exit block.
  2) Otherwise, use the nearest common post-dominator of all exit blocks (if that block is not inside the loop).
  3) If no suitable after-loop target can be found, the pass falls back to inserting klee_silent_exit and emits a warning.
  Note: After-loop target selection is performed before changing the CFG, so the chosen target is valid for the branching inserted into the newly-created ExitBB.
- PHI nodes and splitBasicBlock handling: the pass splits the header after PHIs; the pass rewires control flow appropriately but complex transforms in the function may require re-running analyses.
- Nested loops: each instrumented loop gets its own counter name (loop.counter.<id>), so nested loops have separate counters.

Statistics
----------
When the plugin is unloaded / the process exits, LoopLimiter prints basic statistics to errs():
- total loops found
- loops instrumented
- loops excluded due to whitelist/blacklist

Build
-----
From the loop-limiter directory:
```bash
mkdir build && cd build
cmake ..
make
```

Usage
-----
1. Compile the input C file to LLVM bitcode:
   clang -O0 -g -emit-llvm -c input.c -o input.bc

2. Run the pass via opt. The --max-iterations option is required.

Example (simple instrumentation, always call klee_silent_exit on bound):
```bash
opt \
  -load ./build/libLoopLimiter.so \
  -load-pass-plugin=./build/libLoopLimiter.so \
  -passes='loop-simplify,loop-limiter' \
  -max-iterations=5 \
  input.bc -o input_instrumented.bc
```

Example (use break mode on loops that can be canonicalized by loop-simplify):
```bash
opt \
  -load ./build/libLoopLimiter.so \
  -load-pass-plugin=./build/libLoopLimiter.so \
  -passes='loop-simplify,loop-limiter' \
  -max-iterations=5 \
  -break \
  input.bc -o input_instrumented.bc
```

Filtering functions
-------------------
- --whitelist: comma-separated list of function names to instrument (empty = all). If provided, only functions listed are instrumented.
- --blacklist: comma-separated list of function names to skip instrumenting. If provided, all functions except those listed are instrumented.
- Note: --whitelist and --blacklist are mutually exclusive; using both will cause the pass to fail.

3. Inspect the instrumented IR:
   llvm-dis-13 input_instrumented.bc

4. Run KLEE on instrumented bitcode as you normally would. When a loop reaches the configured maximum the pass will either use the loop's existing canonical exit edge (`--break`) or insert `klee_silent_exit(1)`.

Tips
--------------
- Change MaxIterations with the `-max-iterations` command-line option passed to opt (this option is required).
- Target specific function(s) with `--whitelist` or skip specific functions with `--blacklist`. These two options cannot be used together.
- Use `--break` only with `loop-simplify`. The current implementation conservatively rewrites only loops whose header has a conditional branch with exactly one in-loop successor and one out-of-loop successor. Other loops emit a warning and fall back to `klee_silent_exit`.
- If a loop is skipped you'll see a warning printed to errs() identifying the function and the reason.
- If you need to support more complex loops (loops without preheaders, or irreducible loops) you must:
  - canonicalize loops (e.g., run passes that create preheaders),
  - or add more complex instrumentation that handles those cases safely.
- If you want different semantics (e.g., check after increment), move the conditional or change the comparison operator accordingly.

Note
--------------------
Based on [llvm-pass-skeleton](https://github.com/sampsyo/llvm-pass-skeleton/tree/8aabfc8ce4f6bcebb16cf53328baeb0f5f889ba4)