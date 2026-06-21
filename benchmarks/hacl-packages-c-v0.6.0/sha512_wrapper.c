#include "runner_config.generated.h"
#include "Hacl_Hash_SHA2.h"

int driver_main(void) {
  uint8_t digest[DIGEST_LEN];

  Hacl_Hash_SHA2_hash_512(message_buf, sizeof message_buf, digest);
  return 0;
}