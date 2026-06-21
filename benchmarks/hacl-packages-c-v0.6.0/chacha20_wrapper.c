#include "runner_config.generated.h"
#include "Hacl_Chacha20.h"

int driver_main(void) {
  uint8_t output[MESSAGE_LEN];

  Hacl_Chacha20_chacha20_encrypt(sizeof message_buf, output, message_buf,
                                 key_buf, nonce_buf, 0);
  return 0;
}