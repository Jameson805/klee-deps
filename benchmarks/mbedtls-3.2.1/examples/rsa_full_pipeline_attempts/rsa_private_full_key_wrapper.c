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
    unsigned char n_full[sizeof(RSA_N_BYTES)];
    unsigned char p_full[sizeof(RSA_P_BYTES)];
    unsigned char q_full[sizeof(RSA_Q_BYTES)];
    unsigned char d_full[sizeof(RSA_D_BYTES)];
    unsigned char dp_full[sizeof(RSA_DP_BYTES)];
    unsigned char dq_full[sizeof(RSA_DQ_BYTES)];
    unsigned char qp_full[sizeof(RSA_QP_BYTES)];
    unsigned char normalized_input[RSA_INPUT_CAP];
    unsigned char output[RSA_INPUT_CAP];
    mbedtls_rsa_context rsa;

    mbedtls_rsa_init(&rsa);

    memcpy(n_full, RSA_N_BYTES, sizeof(n_full));
    memcpy(p_full, RSA_P_BYTES, sizeof(p_full));
    memcpy(q_full, RSA_Q_BYTES, sizeof(q_full));
    memcpy(d_full, RSA_D_BYTES, sizeof(d_full));
    memcpy(dp_full, RSA_DP_BYTES, sizeof(dp_full));
    memcpy(dq_full, RSA_DQ_BYTES, sizeof(dq_full));
    memcpy(qp_full, RSA_QP_BYTES, sizeof(qp_full));

    overwrite_suffix(n_full, sizeof(n_full), n_buf, sizeof(n_buf));
    overwrite_suffix(p_full, sizeof(p_full), p_buf, sizeof(p_buf));
    overwrite_suffix(q_full, sizeof(q_full), q_buf, sizeof(q_buf));
    overwrite_suffix(d_full, sizeof(d_full), d_buf, sizeof(d_buf));
    overwrite_suffix(dp_full, sizeof(dp_full), dp_buf, sizeof(dp_buf));
    overwrite_suffix(dq_full, sizeof(dq_full), dq_buf, sizeof(dq_buf));
    overwrite_suffix(qp_full, sizeof(qp_full), qp_buf, sizeof(qp_buf));

    rsa.MBEDTLS_PRIVATE(len) = sizeof(n_full);

    if ((ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(N), n_full, sizeof(n_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(P), p_full, sizeof(p_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(Q), q_full, sizeof(q_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(D), d_full, sizeof(d_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(DP), dp_full, sizeof(dp_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(DQ), dq_full, sizeof(dq_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(QP), qp_full, sizeof(qp_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa.MBEDTLS_PRIVATE(E), RSA_E_BYTES, sizeof(RSA_E_BYTES))) != 0) {
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