LoopLimiter
====================

Overview
--------
LoopLimiter is an LLVM function pass that instruments loops to limit the number of iterations explored by KLEE. When a loop exceeds a configured iteration bound the pass inserts a call to klee_silent_exit(1) to terminate that execution path.

It effectively does the following:
```c
int loop_counter = 0;
while (condition) {
  if (loop_counter >= MAX_ITERATIONS)
    klee_silent_exit(1);

  // loop body

  loop_counter++;
}
```

What the pass actually does in IR terms
--------------------------------------
- Create an alloca for the counter in the function entry block (so it is visible to all blocks).
- Insert a store 0 into the counter at the loop preheader (so the counter resets on loop entry).
- Split the loop header so PHI nodes remain in the header and the body starts in a new block.
- Create an ExitBB that calls klee_silent_exit(1) and then unreachable.
- Replace the header terminator with a conditional branch:
  - if counter >= MaxIterations -> ExitBB
  - else -> loop body
- Insert a counter increment (load/add/store) in the loop latch immediately before the back-edge is taken.

Limitations and behavior
------------------------
- The pass instruments only loops that have:
  - a canonical single preheader, and
  - a single latch (single back-edge).
  Loops missing these (no preheader, multiple latches/back-edges, irreducible loops) are skipped and a warning is emitted.
- The check uses >= MaxIterations before executing the body. That means when MaxIterations==N the body will not run for the (N+1)-th iteration; adjust logic if you prefer different semantics (e.g., allow exactly N iterations).
- PHI nodes and splitBasicBlock handling: the pass splits the header after PHIs; the pass rewires control flow appropriately but complex transforms in the function may require re-running analyses.
- Nested loops: each instrumented loop gets its own counter name (loop.counter.<id>), so nested loops have separate counters.

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

2. Run the pass via opt (example in run_test.sh). Example:
```bash
opt \
  -load ./build/libLoopLimiter.so \
  -load-pass-plugin=./build/libLoopLimiter.so \
  -passes=loop-limiter \
  -max-iterations=5 \
  input.bc -o input_instrumented.bc
```

3. Inspect the instrumented IR:
   llvm-dis-13 input_instrumented.bc

4. Run KLEE on instrumented bitcode as you normally would. When a loop reaches the configured maximum the pass will have inserted a klee_silent_exit(1) so KLEE will end that path.

Tips
--------------
- Change MaxIterations with the -max-iterations command-line option passed to opt (as shown above).
- If a loop is skipped you'll see a warning printed to errs() identifying the function and the reason.
- If you need to support more complex loops (multiple latches, loops without preheaders, or irreducible loops) you must:
  - canonicalize loops (e.g., run passes that create preheaders),
  - or add more complex instrumentation that handles multiple back-edges and safe insertion points.
- If you want different semantics (e.g., check after increment), move the conditional or change the comparison operator accordingly.

Note
--------------------
Based on [llvm-pass-skeleton](https://github.com/sampsyo/llvm-pass-skeleton/tree/8aabfc8ce4f6bcebb16cf53328baeb0f5f889ba4)