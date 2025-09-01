#include <gcrypt.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define SYM_SIZE 32
// Allocate symbolic buffers for base, exponent, and modulus
unsigned char base_buf[SYM_SIZE];
unsigned char exp_buf[SYM_SIZE];
unsigned char mod_buf[SYM_SIZE];

int main() {
    // Parse symbolic buffers into gcry_mpi_t big numbers
    gcry_mpi_t base, exp, mod, result;
    if (gcry_mpi_scan(&base, GCRYMPI_FMT_USG, base_buf, SYM_SIZE, NULL) != 0)
        return 2;
    if (gcry_mpi_scan(&exp, GCRYMPI_FMT_USG, exp_buf, SYM_SIZE, NULL) != 0)
        return 3;
    if (gcry_mpi_scan(&mod, GCRYMPI_FMT_USG, mod_buf, SYM_SIZE, NULL) != 0)
        return 4;

    result = gcry_mpi_new(SYM_SIZE * 8);

    // Perform modular exponentiation
    gcry_mpi_powm(result, base, exp, mod);

    // Free memory
    gcry_mpi_release(base);
    gcry_mpi_release(exp);
    gcry_mpi_release(mod);
    gcry_mpi_release(result);

    return 0;
}
