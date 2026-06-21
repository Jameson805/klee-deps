#include "runner_config.generated.h"
#include "bearssl.h"

int driver_main(void) {
  br_aes_ct_cbcenc_keys ctx = {0};
  unsigned char iv[IV_LEN] = {0};
  unsigned char data[DATA_LEN] = {0};

  runner_copy_bytes(ctx.skey, skey_buf, sizeof(skey_buf));
  runner_copy_bytes(iv, iv_buf, sizeof(iv));
  runner_copy_bytes(data, data_buf, sizeof(data));
  ctx.vtable = &br_aes_ct_cbcenc_vtable;
  ctx.num_rounds = N_ROUND;

  br_aes_ct_cbcenc_run(&ctx, iv, data, (size_t)DATA_LEN);
  return 0;
}
