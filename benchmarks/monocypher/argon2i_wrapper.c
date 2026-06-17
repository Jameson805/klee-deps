#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  uint8_t direct_hash[HASH_LEN] = {0};
  uint8_t general_hash[HASH_LEN] = {0};
  uint8_t direct_work_area[ARGON2_BLOCKS * 1024] = {0};
  uint8_t general_work_area[ARGON2_BLOCKS * 1024] = {0};

  crypto_argon2i(direct_hash, HASH_LEN,
                 direct_work_area, ARGON2_BLOCKS, ARGON2_ITERATIONS,
                 password_buf, PASSWORD_LEN,
                 salt_buf, SALT_LEN);

  crypto_argon2i_general(general_hash, HASH_LEN,
                         general_work_area, ARGON2_BLOCKS, ARGON2_ITERATIONS,
                         password_buf, PASSWORD_LEN,
                         salt_buf, SALT_LEN,
                         0, 0,
                         0, 0);

  return crypto_verify32(direct_hash, general_hash) != 0;
}
