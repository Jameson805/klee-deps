#include "runner_config.generated.h"

#include <openssl/bn.h>

#include "openssl_rsa_benchmark_common.h"

int driver_main(void)
{
    RSA *rsa = NULL;
    BIGNUM *input = NULL;
    BIGNUM *result = NULL;
    BN_CTX *ctx = NULL;
    unsigned char normalized[sizeof(ciphertext_buf)];
    unsigned char output[sizeof(ciphertext_buf)];
    volatile unsigned char sink = 0;

    rsa = load_symbolic_crt_key(dp_buf, sizeof(dp_buf), dq_buf, sizeof(dq_buf));
    if (rsa == NULL) {
        goto fail;
    }
    if (!normalize_ciphertext(rsa, ciphertext_buf, sizeof(ciphertext_buf),
                              normalized, sizeof(normalized))) {
        goto fail;
    }

    ctx = BN_CTX_new();
    input = BN_bin2bn(normalized, (int) sizeof(normalized), NULL);
    result = BN_new();
    if (ctx == NULL || input == NULL || result == NULL) {
        goto fail;
    }

    if (!rsa->meth->rsa_mod_exp(result, input, rsa, ctx)) {
        goto fail;
    }
    if (BN_bn2binpad(result, output, sizeof(output)) != (int) sizeof(output)) {
        goto fail;
    }

    sink ^= output[0];
    (void) sink;
    BN_free(result);
    BN_free(input);
    BN_CTX_free(ctx);
    RSA_free(rsa);
    return 0;

fail:
    BN_free(result);
    BN_free(input);
    BN_CTX_free(ctx);
    RSA_free(rsa);
    return 1;
}
