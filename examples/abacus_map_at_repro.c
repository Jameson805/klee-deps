/*
 * Reproducer for an ABACUS BitVector traversal issue in getInputSymbolSet().
 *
 * The repeated arithmetic keeps building a larger expression graph from one
 * symbolic byte. In the buggy traversal, shared subexpressions can be revisited
 * repeatedly while walking that graph, which made the analysis fall back to an
 * oversized-worklist escape path instead of finishing the input-symbol scan.
 */

#include <stdint.h>

void abacus_make_symbolic(char *name, void *addr, uint32_t length) {
  (void)name;
  (void)addr;
  (void)length;
}

volatile uint32_t output;

int main(void) {
  uint8_t secret = 0x5a;
  uint32_t a;
  uint32_t b;

  abacus_make_symbolic("key", &secret, 1);

  a = secret;
  b = (uint32_t)secret + 1u;

  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;
  a = a + b; b = a + b;

  output = b;
  return 0;
}