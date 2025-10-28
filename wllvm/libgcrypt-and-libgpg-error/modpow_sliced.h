#ifndef MODPOW_SLICED_H
#define MODPOW_SLICED_H

#include <gcrypt.h>

void _gcry_mpi_powm_slice_1(gcry_mpi_t res, gcry_mpi_t base, gcry_mpi_t expo,
                            gcry_mpi_t mod);

#endif
