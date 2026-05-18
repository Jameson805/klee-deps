#include "klee/klee.h"

int table_a[4];
int table_b[4];
int out[8];

int main(void) {
  int pub;
  int secret;

  klee_make_symbolic(&pub, sizeof(pub), "pub");
  klee_make_symbolic_sc(&secret, sizeof(secret), "secret", 1);

  pub &= 1;
  secret &= 7;

  int base = pub ? 4 : 0;

  if (secret & 4) {
    out[base + (secret & 1)] = 1;
    table_a[(secret >> 1) & 3] = 2;
  } else {
    out[base + 2] = 1;
  }

  out[base + ((secret ^ pub) & 3)] += 3;

  if ((secret & 3) == 3) {
    table_b[(secret ^ 1) & 3] = 4;
  }

  return 0;
}