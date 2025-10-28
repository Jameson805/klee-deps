#include <openssl/bn.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

#if RECP + MONT + MONT_CONSTTIME + MONT_WORD != 1
  #error "You must define *exactly one* of RECP, MONT, MONT_CONSTTIME, or MONT_WORD."
#endif

#ifndef REPLAY
    #include "klee/klee.h"
#endif

#define SYM_SIZE 8

/* Returns nonzero if any byte in buf is nonzero */
unsigned buf_nonzero(const unsigned char *buf, size_t size) {
    unsigned v = 0;
    for (size_t i = 0; i < size; ++i)
        v |= buf[i];
    return v;
}

/* Compute bit-length of big-endian unsigned integer stored in buf (MSB at index 0).
   Returns 0 if all bits are zero.
   Constant-time: no data-dependent branches or memory accesses. */
unsigned buf_bitlen(const unsigned char *buf, size_t size) {
    unsigned found = 0;   /* becomes 1 once any '1' bit is found */
    unsigned bitpos = 0;  /* stores the highest set bit position */

    /* Iterate from most-significant bit to least-significant bit */
    for (size_t i = 0; i < size; i++) {
        for (int j = 7; j >= 0; --j) {
            unsigned bit = (buf[i] >> j) & 1u;
            unsigned curpos = (unsigned)((size - 1 - i) * 8u + j);
            unsigned set = bit & (1u - found);  /* first time we see a 1 from the MSB */
            bitpos = (set * curpos) | ((1u - set) * bitpos);
            found |= bit;
        }
    }

    /* bitlen = found ? bitpos + 1 : 0 */
    return found * (bitpos + 1u);
}

void be_store_u64_tail(unsigned char *dst, size_t dst_len, uint64_t x) {
    memset(dst, 0, dst_len);
    for (int i = 0; i < 8; ++i) {
        dst[dst_len - 8 + i] = (unsigned char)((x >> (8 * (7 - i))) & 0xFF);
    }
}

int load_bytes(const char *filename, void *buf, size_t size)
{
    FILE *f = fopen(filename, "rb");
    if (!f) {
        printf("ERROR: unable to open file %s\n", filename);
        return 0;
    }

    if (fread(buf, 1, size, f) != size) {
        printf("ERROR: reading file %s\n", filename);
        fclose(f);
        return 0;
    }

    fclose(f);
    return 1;
}

int main(int argc, char *argv[]) {
    #ifdef REPLAY
        #ifdef CONCRETE_PUBS
            assert(argc == 2 && "Required arguments: <exp_filename>");
            char *exp_filename = argv[1];
        #else
            assert(argc == 4 && "Required arguments: <exp_filename> <base_filename> <mod_filename>");
            char *exp_filename = argv[1];
            char *base_filename = argv[2];
            char *mod_filename = argv[3];
        #endif
    #endif

    unsigned char base_buf[SYM_SIZE];
    unsigned char exp_buf[SYM_SIZE];
    unsigned char mod_buf[SYM_SIZE];

    #ifdef REPLAY
        if (!load_bytes(exp_filename, exp_buf, sizeof(exp_buf))) return 1;
    #else
        klee_make_symbolic_sc(exp_buf, sizeof(exp_buf), "exp", 1);
        // exp_buf > 0
        klee_assume(buf_nonzero(exp_buf, SYM_SIZE) != 0);

        unsigned int bitlen;
        klee_make_symbolic_sc(&bitlen, sizeof(bitlen), "exp_bitlen", 0);
        // exp and exp' must be of the same bit length
        klee_assume(buf_bitlen(exp_buf, SYM_SIZE) == bitlen);
    #endif

    #ifdef MONT_WORD
        uint64_t base_i;
        #ifdef CONCRETE_PUBS
            base_i = 100003;
        #else
            #ifdef REPLAY
                if (!load_bytes(base_filename, &base_i, sizeof(base_i))) return 1;
            #else
                klee_make_symbolic_sc(&base_i, sizeof(base_i), "base", 0);
                klee_assume(base_i > 0);
                klee_assume(base_i % 2 == 1);
            #endif
        #endif
    #else
        #ifdef CONCRETE_PUBS
            uint64_t base_i = 100003;
            be_store_u64_tail(base_buf, sizeof(base_buf), base_i);
        #else
            #ifdef REPLAY
                if (!load_bytes(base_filename, base_buf, sizeof(base_buf))) return 1;
            #else
                klee_make_symbolic_sc(base_buf, sizeof(base_buf), "base", 0);
                // base_buf > 0
                klee_assume(buf_nonzero(base_buf, SYM_SIZE) != 0);
            #endif
        #endif
    #endif

    #ifdef CONCRETE_PUBS
        uint64_t mod_i = 1000000007;
        be_store_u64_tail(mod_buf, sizeof(mod_buf), mod_i);
    #else
        #ifdef REPLAY
            if (!load_bytes(mod_filename, mod_buf, sizeof(mod_buf))) return 1;
        #else
            klee_make_symbolic_sc(mod_buf, sizeof(mod_buf), "mod", 0);
            // mod_buf > 0
            klee_assume(buf_nonzero(mod_buf, SYM_SIZE) != 0);
            // mod_buf is odd
            klee_assume(mod_buf[SYM_SIZE - 1] & 1);
        #endif
    #endif

    BIGNUM *base = BN_new();
    BIGNUM *exp = BN_new();
    BIGNUM *mod = BN_new();
    BIGNUM *res = BN_new();

    BN_CTX *ctx = BN_CTX_new();

    BN_bin2bn(base_buf, SYM_SIZE, base);
    BN_bin2bn(exp_buf, SYM_SIZE, exp);
    BN_bin2bn(mod_buf, SYM_SIZE, mod);

    if (
        #ifdef RECP
            !BN_mod_exp_recp(res, base, exp, mod, ctx)
        #elifdef MONT
            !BN_mod_exp_mont(res, base, exp, mod, ctx, NULL)
        #elifdef MONT_CONSTTIME
            !BN_mod_exp_mont_consttime(res, base, exp, mod, ctx, NULL)
        #elifdef MONT_WORD
            !BN_mod_exp_mont_word(res, base_i, exp, mod, ctx, NULL)
        #endif
       ) {
        #ifdef RECP
            printf("BN_mod_exp_recp failed\n");
        #elifdef MONT
            printf("BN_mod_exp_mont failed\n");
        #elifdef MONT_CONSTTIME
            printf("BN_mod_exp_mont_consttime failed\n");
        #elifdef MONT_WORD
            printf("BN_mod_exp_mont_word failed\n");
        #endif
        BN_free(base);
        BN_free(exp);
        BN_free(mod);
        BN_free(res);
        BN_CTX_free(ctx);
        return 1;
    }

    BN_free(base);
    BN_free(exp);
    BN_free(mod);
    BN_free(res);
    BN_CTX_free(ctx);

    return 0;
}
