#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  uint8_t public_key[32] = {0};
  volatile uint8_t sink;

  crypto_key_exchange_public_key(public_key, secret_key_buf);
  sink = public_key[0];
  (void)sink;

  return 0;
}
