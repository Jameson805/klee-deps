#include <gcrypt.h>    
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

/* Frama-C nondeterministic interval helper */
extern int Frama_C_interval(int a, int b);


int main(void)
{
    /* Nondeterministic small values for base, exponent, and modulus */
    unsigned long A = (unsigned long) Frama_C_interval(-100, 100);
    unsigned long E = (unsigned long) Frama_C_interval(0, 10);
    unsigned long N = (unsigned long) Frama_C_interval(2, 100);

    /* Initialize big integers using stubs */
    gcry_mpi_t base   = gcry_mpi_new(256);
    gcry_mpi_t exp    = gcry_mpi_new(256);
    gcry_mpi_t mod    = gcry_mpi_new(256);
    gcry_mpi_t result = gcry_mpi_new(256);

    if (!base || !exp || !mod || !result) {
        return 2;
    }

    /* Set the integer values */
    gcry_mpi_set_ui(base, A);
    gcry_mpi_set_ui(exp,  E);
    gcry_mpi_set_ui(mod,  N);

    /* Call the real function to be sliced */
    gcry_mpi_powm(result, base, exp, mod);

    gcry_mpi_release(base);
    gcry_mpi_release(exp);
    gcry_mpi_release(mod);
    gcry_mpi_release(result);

    return 0;
}
