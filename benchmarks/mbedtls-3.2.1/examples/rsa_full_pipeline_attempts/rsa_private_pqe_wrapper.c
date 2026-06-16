#include "runner_config.generated.h"
#include "mbedtls/bignum.h"
#include "mbedtls/rsa.h"
#include "../rsa_private_base_key_bytes.h"

#define RSA_INPUT_CAP 128

static int zero_rng(void *rng_state, unsigned char *output, size_t len)
{
    (void) rng_state;
    memset(output, 0, len);
    return 0;
}

static int normalize_ciphertext(mbedtls_rsa_context *rsa, unsigned char output[RSA_INPUT_CAP])
{
    int ret = 0;
    size_t len = rsa->MBEDTLS_PRIVATE(len);
    mbedtls_mpi ciphertext;

    if (len == 0 || len > RSA_INPUT_CAP) {
        return MBEDTLS_ERR_RSA_BAD_INPUT_DATA;
    }

    mbedtls_mpi_init(&ciphertext);
    ret = mbedtls_mpi_read_binary(&ciphertext, ciphertext_buf, sizeof(ciphertext_buf));
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_mpi_mod_mpi(&ciphertext, &ciphertext, &rsa->MBEDTLS_PRIVATE(N));
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_mpi_write_binary(&ciphertext, output, len);

cleanup:
    mbedtls_mpi_free(&ciphertext);
    return ret;
}

int driver_main(void)
{
    int ret = 0;
    unsigned char p_full[sizeof(RSA_P_BYTES)];
    unsigned char q_full[sizeof(RSA_Q_BYTES)];
    unsigned char normalized_input[RSA_INPUT_CAP];
    unsigned char output[RSA_INPUT_CAP];
    mbedtls_rsa_context rsa;

    mbedtls_rsa_init(&rsa);

    memcpy(p_full, RSA_P_BYTES, sizeof(p_full));
    memcpy(q_full, RSA_Q_BYTES, sizeof(q_full));
    overwrite_suffix(p_full, sizeof(p_full), p_buf, sizeof(p_buf));
    overwrite_suffix(q_full, sizeof(q_full), q_buf, sizeof(q_buf));

    ret = mbedtls_rsa_import_raw(&rsa,
                                 NULL, 0,
                                 p_full, sizeof(p_full),
                                 q_full, sizeof(q_full),
                                 NULL, 0,
                                 RSA_E_BYTES, sizeof(RSA_E_BYTES));
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_rsa_complete(&rsa);
    if (ret != 0) {
        ret = 0;
        goto cleanup;
    }

    if ((ret = mbedtls_mpi_lset(&rsa.MBEDTLS_PRIVATE(Vi), 1)) != 0 ||
        (ret = mbedtls_mpi_lset(&rsa.MBEDTLS_PRIVATE(Vf), 1)) != 0) {
        goto cleanup;
    }

    ret = normalize_ciphertext(&rsa, normalized_input);
    if (ret != 0) {
        ret = 0;
        goto cleanup;
    }

    ret = mbedtls_rsa_private(&rsa, zero_rng, NULL, normalized_input, output);
    if (ret == MBEDTLS_ERR_RSA_VERIFY_FAILED) {
        ret = 0;
    }

cleanup:
    mbedtls_rsa_free(&rsa);
    return ret == 0 ? 0 : 1;
}