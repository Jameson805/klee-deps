/*
 * Small standalone reproducer for the KLEE missing-!dbg verifier crash.
 *
 * This is the original standalone kernel that reproduced the problem when
 * built to LLVM bitcode with optimization enabled.
 *
 * From the workspace root, run:
 *   source ./activate-workspace.sh
 *   export LLVM_COMPILER=clang
 *   export LLVM_COMPILER_PATH=$(dirname "$(command -v clang-16)")
 *   wllvm -g -O2 -fno-pie -fno-plt -Wl,-no-pie \
 *     examples/min_missing_dbg_shift_repro.c -o /tmp/min_missing_dbg_shift_repro
 *   extract-bc /tmp/min_missing_dbg_shift_repro
 *   /dkucc/home/yl925/klee-deps/build/klee-cf/bin/klee --write-no-tests \
 *     /tmp/min_missing_dbg_shift_repro.bc
 */
int main(int argc, char **argv) {
  (void)argv;

  unsigned long long table[8] = {0};
  unsigned long long acc = 0;
  int xstride = 1 << (argc & 1);

  for (int j = 0; j < xstride; ++j) {
    acc ^= table[j];
    acc ^= table[j + 3 * xstride];
  }

  return (int)acc;
}
