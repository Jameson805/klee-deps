#include "runner_config.generated.h"
#include <sodium.h>

int driver_main(void) {
  unsigned char output[MESSAGE_LEN];

  return crypto_stream_chacha20_xor(output, message_buf,
                                    sizeof message_buf, nonce_buf, key_buf);
}
