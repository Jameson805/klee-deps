#include "mbedtls/bignum.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

#ifndef REPLAY
    #include "klee/klee.h"
#endif

int load_bytes(const char *filename, void *buf, size_t size)
{
    FILE *f = fopen(filename, "rb");
    if (!f) {
        printf("ERROR: unable to open file %s\n", filename);
        return 0;
    }

    if (fread(buf, 1, size, f) != size) {
        printf("ERROR: reading file %s\n", filename);
        fclose(f);
        return 0;
    }

    fclose(f);
    return 1;
}

/* Constant-time bit-length of signed 64-bit integer, ignoring the sign bit.
   That is, it computes bitlen(abs(x)) for bits [0..62].
   Returns 0 if all 63 lower bits are zero.
   Runs in constant time with respect to input value. */
unsigned bitlen_i64_nosign(int64_t x) {
    uint64_t ux = (uint64_t)x & 0x7FFFFFFFFFFFFFFFULL; /* mask off sign bit */
    unsigned found = 0;
    unsigned bitpos = 0;

    /* Scan bits 62..0 (most-significant to least-significant) */
    for (int j = 62; j >= 0; --j) {
        unsigned bit = (unsigned)((ux >> j) & 1u);
        unsigned set = bit & (1u - found);      /* set only on first (highest) 1 */
        bitpos = (set * (unsigned)j) | ((1u - set) * bitpos);
        found |= bit;
    }

    /* bitlen = found ? bitpos + 1 : 0, branchless */
    return found * (bitpos + 1u);
}

int main(int argc, char *argv[]) {
    #ifdef REPLAY
        #ifdef CONCRETE_PUBS
            assert(argc == 2 && "Required arguments: <E_filename>");
            char *E_filename = argv[1];
        #else
            assert(argc == 4 && "Required arguments: <E_filename> <A_filename> <N_filename>");
            char *E_filename = argv[1];
            char *A_filename = argv[2];
            char *N_filename = argv[3];
        #endif
    #endif

    // Declare mbedtls_mpi variables for exponent (E_exponent), base (A_base), modulus (N_modulus), and result (X_result)
    mbedtls_mpi E_exponent, A_base, N_modulus, X_result;
    int ret; // For return codes of mbedtls functions

    // 1. Initialize MPI variables
    // This function allocates and initializes the internal structure of the MPI.
    mbedtls_mpi_init(&E_exponent);
    mbedtls_mpi_init(&A_base);
    mbedtls_mpi_init(&N_modulus);
    mbedtls_mpi_init(&X_result);

    // 2. Set values for A_base, E_exponent, and N_modulus using mbedtls_mpi_lset for simpler integer assignments.
    // We'll calculate X_result = A_base^E_exponent mod N_modulus

    int64_t E;
    #ifdef REPLAY
        if (!load_bytes(E_filename, &E, sizeof(E))) goto cleanup;
    #else
        klee_make_symbolic_sc(&E, sizeof(E), "E", 1);
        klee_assume(E >= 1);

        size_t bitlen;
        klee_make_symbolic_sc(&bitlen, sizeof(bitlen), "E_bitlen", 0);
        // E and E' must be of the same bit length
        klee_assume(bitlen_i64_nosign(E) == bitlen);
    #endif

    int64_t A;
    #ifdef CONCRETE_PUBS
        A = 100003;
    #else
        #ifdef REPLAY
            if (!load_bytes(A_filename, &A, sizeof(A))) goto cleanup;
        #else
            klee_make_symbolic_sc(&A, sizeof(A), "A", 0);
            klee_assume(A >= 1);
        #endif
    #endif

    int64_t N;
    #ifdef CONCRETE_PUBS
        N = 1000000007;
    #else
        #ifdef REPLAY
            if (!load_bytes(N_filename, &N, sizeof(N))) goto cleanup;
        #else
            klee_make_symbolic_sc(&N, sizeof(N), "N", 0);
            klee_assume(N >= 1);
            klee_assume(N % 2 == 1);
        #endif
    #endif

    ret = mbedtls_mpi_lset(&E_exponent, E);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(E_exponent) failed with %d\n", ret);
        goto cleanup;
    }
    ret = mbedtls_mpi_lset(&A_base, A);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(A_base) failed with %d\n", ret);
        goto cleanup;
    }
    ret = mbedtls_mpi_lset(&N_modulus, N);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(N_modulus) failed with %d\n", ret);
        goto cleanup;
    }

    // printf("Calculating X_result = A_base^E_exponent mod N_modulus\n");
    // mbedtls_mpi_write_file writes the MPI value to a file (or stdout if path is NULL).
    // The second argument is the radix.

    #ifdef PRINT
    mbedtls_mpi_write_file("A_base (base):     ", &A_base, 10, NULL);
    mbedtls_mpi_write_file("E_exponent (exponent): ", &E_exponent, 10, NULL);
    mbedtls_mpi_write_file("N_modulus (modulus):  ", &N_modulus, 10, NULL);
    #endif

    // 3. Call mbedtls_mpi_exp_mod(X_result, A_base, E_exponent, N_modulus, prec_RR)
    // Based on the signature:
    // X_result: The result (output) MPI
    // A_base: The base (input) MPI
    // E_exponent: The exponent (input) MPI
    // N_modulus: The modulus (input) MPI
    // prec_RR: Optional precomputed context for optimization. We pass NULL for simplicity.
    // printf("\nCalling mbedtls_mpi_exp_mod...\n");
    ret = mbedtls_mpi_exp_mod(&X_result, &A_base, &E_exponent, &N_modulus, NULL);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_exp_mod() failed with %d\n", ret);
        goto cleanup;
    }

    // 4. Print the result X_result
    #ifdef PRINT
    mbedtls_mpi_write_file("Result X_result:     ", &X_result, 10, NULL); // Print X_result to console in decimal
    #endif

cleanup:
    // 5. Free memory occupied by MPI variables
    // It's crucial to free the memory allocated for each mbedtls_mpi object
    // when they are no longer needed to prevent memory leaks.
    mbedtls_mpi_free(&X_result);
    mbedtls_mpi_free(&N_modulus);
    mbedtls_mpi_free(&E_exponent);
    mbedtls_mpi_free(&A_base);

    // Return success or failure based on the operation's outcome
    return (ret == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}