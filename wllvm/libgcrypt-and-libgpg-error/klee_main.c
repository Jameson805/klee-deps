#include <gcrypt.h>
#include <klee/klee.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define SYM_SIZE 8
#define CONCRETE_PUBS

int main() {
    // Allocate symbolic buffers for base, exponent, and modulus
    unsigned char base_buf[SYM_SIZE];
    unsigned char exp_buf[SYM_SIZE];
    unsigned char mod_buf[SYM_SIZE];

    #ifdef CONCRETE_PUBS
        uint32_t base_i = 100003;
        memset(base_buf, 0, sizeof(base_buf));
        memcpy(base_buf, &base_i, sizeof(base_i));
    #else
        klee_make_symbolic_sc(base_buf, sizeof(base_buf), "base", 0);
    #endif

    klee_make_symbolic_sc(exp_buf, sizeof(exp_buf), "exp", 1);

    #ifdef CONCRETE_PUBS
        uint32_t mod_i = 1000000007;
        memset(mod_buf, 0, sizeof(mod_buf));
        memcpy(mod_buf, &mod_i, sizeof(mod_i));
    #else
        klee_make_symbolic_sc(mod_buf, sizeof(mod_buf), "mod", 0);
    #endif

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
