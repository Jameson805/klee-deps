#include "runner_config.generated.h"
#include "rsa_benchmark_common.h"

int driver_main(void)
{
    int ret = 0;
    size_t output_len = 0;
    unsigned char normalized_input[RSA_KEY_SIZE];
    unsigned char output[RSA_KEY_SIZE];
    mbedtls_rsa_context rsa;

    mbedtls_rsa_init(&rsa);

    ret = load_symbolic_crt_key(&rsa, dp_buf, sizeof(dp_buf), dq_buf, sizeof(dq_buf));
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_rsa_set_padding(&rsa, MBEDTLS_RSA_PKCS_V15, MBEDTLS_MD_NONE);
    if (ret != 0) {
        goto cleanup;
    }

    ret = normalize_ciphertext(&rsa, ciphertext_buf, sizeof(ciphertext_buf),
                               normalized_input, sizeof(normalized_input));
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_rsa_rsaes_pkcs1_v15_decrypt(&rsa, zero_rng, NULL, &output_len,
                                              normalized_input, output, sizeof(output));
    if (ret == MBEDTLS_ERR_RSA_VERIFY_FAILED || ret == MBEDTLS_ERR_RSA_INVALID_PADDING) {
        ret = 0;
    }

cleanup:
    mbedtls_rsa_free(&rsa);
    return ret == 0 ? 0 : 1;
}
