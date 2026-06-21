#include "runner_config.generated.h"

#include <gcrypt.h>

static int libgcrypt_ecdsa_init(void)
{
    if (!gcry_check_version(NULL)) {
        return 0;
    }
    gcry_control(GCRYCTL_DISABLE_SECMEM, 0);
    gcry_control(GCRYCTL_INITIALIZATION_FINISHED, 0);
    return 1;
}

int driver_main(void)
{
    gcry_mpi_t private_key = NULL;
    gcry_sexp_t key = NULL;
    gcry_sexp_t data = NULL;
    gcry_sexp_t signature = NULL;
    unsigned char output[256];
    volatile unsigned char sink = 0;
    gcry_error_t err;
    size_t output_len;

    if (!libgcrypt_ecdsa_init()) {
        return 1;
    }

    err = gcry_mpi_scan(&private_key, GCRYMPI_FMT_USG,
                        private_key_buf, sizeof(private_key_buf), NULL);
    if (err) {
        goto fail;
    }
    gcry_mpi_add_ui(private_key, private_key, 1);
    err = gcry_sexp_build(&key, NULL,
                          "(private-key(ecc(curve \"NIST P-256\")(d %m)))",
                          private_key);
    if (err) {
        goto fail;
    }
    err = gcry_sexp_build(&data, NULL,
                          "(data(flags rfc6979 no-blinding)(hash sha256 %b))",
                          (int) sizeof(digest_buf), digest_buf);
    if (err) {
        goto fail;
    }

    err = gcry_pk_sign(&signature, data, key);
    if (err || signature == NULL) {
        goto fail;
    }
    output_len = gcry_sexp_sprint(signature, GCRYSEXP_FMT_CANON,
                                  output, sizeof(output));
    if (output_len > 0) {
        sink ^= output[0];
    }

    (void) sink;
    gcry_sexp_release(signature);
    gcry_sexp_release(data);
    gcry_sexp_release(key);
    gcry_mpi_release(private_key);
    return 0;

fail:
    gcry_sexp_release(signature);
    gcry_sexp_release(data);
    gcry_sexp_release(key);
    gcry_mpi_release(private_key);
    return 1;
}