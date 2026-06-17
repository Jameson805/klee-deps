#include "runner_config.generated.h"
#include "monocypher-ed25519.h"

int driver_main(void) {
  crypto_sign_ed25519_ctx ctx;
  uint8_t public_key[32] = {0};
  uint8_t direct_signature[64] = {0};
  uint8_t incremental_signature[64] = {0};

  crypto_ed25519_public_key(public_key, secret_key_buf);
  crypto_ed25519_sign(direct_signature, secret_key_buf, public_key,
                      message_buf, MESSAGE_LEN);

  crypto_ed25519_sign_init_first_pass(&ctx.ctx, secret_key_buf, public_key);
  crypto_ed25519_sign_update(&ctx.ctx, message_buf, MESSAGE_LEN);
  crypto_ed25519_sign_init_second_pass(&ctx.ctx);
  crypto_ed25519_sign_update(&ctx.ctx, message_buf, MESSAGE_LEN);
  crypto_ed25519_sign_final(&ctx.ctx, incremental_signature);

  if (crypto_verify64(direct_signature, incremental_signature) != 0) {
    return 1;
  }

  return 0;
}
