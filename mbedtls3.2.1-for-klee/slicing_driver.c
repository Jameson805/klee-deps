#include "mbedtls/bignum.h"
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>

/* Frama-C nondeterministic interval helper */
extern int Frama_C_interval(int a, int b);

int main() {
    mbedtls_mpi A_base, E_exponent, N_modulus, X_result;
    int ret;

    mbedtls_mpi_init(&A_base);
    mbedtls_mpi_init(&E_exponent);
    mbedtls_mpi_init(&N_modulus);
    mbedtls_mpi_init(&X_result);

    int64_t A = Frama_C_interval(-100, 100);
    int64_t E = Frama_C_interval(0, 10);
    int64_t N = Frama_C_interval(2, 100);

    ret = mbedtls_mpi_lset(&A_base, A);
    if (ret != 0) goto cleanup;

    ret = mbedtls_mpi_lset(&E_exponent, E);
    if (ret != 0) goto cleanup;

    ret = mbedtls_mpi_lset(&N_modulus, N);
    if (ret != 0) goto cleanup;

    ret = mbedtls_mpi_exp_mod(&X_result, &A_base, &E_exponent, &N_modulus, NULL);
    if (ret != 0) goto cleanup;

    int result = 0;
    // Optionally extract a byte from the result for slicing
    // (Assumes MBEDTLS_MPI_PRIVATE macro is available, otherwise use direct access if allowed)
    // result = (int)(MBEDTLS_MPI_PRIVATE(X_result, p)[0] & 0xff);
    (void) result;

cleanup:
    mbedtls_mpi_free(&X_result);
    mbedtls_mpi_free(&N_modulus);
    mbedtls_mpi_free(&E_exponent);
    mbedtls_mpi_free(&A_base);

    return (ret == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}

/*
frama-c slicing_driver.c mbedtls3.2.1/library/bignum.c \
  -cpp-extra-args="-Imbedtls3.2.1/include" \
  -slice-annot="mbedtls_mpi_exp_mod" \
  -then-on 'Slicing export' -print > bignum_2125_sliced.c
*/
