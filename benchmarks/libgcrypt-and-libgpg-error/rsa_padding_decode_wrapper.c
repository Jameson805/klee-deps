#include "runner_config.generated.h"

#include <gcrypt.h>

#include "libgcrypt_rsa_benchmark_common.h"

#if defined(LIBGCRYPT_RSA_PKCS1_DECODE_FOR_ENC) + \
    defined(LIBGCRYPT_RSA_OAEP_DECODE) != 1
#error "Define exactly one Libgcrypt RSA padding decode target macro."
#endif

gcry_err_code_t _gcry_rsa_pkcs1_decode_for_enc(unsigned char **r_result,
                                               size_t *r_resultlen,
                                               unsigned int nbits,
                                               gcry_mpi_t value);
gcry_err_code_t _gcry_rsa_oaep_decode(unsigned char **r_result,
                                      size_t *r_resultlen,
                                      unsigned int nbits,
                                      int algo,
                                      gcry_mpi_t value,
                                      const unsigned char *label,
                                      size_t labellen);

int driver_main(void)
{
    gcry_mpi_t encoded = NULL;
    unsigned char *decoded = NULL;
    size_t decoded_len = 0;
    volatile unsigned char sink = 0;
    gcry_err_code_t rc;

    if (!libgcrypt_rsa_init()) {
        return 1;
    }

    rc = scan_mpi(&encoded, encoded_buf, sizeof(encoded_buf));
    if (rc) {
        goto fail;
    }

#if defined(LIBGCRYPT_RSA_PKCS1_DECODE_FOR_ENC)
    rc = _gcry_rsa_pkcs1_decode_for_enc(&decoded, &decoded_len,
                                        RSA_KEY_SIZE * 8, encoded);
#else
    rc = _gcry_rsa_oaep_decode(&decoded, &decoded_len,
                               RSA_KEY_SIZE * 8, GCRY_MD_SHA1,
                               encoded, NULL, 0);
#endif

    if (!rc && decoded_len > 0) {
        sink ^= decoded[0];
    } else {
        sink ^= (unsigned char) rc;
    }

    (void) sink;
    gcry_free(decoded);
    gcry_mpi_release(encoded);
    return 0;

fail:
    gcry_free(decoded);
    gcry_mpi_release(encoded);
    return 1;
}