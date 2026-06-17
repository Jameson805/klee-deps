#include "runner_config.generated.h"
#include <sodium.h>

int driver_main(void) {
  unsigned char ciphertext[sizeof message_buf] = {0};

  return crypto_stream_chacha20_xor(ciphertext, message_buf,
                                    sizeof message_buf, nonce_buf, key_buf);
}