#include <gcrypt.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#include "modpow_sliced.h"

#ifndef REPLAY
    #include "klee/klee.h"
#endif

#define SYM_SIZE 2

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

int main(int argc, char *argv[]) {
    #ifdef REPLAY
        #ifdef CONCRETE_PUBS
            assert(argc == 2 && "Required arguments: <exp_filename>");
            char *exp_filename = argv[1];
        #else
            assert(argc == 4 && "Required arguments: <exp_filename> <base_filename> <mod_filename>");
            char *exp_filename = argv[1];
            char *base_filename = argv[2];
            char *mod_filename = argv[3];
        #endif
    #endif

    // Allocate symbolic buffers for exponent, base, and modulus
    unsigned char exp_buf[SYM_SIZE];
    unsigned char base_buf[SYM_SIZE];
    unsigned char mod_buf[SYM_SIZE];

    #ifdef REPLAY
        if (!load_bytes(exp_filename, exp_buf, sizeof(exp_buf))) return 1;
    #else
        klee_make_symbolic_sc(exp_buf, sizeof(exp_buf), "exp", 1);

        for (int i = 0; i < SYM_SIZE; i++) {
            klee_assume(exp_buf[i] != 0);
            klee_assume(exp_buf[i] <= 0x05);
        }
    #endif
    klee_warning("Reaches after exp");

    #ifdef CONCRETE_PUBS
        uint32_t base_i = 100003;
        memset(base_buf, 0, sizeof(base_buf));
        memcpy(base_buf, &base_i, sizeof(base_i));
    #else
        #ifdef REPLAY
            if (!load_bytes(base_filename, base_buf, sizeof(base_buf))) return 1;
        #else
            klee_make_symbolic_sc(base_buf, sizeof(base_buf), "base", 0);

            for (int i = 0; i < SYM_SIZE; i++) {
                klee_assume(base_buf[i] != 0); 
                klee_assume(base_buf[i] <= 0x2F); 
            }
        #endif
    #endif
    klee_warning("Reached after base");

    #ifdef CONCRETE_PUBS
        uint32_t mod_i = 1000000007;
        memset(mod_buf, 0, sizeof(mod_buf));
        memcpy(mod_buf, &mod_i, sizeof(mod_i));
    #else
        #ifdef REPLAY
            if (!load_bytes(mod_filename, mod_buf, sizeof(mod_buf))) return 1;
        #else
            klee_make_symbolic_sc(mod_buf, sizeof(mod_buf), "mod", 0);

            for (int i = 0; i < SYM_SIZE; i++) {
                klee_assume(mod_buf[i] != 0); 
                klee_assume(mod_buf[i] <= 0x0F); 
            }
            klee_assume(!(mod_buf[0] == 1 && mod_buf[1] == 0));
        #endif
    #endif

    klee_warning("Reaches all make symbolics");

    // Parse symbolic buffers into gcry_mpi_t big numbers
    gcry_mpi_t base, exp, mod, result;
    if (gcry_mpi_scan(&base, GCRYMPI_FMT_USG, base_buf, SYM_SIZE, NULL) != 0)
        return 2;
    if (gcry_mpi_scan(&exp, GCRYMPI_FMT_USG, exp_buf, SYM_SIZE, NULL) != 0)
        return 3;
    if (gcry_mpi_scan(&mod, GCRYMPI_FMT_USG, mod_buf, SYM_SIZE, NULL) != 0)
        return 4;

    klee_warning("Reaches all gcry_mpi_scan");


    result = gcry_mpi_new(SYM_SIZE * 8);

    // Perform modular exponentiation
    _gcry_mpi_powm_slice_1(result, base, exp, mod);

    // Free memory
    gcry_mpi_release(base);
    gcry_mpi_release(exp);
    gcry_mpi_release(mod);
    gcry_mpi_release(result);

    return 0;
}
