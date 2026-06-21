#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  uint8_t direct_hash[HASH_LEN] = {0};
  uint8_t direct_work_area[ARGON2_BLOCKS * 1024] = {0};
  volatile uint8_t sink;

  crypto_argon2i(direct_hash, HASH_LEN,
                 direct_work_area, ARGON2_BLOCKS, ARGON2_ITERATIONS,
                 password_buf, PASSWORD_LEN,
                 salt_buf, SALT_LEN);
  sink = direct_hash[0];
  (void)sink;

  return 0;
}
