#include "runner_config.generated.h"
#include "Hacl_Bignum64.h"

#include <stdint.h>
#include <stdlib.h>

int driver_main(void)
{
    uint32_t limb_len = (uint32_t)((sizeof(mod_buf) + sizeof(uint64_t) - 1) / sizeof(uint64_t));
    uint64_t *modulus = Hacl_Bignum64_new_bn_from_bytes_be((uint32_t)sizeof(mod_buf), mod_buf);
    uint64_t *base = Hacl_Bignum64_new_bn_from_bytes_be((uint32_t)sizeof(base_buf), base_buf);
    uint64_t *exponent = Hacl_Bignum64_new_bn_from_bytes_be((uint32_t)sizeof(exp_buf), exp_buf);
    uint64_t *result = (uint64_t *)calloc(limb_len, sizeof(uint64_t));
    bool ok = false;

    if (modulus == NULL || base == NULL || exponent == NULL || result == NULL) {
        free(result);
        free(exponent);
        free(base);
        free(modulus);
        return 1;
    }

    ok = Hacl_Bignum64_mod_exp_consttime(
        limb_len,
        modulus,
        base,
        (uint32_t)(sizeof(exp_buf) * 8U),
        exponent,
        result
    );

    free(result);
    free(exponent);
    free(base);
    free(modulus);
    return ok ? 0 : 1;
}