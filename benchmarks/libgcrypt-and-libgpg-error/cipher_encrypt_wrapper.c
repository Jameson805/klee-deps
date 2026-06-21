#include "runner_config.generated.h"

#include <gcrypt.h>

#if defined(LIBGCRYPT_CIPHER_AES128) + defined(LIBGCRYPT_CIPHER_DES) != 1
#error "Define exactly one Libgcrypt cipher target macro."
#endif

int driver_main(void)
{
    gcry_cipher_hd_t handle = NULL;
    unsigned char output[sizeof(data_buf)] = {0};
    volatile unsigned char sink = 0;
    gcry_error_t err;
    int algorithm;

    if (!gcry_check_version(NULL)) {
        return 1;
    }
    gcry_control(GCRYCTL_DISABLE_SECMEM, 0);
    gcry_control(GCRYCTL_INITIALIZATION_FINISHED, 0);

#if defined(LIBGCRYPT_CIPHER_AES128)
    algorithm = GCRY_CIPHER_AES128;
#else
    algorithm = GCRY_CIPHER_DES;
#endif

    err = gcry_cipher_open(&handle, algorithm, GCRY_CIPHER_MODE_ECB, 0);
    if (err) {
        goto fail;
    }
#if defined(LIBGCRYPT_CIPHER_DES)
    err = gcry_cipher_ctl(handle, GCRYCTL_SET_ALLOW_WEAK_KEY, NULL, 1);
    if (err) {
        goto fail;
    }
#endif
    err = gcry_cipher_setkey(handle, key_buf, sizeof(key_buf));
    if (err) {
#if defined(LIBGCRYPT_CIPHER_DES)
        if (gcry_err_code(err) != GPG_ERR_WEAK_KEY) {
            goto fail;
        }
#else
        goto fail;
#endif
    }
    err = gcry_cipher_encrypt(handle, output, sizeof(output), data_buf, sizeof(data_buf));
    if (err) {
        goto fail;
    }
    sink ^= output[0];

    (void) sink;
    gcry_cipher_close(handle);
    return 0;

fail:
    fprintf(stderr, "libgcrypt cipher benchmark failed: %s (%s)\n",
            gcry_strerror(err), gcry_strsource(err));
    gcry_cipher_close(handle);
    return 1;
}