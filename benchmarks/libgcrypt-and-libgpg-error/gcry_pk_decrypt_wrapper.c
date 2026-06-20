#include "runner_config.generated.h"

#include <gcrypt.h>

#include "libgcrypt_rsa_benchmark_common.h"

#if defined(LIBGCRYPT_RSA_DECRYPT_PKCS1) + \
    defined(LIBGCRYPT_RSA_DECRYPT_OAEP) + \
    defined(LIBGCRYPT_RSA_DECRYPT_RAW) != 1
#error "Define exactly one Libgcrypt RSA decrypt target macro."
#endif

int driver_main(void)
{
    gcry_sexp_t key = NULL;
    gcry_sexp_t data = NULL;
    gcry_sexp_t result = NULL;
    unsigned char output[256];
    volatile unsigned char sink = 0;
    gcry_error_t err;
    size_t output_len;

    if (!libgcrypt_rsa_init()) {
        return 1;
    }

    key = load_symbolic_private_key(d_buf, sizeof(d_buf));
    if (key == NULL) {
        goto fail;
    }
    data = build_decrypt_data(ciphertext_buf, sizeof(ciphertext_buf));
    if (data == NULL) {
        goto fail;
    }

    err = gcry_pk_decrypt(&result, data, key);
    if (!err && result != NULL) {
        output_len = gcry_sexp_sprint(result, GCRYSEXP_FMT_CANON,
                                      output, sizeof(output));
        if (output_len > 0) {
            sink ^= output[0];
        }
    } else {
        sink ^= (unsigned char) err;
    }

    (void) sink;
    gcry_sexp_release(result);
    gcry_sexp_release(data);
    gcry_sexp_release(key);
    return 0;

fail:
    gcry_sexp_release(result);
    gcry_sexp_release(data);
    gcry_sexp_release(key);
    return 1;
}