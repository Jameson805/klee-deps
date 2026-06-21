#include "runner_config.generated.h"
#include "Hacl_Curve25519_51.h"

int driver_main(void) {
  uint8_t output[OUTPUT_LEN];

  Hacl_Curve25519_51_scalarmult(output, scalar_buf, point_buf);
  return 0;
}