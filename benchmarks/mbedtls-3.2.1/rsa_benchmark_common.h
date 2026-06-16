#ifndef RSA_BENCHMARK_COMMON_H
#define RSA_BENCHMARK_COMMON_H

#include <string.h>

#include "mbedtls/bignum.h"
#include "mbedtls/rsa.h"
#include "rsa_private_base_key_bytes.h"

static int zero_rng(void *rng_state, unsigned char *output, size_t len)
{
    (void) rng_state;
    memset(output, 0, len);
    return 0;
}

static int load_symbolic_crt_key(mbedtls_rsa_context *rsa,
                                 const unsigned char *dp_suffix,
                                 size_t dp_suffix_len,
                                 const unsigned char *dq_suffix,
                                 size_t dq_suffix_len)
{
    int ret;
    unsigned char dp_full[sizeof(RSA_DP_BYTES)];
    unsigned char dq_full[sizeof(RSA_DQ_BYTES)];

    ret = mbedtls_rsa_import_raw(rsa,
                                 RSA_N_BYTES, sizeof(RSA_N_BYTES),
                                 RSA_P_BYTES, sizeof(RSA_P_BYTES),
                                 RSA_Q_BYTES, sizeof(RSA_Q_BYTES),
                                 RSA_D_BYTES, sizeof(RSA_D_BYTES),
                                 RSA_E_BYTES, sizeof(RSA_E_BYTES));
    if (ret != 0) {
        return ret;
    }

    ret = mbedtls_rsa_complete(rsa);
    if (ret != 0) {
        return ret;
    }

    memcpy(dp_full, RSA_DP_BYTES, sizeof(dp_full));
    memcpy(dq_full, RSA_DQ_BYTES, sizeof(dq_full));
    overwrite_suffix(dp_full, sizeof(dp_full), dp_suffix, dp_suffix_len);
    overwrite_suffix(dq_full, sizeof(dq_full), dq_suffix, dq_suffix_len);

    mbedtls_mpi_free(&rsa->MBEDTLS_PRIVATE(DP));
    mbedtls_mpi_free(&rsa->MBEDTLS_PRIVATE(DQ));

    if ((ret = mbedtls_mpi_read_binary(&rsa->MBEDTLS_PRIVATE(DP), dp_full, sizeof(dp_full))) != 0 ||
        (ret = mbedtls_mpi_read_binary(&rsa->MBEDTLS_PRIVATE(DQ), dq_full, sizeof(dq_full))) != 0 ||
        (ret = mbedtls_mpi_lset(&rsa->MBEDTLS_PRIVATE(Vi), 1)) != 0 ||
        (ret = mbedtls_mpi_lset(&rsa->MBEDTLS_PRIVATE(Vf), 1)) != 0) {
        return ret;
    }

    return 0;
}

static int normalize_ciphertext(mbedtls_rsa_context *rsa,
                                const unsigned char *ciphertext,
                                size_t ciphertext_len,
                                unsigned char *output,
                                size_t output_len)
{
    int ret = 0;
    size_t len = rsa->MBEDTLS_PRIVATE(len);
    mbedtls_mpi ciphertext_mpi;

    if (len == 0 || len > output_len) {
        return MBEDTLS_ERR_RSA_BAD_INPUT_DATA;
    }

    mbedtls_mpi_init(&ciphertext_mpi);
    ret = mbedtls_mpi_read_binary(&ciphertext_mpi, ciphertext, ciphertext_len);
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_mpi_mod_mpi(&ciphertext_mpi, &ciphertext_mpi, &rsa->MBEDTLS_PRIVATE(N));
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_mpi_write_binary(&ciphertext_mpi, output, len);

cleanup:
    mbedtls_mpi_free(&ciphertext_mpi);
    return ret;
}

#endif
