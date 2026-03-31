#include "common.h"
#include <openssl/bn.h>

#if RECP + MONT + MONT_CONSTTIME + MONT_WORD != 1
  #error "You must define *exactly one* of RECP, MONT, MONT_CONSTTIME, or MONT_WORD."
#endif

/* Convert the least-significant bytes of a big-endian buffer to BN_ULONG.
   Takes the tail min(len, sizeof(BN_ULONG)) bytes and ignores any higher bytes. */
static BN_ULONG be_tail_to_bn_ulong(const unsigned char *buf, size_t len) {
    BN_ULONG v = 0;
    size_t n = sizeof(BN_ULONG);
    if (len < n) n = len;
    for (size_t i = 0; i < n; i++) {
        v = (v << 8) | (BN_ULONG)buf[len - n + i];
    }
    return v;
}

int driver_main(const unsigned char *exp_buf, const unsigned char *base_buf, const unsigned char *mod_buf, size_t len)
{
    BIGNUM *base = BN_new();
    BIGNUM *exp = BN_new();
    BIGNUM *mod = BN_new();
    BIGNUM *result = BN_new();
    BN_CTX *ctx = BN_CTX_new();

    if (!base || !exp || !mod || !result || !ctx) {
        fprintf(stderr, "ERROR: BN_new/BN_CTX_new failed\n");
        goto fail;
    }

    if (!BN_bin2bn(base_buf, len, base)) {
        fprintf(stderr, "ERROR: BN_bin2bn(base) failed\n");
        goto fail;
    }
    if (!BN_bin2bn(exp_buf, len, exp)) {
        fprintf(stderr, "ERROR: BN_bin2bn(exponent) failed\n");
        goto fail;
    }
    if (!BN_bin2bn(mod_buf, len, mod)) {
        fprintf(stderr, "ERROR: BN_bin2bn(modulus) failed\n");
        goto fail;
    }

    #ifdef SELF_COMP
        branchRecordingEnabled = 1;
    #endif

    #if defined(RECP)
        if (!BN_mod_exp_recp(result, base, exp, mod, ctx)) {
            fprintf(stderr, "ERROR: BN_mod_exp_recp failed\n");
            goto fail;
        }
    #elif defined(MONT)
        if (!BN_mod_exp_mont(result, base, exp, mod, ctx, NULL)) {
            fprintf(stderr, "ERROR: BN_mod_exp_mont failed\n");
            goto fail;
        }
    #elif defined(MONT_CONSTTIME)
        if (!BN_mod_exp_mont_consttime(result, base, exp, mod, ctx, NULL)) {
            fprintf(stderr, "ERROR: BN_mod_exp_mont_consttime failed\n");
            goto fail;
        }
    #elif defined(MONT_WORD)
        {
            BN_ULONG a = be_tail_to_bn_ulong(base_buf, len);
            if (!BN_mod_exp_mont_word(result, a, exp, mod, ctx, NULL)) {
                fprintf(stderr, "ERROR: BN_mod_exp_mont_word failed\n");
                goto fail;
            }
        }
    #endif

    #ifdef SELF_COMP
        branchRecordingEnabled = 0;
    #endif

    BN_free(result);
    BN_free(mod);
    BN_free(exp);
    BN_free(base);
    BN_CTX_free(ctx);
    return 0;

fail:
    #ifdef SELF_COMP
        branchRecordingEnabled = 0;
    #endif

    if (result)  BN_free(result);
    if (mod) BN_free(mod);
    if (exp)BN_free(exp);
    if (base)    BN_free(base);
    if (ctx)     BN_CTX_free(ctx);
    return 1;
}
