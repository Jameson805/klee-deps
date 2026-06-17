#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  uint8_t ciphertext[MESSAGE_LEN] = {0};
  uint8_t roundtrip[MESSAGE_LEN] = {0};

  crypto_chacha20(ciphertext, message_buf, MESSAGE_LEN, key_buf, nonce_buf);
  crypto_chacha20(roundtrip, ciphertext, MESSAGE_LEN, key_buf, nonce_buf);

  return crypto_verify64(roundtrip, message_buf) != 0;
}
