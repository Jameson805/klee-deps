#define MBEDTLS_ALLOW_PRIVATE_ACCESS
#include "mbedtls/bignum.h"

#include "klee/klee.h"
#include "assert.h"

#define SYM_SIZE 4
unsigned char N_buf[SYM_SIZE];

#define ciL    (sizeof(mbedtls_mpi_uint))         /* chars in limb  */
#define biL    (ciL << 3)               /* bits  in limb  */
#define biH    (ciL << 2)               /* half limb size */

int main()
{
    klee_make_symbolic(N_buf, SYM_SIZE, "N_buf");
    klee_assume(N_buf[SYM_SIZE - 1] & 1);

    mbedtls_mpi N, RR;
    
    mbedtls_mpi_init(&N);
    mbedtls_mpi_init(&RR);

    int ret;
    MBEDTLS_MPI_CHK( mbedtls_mpi_read_binary(&N,  N_buf, SYM_SIZE) );
    MBEDTLS_MPI_CHK( mbedtls_mpi_lset( &RR, 1 ) );
    MBEDTLS_MPI_CHK( mbedtls_mpi_shift_l( &RR, N.n * 2 * biL ) );
    MBEDTLS_MPI_CHK( mbedtls_mpi_mod_mpi( &RR, &RR, &N ) );

cleanup:
    mbedtls_mpi_free(&N);
    klee_assert(ret == 0);
    return ret;
}
