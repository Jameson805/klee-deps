#include "runner_config.generated.h"
#include "library/constant_time_internal.h"
#include "mbedtls/rsa.h"

int driver_main(void)
{
    unsigned char input[RSA_KEY_SIZE];
    unsigned char output[RSA_KEY_SIZE];
    size_t output_len = 0;
    int ret;

    runner_copy_bytes(input, encoded_buf, sizeof(input));

    ret = mbedtls_ct_rsaes_pkcs1_v15_unpadding(input, sizeof(input),
                                                output, sizeof(output),
                                                &output_len);
    if (ret != 0 && ret != MBEDTLS_ERR_RSA_INVALID_PADDING) {
        fprintf(stderr, "ERROR: mbedtls_ct_rsaes_pkcs1_v15_unpadding failed: %d\n", ret);
        return 1;
    }

    return 0;
}
