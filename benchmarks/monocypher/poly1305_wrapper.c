#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  uint8_t direct_mac[16] = {0};
  volatile uint8_t sink;

  crypto_poly1305(direct_mac, message_buf, MESSAGE_LEN, key_buf);
  sink = direct_mac[0];
  (void)sink;

  return 0;
}
