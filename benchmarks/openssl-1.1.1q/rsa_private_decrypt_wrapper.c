#include "runner_config.generated.h"

#include <openssl/rsa.h>

#include "openssl_rsa_benchmark_common.h"

#if defined(OPENSSL_RSA_DECRYPT_PKCS1) + \
    defined(OPENSSL_RSA_DECRYPT_OAEP) + \
    defined(OPENSSL_RSA_DECRYPT_SSLV23) + \
    defined(OPENSSL_RSA_DECRYPT_NO_PADDING) != 1
#error "Define exactly one OpenSSL RSA decrypt target macro."
#endif

static int selected_padding(void)
{
#if defined(OPENSSL_RSA_DECRYPT_PKCS1)
    return RSA_PKCS1_PADDING;
#elif defined(OPENSSL_RSA_DECRYPT_OAEP)
    return RSA_PKCS1_OAEP_PADDING;
#elif defined(OPENSSL_RSA_DECRYPT_SSLV23)
    return RSA_SSLV23_PADDING;
#else
    return RSA_NO_PADDING;
#endif
}

int driver_main(void)
{
    RSA *rsa = NULL;
    unsigned char normalized[sizeof(ciphertext_buf)];
    unsigned char output[sizeof(ciphertext_buf)];
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

    ret = RSA_private_decrypt((int) sizeof(normalized), normalized, output,
                              rsa, selected_padding());
    if (ret > 0) {
        sink ^= output[0];
    } else {
        sink ^= (unsigned char) ret;
    }

    (void) sink;
    RSA_free(rsa);
    return 0;

fail:
    RSA_free(rsa);
    return 1;
}
