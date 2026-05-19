#include "runner_config.generated.h"
#include <gcrypt.h>

#ifdef USE_SLICED
    #include "powm_sliced.h"
#endif

int driver_main(void)
{
    size_t len = sizeof(exp_buf);

    if (!gcry_check_version(NULL)) {
        fprintf(stderr, "libgcrypt init failed\n");
        return 1;
    }
    gcry_control(GCRYCTL_DISABLE_SECMEM, 0);
    gcry_control(GCRYCTL_INITIALIZATION_FINISHED, 0);

    gcry_mpi_t exp = NULL, base = NULL, mod = NULL, result = NULL;
    gcry_error_t err;

    err = gcry_mpi_scan(&exp,  GCRYMPI_FMT_USG, exp_buf, len, NULL);
    if (err) {
        fprintf(stderr, "gcry_mpi_scan(exp) failed: %s (%s)\n", gcry_strerror(err), gcry_strsource(err));
        goto fail;
    }

    err = gcry_mpi_scan(&base, GCRYMPI_FMT_USG, base_buf, len, NULL);
    if (err) {
        fprintf(stderr, "gcry_mpi_scan(base) failed: %s (%s)\n", gcry_strerror(err), gcry_strsource(err));
        goto fail;
    }

    err = gcry_mpi_scan(&mod,  GCRYMPI_FMT_USG, mod_buf, len, NULL);
    if (err) {
        fprintf(stderr, "gcry_mpi_scan(mod) failed: %s (%s)\n", gcry_strerror(err), gcry_strsource(err));
        goto fail;
    }

    result = gcry_mpi_new((unsigned)(len * 8));
    if (!result) {
        fprintf(stderr, "gcry_mpi_new(result) failed: out of memory\n"); goto fail;
    }

    #ifdef USE_SLICED
        _gcry_mpi_powm_slice_1(result, base, exp, mod); /* no error code */
    #else
        gcry_mpi_powm(result, base, exp, mod);          /* no error code */
    #endif

    gcry_mpi_release(result);
    gcry_mpi_release(base);
    gcry_mpi_release(exp);
    gcry_mpi_release(mod);
    return 0;

fail:
    if (result) gcry_mpi_release(result);
    if (base)   gcry_mpi_release(base);
    if (exp)    gcry_mpi_release(exp);
    if (mod)    gcry_mpi_release(mod);
    return 1;
}
