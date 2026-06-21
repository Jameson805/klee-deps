#ifndef OPENSSL_RSA_BENCHMARK_COMMON_H
#define OPENSSL_RSA_BENCHMARK_COMMON_H

#include <stddef.h>
#include <string.h>

#include <openssl/bn.h>
#include <openssl/evp.h>
#include <openssl/rsa.h>

#include "crypto/rsa/rsa_local.h"
#include "openssl_rsa_private_base_key_bytes.h"

static BIGNUM *bn_from_bytes(const unsigned char *bytes, size_t len)
{
    return BN_bin2bn(bytes, (int) len, NULL);
}

static RSA *load_symbolic_crt_key(const unsigned char *dp_bytes,
                                  size_t dp_len,
                                  const unsigned char *dq_bytes,
                                  size_t dq_len)
{
    RSA *rsa = NULL;
    BIGNUM *n = NULL;
    BIGNUM *e = NULL;
    BIGNUM *d = NULL;
    BIGNUM *p = NULL;
    BIGNUM *q = NULL;
    BIGNUM *dmp1 = NULL;
    BIGNUM *dmq1 = NULL;
    BIGNUM *iqmp = NULL;

    rsa = RSA_new();
    if (rsa == NULL) {
        goto err;
    }

    n = bn_from_bytes(RSA_N_BYTES, sizeof(RSA_N_BYTES));
    e = bn_from_bytes(RSA_E_BYTES, sizeof(RSA_E_BYTES));
    d = bn_from_bytes(RSA_D_BYTES, sizeof(RSA_D_BYTES));
    p = bn_from_bytes(RSA_P_BYTES, sizeof(RSA_P_BYTES));
    q = bn_from_bytes(RSA_Q_BYTES, sizeof(RSA_Q_BYTES));
    dmp1 = bn_from_bytes(dp_bytes, dp_len);
    dmq1 = bn_from_bytes(dq_bytes, dq_len);
    iqmp = bn_from_bytes(RSA_QP_BYTES, sizeof(RSA_QP_BYTES));
    if (n == NULL || e == NULL || d == NULL || p == NULL || q == NULL
        || dmp1 == NULL || dmq1 == NULL || iqmp == NULL) {
        goto err;
    }

    if (!RSA_set0_key(rsa, n, e, d)) {
        goto err;
    }
    n = NULL;
    e = NULL;
    d = NULL;

    if (!RSA_set0_factors(rsa, p, q)) {
        goto err;
    }
    p = NULL;
    q = NULL;

    if (!RSA_set0_crt_params(rsa, dmp1, dmq1, iqmp)) {
        goto err;
    }
    dmp1 = NULL;
    dmq1 = NULL;
    iqmp = NULL;

    RSA_blinding_off(rsa);
    return rsa;

err:
    BN_free(n);
    BN_free(e);
    BN_free(d);
    BN_free(p);
    BN_free(q);
    BN_free(dmp1);
    BN_free(dmq1);
    BN_free(iqmp);
    RSA_free(rsa);
    return NULL;
}

static int normalize_ciphertext(const RSA *rsa,
                                const unsigned char *ciphertext,
                                size_t ciphertext_len,
                                unsigned char *output,
                                size_t output_len)
{
    const BIGNUM *n = NULL;
    BN_CTX *ctx = NULL;
    BIGNUM *tmp = NULL;
    int ret = 0;
    int num = RSA_size(rsa);

    if (num <= 0 || output_len < (size_t) num) {
        return 0;
    }

    RSA_get0_key(rsa, &n, NULL, NULL);
    if (n == NULL) {
        return 0;
    }

    ctx = BN_CTX_new();
    tmp = BN_new();
    if (ctx == NULL || tmp == NULL) {
        goto cleanup;
    }

    if (BN_bin2bn(ciphertext, (int) ciphertext_len, tmp) == NULL) {
        goto cleanup;
    }
    if (!BN_mod(tmp, tmp, n, ctx)) {
        goto cleanup;
    }
    if (BN_bn2binpad(tmp, output, num) != num) {
        goto cleanup;
    }

    ret = 1;

cleanup:
    BN_free(tmp);
    BN_CTX_free(ctx);
    return ret;
}

static EVP_PKEY *wrap_rsa_in_evp(RSA *rsa)
{
    EVP_PKEY *pkey = EVP_PKEY_new();

    if (pkey == NULL) {
        return NULL;
    }
    if (EVP_PKEY_assign_RSA(pkey, rsa) != 1) {
        EVP_PKEY_free(pkey);
        return NULL;
    }

    return pkey;
}

#endif
