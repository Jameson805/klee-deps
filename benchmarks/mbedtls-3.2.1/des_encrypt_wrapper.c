#include "runner_config.generated.h"

#include <mbedtls/des.h>

int driver_main(void)
{
    mbedtls_des_context ctx;
    unsigned char output[sizeof(data_buf)] = {0};
    volatile unsigned char sink = 0;
    int ret;

    mbedtls_des_init(&ctx);
    ret = mbedtls_des_setkey_enc(&ctx, key_buf);
    if (ret != 0) {
        mbedtls_des_free(&ctx);
        return 1;
    }

    ret = mbedtls_des_crypt_ecb(&ctx, data_buf, output);
    sink ^= output[0];
    mbedtls_des_free(&ctx);

    (void)sink;
    return ret != 0;
}
