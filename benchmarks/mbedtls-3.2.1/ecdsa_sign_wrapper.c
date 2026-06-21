#include "runner_config.generated.h"

#include <string.h>

#include "mbedtls/ecdsa.h"
#include "mbedtls/ecp.h"

struct nonce_rng_state {
    const unsigned char *bytes;
    size_t len;
};

static int secret_nonce_rng(void *rng_state, unsigned char *output, size_t len)
{
    struct nonce_rng_state *state = (struct nonce_rng_state *) rng_state;
    size_t copied = 0;

    while (copied < len) {
        size_t chunk = state->len;
        if (chunk > len - copied) {
            chunk = len - copied;
        }
        memcpy(output + copied, state->bytes, chunk);
        copied += chunk;
    }
    return 0;
}

int driver_main(void)
{
    int ret = 0;
    mbedtls_ecp_group group;
    mbedtls_mpi private_key;
    mbedtls_mpi signature_r;
    mbedtls_mpi signature_s;
    struct nonce_rng_state rng_state;
    volatile unsigned long sink = 0;

    mbedtls_ecp_group_init(&group);
    mbedtls_mpi_init(&private_key);
    mbedtls_mpi_init(&signature_r);
    mbedtls_mpi_init(&signature_s);

    ret = mbedtls_ecp_group_load(&group, MBEDTLS_ECP_DP_SECP192R1);
    if (ret != 0) {
        goto cleanup;
    }

    ret = mbedtls_mpi_read_binary(&private_key, private_key_buf, sizeof(private_key_buf));
    if (ret != 0) {
        goto cleanup;
    }

    rng_state.bytes = nonce_buf;
    rng_state.len = sizeof(nonce_buf);
    ret = mbedtls_ecdsa_sign(&group, &signature_r, &signature_s, &private_key,
                             digest_buf, sizeof(digest_buf),
                             secret_nonce_rng, &rng_state);
    if (ret != 0) {
        goto cleanup;
    }

    sink ^= mbedtls_mpi_get_bit(&signature_r, 0);
    sink ^= mbedtls_mpi_get_bit(&signature_s, 0);
    (void) sink;

cleanup:
    mbedtls_mpi_free(&signature_s);
    mbedtls_mpi_free(&signature_r);
    mbedtls_mpi_free(&private_key);
    mbedtls_ecp_group_free(&group);
    return ret == 0 ? 0 : 1;
}
