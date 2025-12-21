#include "common.h"
#include "mbedtls/bignum.h"

#ifdef USE_SLICED
    #include "bignum_sliced.h"
#endif

int driver_main(const unsigned char *exp_buf, const unsigned char *base_buf, const unsigned char *mod_buf, size_t len)
{
    mbedtls_mpi exp, base, mod, result;
    int ret = 0;

    mbedtls_mpi_init(&exp);
    mbedtls_mpi_init(&base);
    mbedtls_mpi_init(&mod);
    mbedtls_mpi_init(&result);

    ret = mbedtls_mpi_read_binary(&exp,  exp_buf,  len);
    if (ret != 0) { fprintf(stderr, "ERROR: mbedtls_mpi_read_binary(exp) failed: %d\n", ret); goto fail; }
    ret = mbedtls_mpi_read_binary(&base, base_buf, len);
    if (ret != 0) { fprintf(stderr, "ERROR: mbedtls_mpi_read_binary(base) failed: %d\n", ret); goto fail; }
    ret = mbedtls_mpi_read_binary(&mod,  mod_buf,  len);
    if (ret != 0) { fprintf(stderr, "ERROR: mbedtls_mpi_read_binary(mod) failed: %d\n", ret); goto fail; }

    #ifdef USE_SLICED
        mbedtls_mpi_exp_mod_slice_1(&result, &base, &exp, &mod);
        ret = 0;
    #else
        ret = mbedtls_mpi_exp_mod(&result, &base, &exp, &mod, NULL);
    #endif
    if (ret != 0) {
        fprintf(stderr, "ERROR: mbedtls_mpi_exp_mod() failed: %d\n", ret);
        goto fail;
    }

    mbedtls_mpi_free(&result);
    mbedtls_mpi_free(&mod);
    mbedtls_mpi_free(&exp);
    mbedtls_mpi_free(&base);
    return 0;

fail:
    mbedtls_mpi_free(&result);
    mbedtls_mpi_free(&mod);
    mbedtls_mpi_free(&exp);
    mbedtls_mpi_free(&base);
    return 1;
}
