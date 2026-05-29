#include "runner_config.generated.h"
#include "Hacl_Bignum32.h"

#include <stdint.h>
#include <stdlib.h>

int driver_main(void)
{
    uint32_t limb_len = (uint32_t)((sizeof(mod_buf) + sizeof(uint32_t) - 1) / sizeof(uint32_t));
    uint32_t *modulus = Hacl_Bignum32_new_bn_from_bytes_be((uint32_t)sizeof(mod_buf), mod_buf);
    uint32_t *base = Hacl_Bignum32_new_bn_from_bytes_be((uint32_t)sizeof(base_buf), base_buf);
    uint32_t *exponent = Hacl_Bignum32_new_bn_from_bytes_be((uint32_t)sizeof(exp_buf), exp_buf);
    uint32_t *result = (uint32_t *)calloc(limb_len, sizeof(uint32_t));
    bool ok = false;

    if (modulus == NULL || base == NULL || exponent == NULL || result == NULL) {
        free(result);
        free(exponent);
        free(base);
        free(modulus);
        return 1;
    }

    ok = Hacl_Bignum32_mod_exp_consttime(
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