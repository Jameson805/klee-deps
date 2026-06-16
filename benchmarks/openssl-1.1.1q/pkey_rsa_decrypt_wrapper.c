#include "runner_config.generated.h"

#include <openssl/evp.h>
#include <openssl/rsa.h>

#include "openssl_rsa_benchmark_common.h"

#if defined(OPENSSL_RSA_DECRYPT_PKCS1) + \
    defined(OPENSSL_RSA_DECRYPT_OAEP) + \
    defined(OPENSSL_RSA_DECRYPT_SSLV23) + \
    defined(OPENSSL_RSA_DECRYPT_NO_PADDING) != 1
#error "Define exactly one OpenSSL RSA decrypt target macro."
#endif

int driver_main(void)
{
    RSA *rsa = NULL;
    EVP_PKEY *pkey = NULL;
    EVP_PKEY_CTX *ctx = NULL;
    unsigned char normalized[sizeof(ciphertext_buf)];
    unsigned char output[sizeof(ciphertext_buf)];
    size_t output_len = sizeof(output);
    volatile unsigned char sink = 0;
    int ret;

    rsa = load_symbolic_crt_key(dp_buf, sizeof(dp_buf), dq_buf, sizeof(dq_buf));
    if (rsa == NULL) {
        goto fail;
    }
    if (!normalize_ciphertext(rsa, ciphertext_buf, sizeof(ciphertext_buf),
                              normalized, sizeof(normalized))) {
        goto fail;
    }

    pkey = wrap_rsa_in_evp(rsa);
    if (pkey == NULL) {
        goto fail;
    }
    rsa = NULL;

    ctx = EVP_PKEY_CTX_new(pkey, NULL);
    if (ctx == NULL) {
        goto fail;
    }
    if (EVP_PKEY_decrypt_init(ctx) <= 0) {
        goto fail;
    }

#if defined(OPENSSL_RSA_DECRYPT_PKCS1)
    if (EVP_PKEY_CTX_set_rsa_padding(ctx, RSA_PKCS1_PADDING) <= 0) {
        goto fail;
    }
#elif defined(OPENSSL_RSA_DECRYPT_OAEP)
    if (EVP_PKEY_CTX_set_rsa_padding(ctx, RSA_PKCS1_OAEP_PADDING) <= 0
        || EVP_PKEY_CTX_set_rsa_oaep_md(ctx, EVP_sha256()) <= 0
        || EVP_PKEY_CTX_set_rsa_mgf1_md(ctx, EVP_sha256()) <= 0) {
        goto fail;
    }
#elif defined(OPENSSL_RSA_DECRYPT_SSLV23)
    if (EVP_PKEY_CTX_set_rsa_padding(ctx, RSA_SSLV23_PADDING) <= 0) {
        goto fail;
    }
#else
    if (EVP_PKEY_CTX_set_rsa_padding(ctx, RSA_NO_PADDING) <= 0) {
        goto fail;
    }
#endif

    ret = EVP_PKEY_decrypt(ctx, output, &output_len, normalized, sizeof(normalized));
    if (ret > 0 && output_len > 0) {
        sink ^= output[0];
    } else {
        sink ^= (unsigned char) ret;
    }

    (void) sink;
    EVP_PKEY_CTX_free(ctx);
    EVP_PKEY_free(pkey);
    return 0;

fail:
    EVP_PKEY_CTX_free(ctx);
    EVP_PKEY_free(pkey);
    RSA_free(rsa);
    return 1;
}
