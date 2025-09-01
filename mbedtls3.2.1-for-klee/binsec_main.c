#include "bignum.h"
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>

int64_t A_input;
int64_t E_input;
int64_t N_input;

int main() {
    // Declare mbedtls_mpi variables for base (A_base), exponent (E_exponent), modulus (N_modulus), and result (X_result)
    mbedtls_mpi A_base, E_exponent, N_modulus, X_result;
    int ret; // For return codes of mbedtls functions

    // 1. Initialize MPI variables
    // This function allocates and initializes the internal structure of the MPI.
    mbedtls_mpi_init(&A_base);
    mbedtls_mpi_init(&E_exponent);
    mbedtls_mpi_init(&N_modulus);
    mbedtls_mpi_init(&X_result);

    // 2. Set values for A_base, E_exponent, and N_modulus using mbedtls_mpi_lset for simpler integer assignments.
    // We'll calculate X_result = A_base^E_exponent mod N_modulus

    // mbedtls_mpi_lset sets an MPI from a long integer.
    ret = mbedtls_mpi_lset(&A_base, A_input);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(A_base) failed with %d\n", ret);
        goto cleanup;
    }

    // #define PRINT

    ret = mbedtls_mpi_lset(&E_exponent, E_input);
    if (ret != 0) {
        printf("ERROR: mbedtls_mpi_lset(E_exponent) failed with %d\n", ret);
        goto cleanup;
    }

    ret = mbedtls_mpi_lset(&N_modulus, N_input);
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
    exit(ret);
}