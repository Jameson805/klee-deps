#ifndef BIGNUM_238_SLICED_H
#define BIGNUM_238_SLICED_H

#include "mbedtls3.2.1/include/mbedtls/bignum.h"

void mbedtls_mpi_exp_mod_slice_1(mbedtls_mpi *X, const mbedtls_mpi *A,
                                 const mbedtls_mpi *E, const mbedtls_mpi *N);

#endif
