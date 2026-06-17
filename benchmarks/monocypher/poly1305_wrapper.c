#include "runner_config.generated.h"
#include "monocypher.h"

int driver_main(void) {
  crypto_poly1305_ctx ctx;
  uint8_t direct_mac[16] = {0};
  uint8_t incremental_mac[16] = {0};

  crypto_poly1305(direct_mac, message_buf, MESSAGE_LEN, key_buf);

  crypto_poly1305_init(&ctx, key_buf);
  crypto_poly1305_update(&ctx, message_buf, MESSAGE_LEN / 2);
  crypto_poly1305_update(&ctx, message_buf + (MESSAGE_LEN / 2),
                         MESSAGE_LEN - (MESSAGE_LEN / 2));
  crypto_poly1305_final(&ctx, incremental_mac);

  return crypto_verify16(direct_mac, incremental_mac) != 0;
}
