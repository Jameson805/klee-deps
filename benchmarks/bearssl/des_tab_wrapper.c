#include "runner_config.generated.h"
#include "bearssl.h"

int driver_main(void) {
  br_des_tab_cbcenc_keys ctx = {0};
  unsigned char iv[br_des_tab_BLOCK_SIZE] = {0};
  unsigned char data[DATA_LEN] = {0};

  /* Only the reduced-round prefix of the expanded key schedule is symbolic. */
  runner_copy_bytes(ctx.skey, skey_buf, sizeof(skey_buf));
  runner_copy_bytes(data, data_buf, sizeof(data));
  ctx.vtable = &br_des_tab_cbcenc_vtable;
  ctx.num_rounds = N_ROUND;

  br_des_tab_cbcenc_run(&ctx, iv, data, (size_t)DATA_LEN);
  return 0;
}
