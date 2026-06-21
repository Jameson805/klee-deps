#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  uint8_t ciphertext[MESSAGE_LEN] = {0};
  volatile uint8_t sink;

  crypto_chacha20(ciphertext, message_buf, MESSAGE_LEN, key_buf, nonce_buf);
  sink = ciphertext[0];
  (void)sink;

  return 0;
}
