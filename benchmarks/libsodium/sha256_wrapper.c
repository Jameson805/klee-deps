#include "runner_config.generated.h"
#include <sodium.h>

int driver_main(void) {
  unsigned char digest[crypto_hash_sha256_BYTES] = {0};

  return crypto_hash_sha256(digest, message_buf, sizeof message_buf);
}