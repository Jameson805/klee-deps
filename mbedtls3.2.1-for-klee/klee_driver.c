#include <stdio.h>
#include <stdlib.h> // For EXIT_SUCCESS, EXIT_FAILURE
#include <limits.h>
#include "klee/klee.h"

int main() {
    mbedtls_mpi A_base, E_exponent, N_modulus, X_result;
    int ret;

    mbedtls_mpi_init(&A_base);
    mbedtls_mpi_init(&E_exponent);
    mbedtls_mpi_init(&N_modulus);
    mbedtls_mpi_init(&X_result);

    int64_t A;
    klee_make_symbolic_sc(&A, sizeof(A), "A", 0);
    // mbedtls_mpi_lset sets an MPI from a long integer.
    ret = mbedtls_mpi_lset(&A_base, A);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(A_base) failed with %d\n", ret);
        goto cleanup;
    }

    int64_t E;
    klee_make_symbolic_sc(&E, sizeof(E), "E", 1);
    ret = mbedtls_mpi_lset(&E_exponent, E);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(E_exponent) failed with %d\n", ret);
        goto cleanup;
    }

    int64_t N;
    klee_make_symbolic_sc(&N, sizeof(N), "N", 0);
    ret = mbedtls_mpi_lset(&N_modulus, N);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(N_modulus) failed with %d\n", ret);
        goto cleanup;
    }

    ret = mbedtls_mpi_exp_mod(&X_result, &A_base, &E_exponent, &N_modulus, NULL);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_exp_mod() failed with %d\n", ret);
        goto cleanup;
    }

cleanup:
    mbedtls_mpi_free(&X_result);
    mbedtls_mpi_free(&N_modulus);
    mbedtls_mpi_free(&E_exponent);
    mbedtls_mpi_free(&A_base);

    // Return success or failure based on the operation's outcome
    return (ret == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
