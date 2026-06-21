#include "runner_config.generated.h"

#include <mbedtls/aes.h>

int driver_main(void)
{
    mbedtls_aes_context ctx;
    unsigned char iv[sizeof(iv_buf)] = {0};
    unsigned char output[sizeof(data_buf)] = {0};
    volatile unsigned char sink = 0;
    int ret;

    mbedtls_aes_init(&ctx);
    ret = mbedtls_aes_setkey_enc(&ctx, key_buf, KEY_BITS);
    if (ret != 0) {
        mbedtls_aes_free(&ctx);
        return 1;
    }

    runner_copy_bytes(iv, iv_buf, sizeof(iv));
    ret = mbedtls_aes_crypt_cbc(&ctx, MBEDTLS_AES_ENCRYPT, sizeof(data_buf),
                                iv, data_buf, output);
    sink ^= output[0];
    mbedtls_aes_free(&ctx);

    (void)sink;
    return ret != 0;
}
