#include <stdint.h>

#include "generated/tls_rempad_luk13/runner_config.generated.h"
#include "tls1_cbc_remove_padding_lucky13.c"

static uint32_t load_u32(const unsigned char *buf) {
  uint32_t value = 0;
  runner_copy_bytes(&value, buf, sizeof(value));
  return value;
}

int driver_main(void) {
  unsigned long options = (unsigned long)load_u32(options_buf);
  long s3_flags = (long)load_u32(s3_flags_buf);
  unsigned long flags = (unsigned long)load_u32(flags_buf);
  int slicing_cheat = (int)load_u32(slicing_cheat_buf);
  unsigned int block_size = load_u32(block_size_buf);
  unsigned int mac_size = load_u32(mac_size_buf);
  unsigned char data[DATA_LEN] = {0};
  SSL3_STATE s3_obj = {0};
  EVP_CIPHER cipher = {0};
  EVP_CIPHER_CTX cipher_ctx = {0};
  SSL s_obj = {0};
  SSL3_RECORD rec_obj = {0};
  char dummy_expand = 0;

  runner_copy_bytes(data, data_buf, sizeof(data));

  s3_obj.flags = s3_flags;
  cipher.flags = flags;
  cipher_ctx.cipher = &cipher;

  s_obj.expand = &dummy_expand;
  s_obj.options = options;
  s_obj.s3 = &s3_obj;
  s_obj.enc_read_ctx = &cipher_ctx;
  s_obj.slicing_cheat = slicing_cheat;

  rec_obj.length = DATA_LEN;
  rec_obj.data = data;
  rec_obj.input = data;

  return tls1_cbc_remove_padding(&s_obj, &rec_obj, block_size, mac_size);
}
