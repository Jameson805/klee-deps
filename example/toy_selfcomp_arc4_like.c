/*
 * Minimal self-composition-style ARC4-like toy.
 *
 * This example is meant for profiling and debugging self-comp overhead on a
 * small state permutation loop with secret-dependent indexing. It is not a
 * benchmark and does not try to model full ARC4 behavior; it only preserves
 * the key shape that makes compare-heavy self-comp runs interesting.
 *
 * Companion helper:
 *   example/toy_selfcomp_arc4_like.profile.sh
 */

#include "klee/klee.h"
#include <stdint.h>

int main(void) {
  uint8_t state[16] = {
      0, 1, 2, 3, 4, 5, 6, 7,
      8, 9, 10, 11, 12, 13, 14, 15,
  };
  uint8_t key[8];
  uint8_t j = 0;
  unsigned i;

  klee_make_symbolic_sc(key, sizeof(key), "key", 1);

  for (i = 0; i < 16; ++i) {
    uint8_t tmp;

    j = (uint8_t)((j + state[i] + key[i & 7]) & 15);
    tmp = state[i];
    state[i] = state[j];
    state[j] = tmp;
  }

  return state[0] & 1;
}
