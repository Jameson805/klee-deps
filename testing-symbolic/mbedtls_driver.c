/*
Author: Jameson DiPalma
*/

#define MBEDTLS_ALLOW_PRIVATE_ACCESS

#include <stdlib.h>
#include <string.h>
#include <klee/klee.h>
#include <assert.h>
#include "branch_tracker.h"
#include "mbedtls/include/mbedtls/bignum.h"

#define LIMB_COUNT 2  // Reduced for manageable bitwidth

// Initialize an mpi struct with fixed values
void mpi_init_concrete(mbedtls_mpi *mpi, mbedtls_mpi_uint val) {
    mpi->s = 1;
    mpi->n = LIMB_COUNT;
    mpi->p = malloc(LIMB_COUNT * sizeof(mbedtls_mpi_uint));
    for (size_t i = 0; i < LIMB_COUNT; ++i) {
        mpi->p[i] = val + i;
    }
}

// Initialize an mpi struct as symbolic and constrain values
void mpi_init_symbolic_limited(mbedtls_mpi *mpi, const char *name_prefix) {
    mpi->s = 1;
    mpi->n = LIMB_COUNT;
    mpi->p = malloc(LIMB_COUNT * sizeof(mbedtls_mpi_uint));
    memset(mpi->p, 0, LIMB_COUNT * sizeof(mbedtls_mpi_uint));

    klee_make_symbolic(mpi->p, LIMB_COUNT * sizeof(mbedtls_mpi_uint), name_prefix);

    // Limit each limb to <= 16 bits to avoid 128-bit temporaries
    for (size_t i = 0; i < LIMB_COUNT; ++i) {
        klee_assume(mpi->p[i] <= 0xFFFF);
    }
}

int main() {
    mbedtls_mpi X, A, E1, E2, N, prec_RR;

    // Concrete "plaintext" base A, modulus N, and prec_RR
    mpi_init_concrete(&A, 0x42);
    mpi_init_concrete(&N, 0x1337);
    mpi_init_concrete(&prec_RR, 0xBEEF);

    // Symbolic secret exponents E1 and E2
    mpi_init_symbolic_limited(&E1, "E1");
    mpi_init_symbolic_limited(&E2, "E2");

    reset_branch_history();

    program_run = 1;
    mbedtls_mpi_exp_mod(&X, &A, &E1, &N, &prec_RR);

    program_run = 2;
    mbedtls_mpi_exp_mod(&X, &A, &E2, &N, &prec_RR);

    assert(branch_histories_equal());

    // Clean up
    free(A.p);
    free(E1.p);
    free(E2.p);
    free(N.p);
    free(prec_RR.p);

    return 0;
}
