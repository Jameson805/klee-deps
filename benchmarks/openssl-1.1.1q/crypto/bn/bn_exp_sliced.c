/*
 * Copyright 1995-2022 The OpenSSL Project Authors. All Rights Reserved.
 *
 * Licensed under the OpenSSL license (the "License").  You may not use
 * this file except in compliance with the License.  You can obtain a copy
 * in the file LICENSE in the source distribution or at
 * https://www.openssl.org/source/license.html
 */

#include "internal/cryptlib.h"
#include "internal/constant_time.h"
#include "bn_local.h"

#include <stdlib.h>
#ifdef _WIN32
# include <malloc.h>
# ifndef alloca
#  define alloca _alloca
# endif
#elif defined(__GNUC__)
# ifndef alloca
#  define alloca(s) __builtin_alloca((s))
# endif
#elif defined(__sun)
# include <alloca.h>
#endif

#include "rsaz_exp.h"

#undef SPARC_T4_MONT
#if defined(OPENSSL_BN_ASM_MONT) && (defined(__sparc__) || defined(__sparc))
# include "sparc_arch.h"
extern unsigned int OPENSSL_sparcv9cap_P[];
# define SPARC_T4_MONT
#endif
#define TABLE_SIZE      32

int BN_mod_exp(BIGNUM *r, const BIGNUM *a, const BIGNUM *p, const BIGNUM *m,
               BN_CTX *ctx)
{
    int ret;

    bn_check_top(a);
    bn_check_top(p);
    bn_check_top(m);

    /*-
     * For even modulus  m = 2^k*m_odd, it might make sense to compute
     * a^p mod m_odd  and  a^p mod 2^k  separately (with Montgomery
     * exponentiation for the odd part), using appropriate exponent
     * reductions, and combine the results using the CRT.
     *
     * For now, we use Montgomery only if the modulus is odd; otherwise,
     * exponentiation using the reciprocal-based quick remaindering
     * algorithm is used.
     *
     * (Timing obtained with expspeed.c [computations  a^p mod m
     * where  a, p, m  are of the same length: 256, 512, 1024, 2048,
     * 4096, 8192 bits], compared to the running time of the
     * standard algorithm:
     *
     *   BN_mod_exp_mont   33 .. 40 %  [AMD K6-2, Linux, debug configuration]
     *                     55 .. 77 %  [UltraSparc processor, but
     *                                  debug-solaris-sparcv8-gcc conf.]
     *
     *   BN_mod_exp_recp   50 .. 70 %  [AMD K6-2, Linux, debug configuration]
     *                     62 .. 118 % [UltraSparc, debug-solaris-sparcv8-gcc]
     *
     * On the Sparc, BN_mod_exp_recp was faster than BN_mod_exp_mont
     * at 2048 and more bits, but at 512 and 1024 bits, it was
     * slower even than the standard algorithm!
     *
     * "Real" timings [linux-elf, solaris-sparcv9-gcc configurations]
     * should be obtained when the new Montgomery reduction code
     * has been integrated into OpenSSL.)
     */

#define MONT_MUL_MOD
#define MONT_EXP_WORD
#define RECP_MUL_MOD

#ifdef MONT_MUL_MOD
    if (BN_is_odd(m)) {
# ifdef MONT_EXP_WORD
        if (a->top == 1 && !a->neg
            && (BN_get_flags(p, BN_FLG_CONSTTIME) == 0)
            && (BN_get_flags(a, BN_FLG_CONSTTIME) == 0)
            && (BN_get_flags(m, BN_FLG_CONSTTIME) == 0)) {
            BN_ULONG A = a->d[0];
            ret = BN_mod_exp_mont_word(r, A, p, m, ctx, NULL);
        } else
# endif
            ret = BN_mod_exp_mont(r, a, p, m, ctx, NULL);
    } else
#endif
#ifdef RECP_MUL_MOD
    {
        ret = BN_mod_exp_recp(r, a, p, m, ctx);
    }
#else
    {
        ret = BN_mod_exp_simple(r, a, p, m, ctx);
    }
#endif

    bn_check_top(r);
    return ret;
}

int BN_mod_exp_recp(BIGNUM *r, const BIGNUM *a, const BIGNUM *p,
                    const BIGNUM *m, BN_CTX *ctx)
{
    int i, j, bits, ret = 0, wstart, wend, window, wvalue;
    int start = 1;
    BIGNUM *aa;
    BIGNUM *val[TABLE_SIZE];
    BN_RECP_CTX recp;
    bits = BN_num_bits(p);
    if (bits == 0)
        return 0;
    BN_RECP_CTX_init(&recp);
    BN_CTX_start(ctx);
    aa = BN_CTX_get(ctx);
    val[0] = BN_CTX_get(ctx);
    if (val[0] == NULL)
        return 0;
    if (m->neg) {
        if (!BN_copy(aa, m))
            return 0;
        aa->neg = 0;
        if (BN_RECP_CTX_set(&recp, aa, ctx) <= 0)
            return 0;
    } else {
        if (BN_RECP_CTX_set(&recp, m, ctx) <= 0)
            return 0;
    }
    if (!BN_nnmod(val[0], a, m, ctx))
        return 0;         
    if (BN_is_zero(val[0]))
        return 0;
    window = BN_window_bits_for_exponent_size(bits);
    if (window > 1) {
        if (!BN_mod_mul_reciprocal(aa, val[0], val[0], &recp, ctx))
            return 0;          
        j = 1 << (window - 1);
        for (i = 1; i < j; i++) {
            if (((val[i] = BN_CTX_get(ctx)) == NULL) ||
                !BN_mod_mul_reciprocal(val[i], val[i - 1], aa, &recp, ctx))
                return 0;
        }
    }
    start = 1;                    
    wvalue = 0;
    wstart = bits - 1;        
    wend = 0;                  
    if (!BN_one(r))
        return 0;
    for (;;) {
        // @slice_preserve_ctrl;
        // @slice_preserve_stmt;
        if (BN_is_bit_set(p, wstart) == 0) {
            if (!start)
                if (!BN_mod_mul_reciprocal(r, r, r, &recp, ctx))
                    return 0;
            if (wstart == 0)
                break;
            wstart--;
            continue;
        }
        j = wstart;
        wvalue = 1;
        wend = 0;
        for (i = 1; i < window; i++) {
            if (wstart - i < 0)
                break;
            // @slice_preserve_ctrl;
            // @slice_preserve_stmt;
            if (BN_is_bit_set(p, wstart - i)) {
                wvalue <<= (i - wend);
                wvalue |= 1;
                wend = i;
            }
        }
        j = wend + 1;
        if (!start)
            for (i = 0; i < j; i++) {
                if (!BN_mod_mul_reciprocal(r, r, r, &recp, ctx))
                    return 0;
            }
        if (!BN_mod_mul_reciprocal(r, r, val[wvalue >> 1], &recp, ctx))
            return 0;
        wstart -= wend + 1;
        wvalue = 0;
        start = 0;
        if (wstart < 0)
            break;
    }
    return 1;
}

int BN_mod_exp_mont(BIGNUM *rr, const BIGNUM *a, const BIGNUM *p,
                    const BIGNUM *m, BN_CTX *ctx, BN_MONT_CTX *in_mont)
{
    int i, j, bits, wstart, wend, window, wvalue;
    int start = 1;
    BIGNUM *d, *r;
    const BIGNUM *aa;
    BIGNUM *val[TABLE_SIZE];
    BN_MONT_CTX *mont = NULL;
    if (!BN_is_odd(m))
        return 0;
    bits = BN_num_bits(p);
    if (bits == 0)
        return 0;
    BN_CTX_start(ctx);
    d = BN_CTX_get(ctx);
    r = BN_CTX_get(ctx);
    val[0] = BN_CTX_get(ctx);
    if (val[0] == NULL)
        return 0;
    if (in_mont != NULL)
        mont = in_mont;
    else {
        if ((mont = BN_MONT_CTX_new()) == NULL)
            return 0;
        if (!BN_MONT_CTX_set(mont, m, ctx))
            return 0;
    }
    // slice_preserve_ctrl;
    // slice_preserve_stmt;
    if (a->neg || BN_ucmp(a, m) >= 0) {
        if (!BN_nnmod(val[0], a, m, ctx))
            return 0;
        aa = val[0];
    } else
        aa = a;
    if (!bn_to_mont_fixed_top(val[0], aa, mont, ctx))
        return 0;               
    window = BN_window_bits_for_exponent_size(bits);
    if (window > 1) {
        if (!bn_mul_mont_fixed_top(d, val[0], val[0], mont, ctx))
            return 0;         
        j = 1 << (window - 1);
        for (i = 1; i < j; i++) {
            if (((val[i] = BN_CTX_get(ctx)) == NULL) ||
                !bn_mul_mont_fixed_top(val[i], val[i - 1], d, mont, ctx))
                return 0;
        }
    }
    start = 1;                  
    wvalue = 0;                
    wstart = bits - 1;         
    wend = 0;       
    j = m->top;             
    if (m->d[j - 1] & (((BN_ULONG)1) << (BN_BITS2 - 1))) {
        if (bn_wexpand(r, j) == NULL)
            return 0;
    } 
    if (!bn_to_mont_fixed_top(r, BN_value_one(), mont, ctx))
        return 0;
    for (;;) {
        // slice_preserve_ctrl;
        // slice_preserve_stmt;
        if (BN_is_bit_set(p, wstart) == 0) {
            if (!start) {
                if (!bn_mul_mont_fixed_top(r, r, r, mont, ctx))
                    return 0;
            }
            if (wstart == 0)
                break;
            wstart--;
            continue;
        }
        j = wstart;
        wvalue = 1;
        wend = 0;
        for (i = 1; i < window; i++) {
            if (wstart - i < 0)
                break;
            // slice_preserve_ctrl;
            // slice_preserve_stmt;
            if (BN_is_bit_set(p, wstart - i)) {
                wvalue <<= (i - wend);
                wvalue |= 1;
                wend = i;
            }
        }
        j = wend + 1;
        if (!start)
            for (i = 0; i < j; i++) {
                if (!bn_mul_mont_fixed_top(r, r, r, mont, ctx))
                    return 0;
            }
        if (!bn_mul_mont_fixed_top(r, r, val[wvalue >> 1], mont, ctx))
            return 0;
        wstart -= wend + 1;
        wvalue = 0;
        start = 0;
        if (wstart < 0)
            break;
    }
    return 1;
}

int BN_mod_exp_mont_word(BIGNUM *rr, BN_ULONG a, const BIGNUM *p,
                         const BIGNUM *m, BN_CTX *ctx, BN_MONT_CTX *in_mont)
{
    BN_MONT_CTX *mont = NULL;
    int b, bits;
    int r_is_one;
    BN_ULONG w, next_w;
    BIGNUM *r, *t;
    BIGNUM *swap_tmp;
#define BN_MOD_MUL_WORD(r, w, m) \
                (BN_mul_word(r, (w)) && \
                ((BN_mod(t, r, m, ctx) && (swap_tmp = r, r = t, t = swap_tmp, 1))))
#define BN_TO_MONTGOMERY_WORD(r, w, mont) \
                (BN_set_word(r, (w)) && BN_to_montgomery(r, r, (mont), ctx))
    if (BN_get_flags(p, BN_FLG_CONSTTIME) != 0
            || BN_get_flags(m, BN_FLG_CONSTTIME) != 0) 
        return 0;
    if (!BN_is_odd(m)) 
        return 0;       
    bits = BN_num_bits(p);
    if (bits == 0)
        return 0;
    if (a == 0)
        return 0;
    BN_CTX_start(ctx);
    r = BN_CTX_get(ctx);
    t = BN_CTX_get(ctx);
    if (t == NULL)
        return 0;
    if (in_mont != NULL)
        mont = in_mont;
    else {
        if ((mont = BN_MONT_CTX_new()) == NULL)
            return 0;
        if (!BN_MONT_CTX_set(mont, m, ctx))
            return 0;
    }
    r_is_one = 1;        
    w = a;                     
    for (b = bits - 2; b >= 0; b--) {
        next_w = w * w;
        if ((next_w / w) != w) {
            if (r_is_one) {
                if (!BN_TO_MONTGOMERY_WORD(r, w, mont))
                    return 0;
                r_is_one = 0;
            } else {
                if (!BN_MOD_MUL_WORD(r, w, m))
                    return 0;
            }
            next_w = 1;
        }
        w = next_w;
        if (!r_is_one) {
            if (!BN_mod_mul_montgomery(r, r, r, mont, ctx))
                return 0;
        }
        // @slice_preserve_ctrl;
        // @slice_preserve_stmt;
        if (BN_is_bit_set(p, b)) {
            next_w = w * a;
            if ((next_w / a) != w) { 
                if (r_is_one) {
                    if (!BN_TO_MONTGOMERY_WORD(r, w, mont))
                        return 0;
                    r_is_one = 0;
                } else {
                    if (!BN_MOD_MUL_WORD(r, w, m))
                        return 0;
                }
                next_w = a;
            }
            w = next_w;
        }
    }
    return 1;
}

// mod_exp_mont_consttime omitted for now

int BN_mod_exp_mont_consttime(BIGNUM *rr, const BIGNUM *a, const BIGNUM *p,
                              const BIGNUM *m, BN_CTX *ctx,
                              BN_MONT_CTX *in_mont)
{
    return 0;
}
