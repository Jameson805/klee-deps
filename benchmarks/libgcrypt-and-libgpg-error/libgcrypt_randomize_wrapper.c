#include <gcrypt.h>

void __wrap__gcry_mpi_randomize(gcry_mpi_t mpi_value,
                                unsigned int nbits,
                                enum gcry_random_level level)
{
    (void) nbits;
    (void) level;
    gcry_mpi_set_ui(mpi_value, 0);
}