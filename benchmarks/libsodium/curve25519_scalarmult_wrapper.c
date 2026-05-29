#include "runner_config.generated.h"
#include <sodium.h>

int driver_main(void) {
  unsigned char shared[crypto_scalarmult_curve25519_BYTES] = {0};

  /* The benchmark models a secret scalar multiplied by a caller-controlled point. */
  (void) crypto_scalarmult_curve25519(shared, scalar_buf, point_buf);
  return 0;
}