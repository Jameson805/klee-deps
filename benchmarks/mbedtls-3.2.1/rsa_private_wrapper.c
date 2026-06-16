#include "runner_config.generated.h"
#include "rsa_benchmark_common.h"

int driver_main(void)
{
    int ret = 0;
    unsigned char normalized_input[RSA_KEY_SIZE];
    unsigned char output[RSA_KEY_SIZE];
    mbedtls_rsa_context rsa;

    mbedtls_rsa_init(&rsa);

    ret = load_symbolic_crt_key(&rsa, dp_buf, sizeof(dp_buf), dq_buf, sizeof(dq_buf));
    if (ret != 0) {
        goto fail;
    }

    ret = normalize_ciphertext(&rsa, ciphertext_buf, sizeof(ciphertext_buf),
                               normalized_input, sizeof(normalized_input));
    if (ret != 0) {
        goto fail;
    }

    ret = mbedtls_rsa_private(&rsa, zero_rng, NULL, normalized_input, output);
    if (ret != 0 && ret != MBEDTLS_ERR_RSA_VERIFY_FAILED) {
        goto fail;
    }

    mbedtls_rsa_free(&rsa);
    return 0;

fail:
    mbedtls_rsa_free(&rsa);
    return 1;
}
