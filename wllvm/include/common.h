#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>

#if KLEE_CF + REPLAY + BINSEC + ABACUS != 1
  #error "You must define *exactly one* of KLEE_CF, REPLAY, BINSEC, or ABACUS."
#endif

#ifdef KLEE_CF
    #include "klee/klee.h"
#endif

#ifdef ABACUS
    #define CONCRETE_PUBS
    int __attribute__((optimize(0)))
    abacus_make_symbolic(char *name, void *addr, uint32_t length) {
        return 1;
    }
#endif

/* Returns nonzero if any byte in buf is nonzero */
static unsigned buf_nonzero(const unsigned char *buf, size_t size) {
    unsigned v = 0;
    for (size_t i = 0; i < size; ++i)
        v |= buf[i];
    return v;
}

/* Compute bit-length of big-endian unsigned integer stored in buf (MSB at index 0).
   Returns 0 if all bits are zero.
   Constant-time: no data-dependent branches or memory accesses. */
static unsigned buf_bitlen(const unsigned char *buf, size_t size) {
    unsigned found = 0;   /* becomes 1 once any '1' bit is found */
    unsigned bitpos = 0;  /* stores the highest set bit position */

    /* Iterate from most-significant bit to least-significant bit */
    for (size_t i = 0; i < size; i++) {
        for (int j = 7; j >= 0; --j) {
            unsigned bit = (buf[i] >> j) & 1u;
            unsigned curpos = (unsigned)((size - 1 - i) * 8u + (unsigned)j);
            unsigned set = bit & (1u - found);  /* first time we see a 1 from the MSB */
            bitpos = (set * curpos) | ((1u - set) * bitpos);
            found |= bit;
        }
    }

    /* bitlen = found ? bitpos + 1 : 0 */
    return found * (bitpos + 1u);
}

/* Store 16-bit big-endian value at end of buffer; zero pad leading bytes. */
static void be_store_u16_tail(unsigned char *dst, size_t dst_len, uint16_t x) {
    assert(dst_len >= 2);
    memset(dst, 0, dst_len);
    for (int i = 0; i < 2; ++i) {
        dst[dst_len - 2 + i] = (unsigned char)((x >> (8 * (1 - i))) & 0xFF);
    }
}

/* Store 32-bit big-endian value at end of buffer; zero pad leading bytes. */
static void be_store_u32_tail(unsigned char *dst, size_t dst_len, uint32_t x) {
    assert(dst_len >= 4);
    memset(dst, 0, dst_len);
    for (int i = 0; i < 4; ++i) {
        dst[dst_len - 4 + i] = (unsigned char)((x >> (8 * (3 - i))) & 0xFF);
    }
}

/* Store 64-bit big-endian value at end of buffer; zero pad leading bytes. */
static void be_store_u64_tail(unsigned char *dst, size_t dst_len, uint64_t x) {
    assert(dst_len >= 8);
    memset(dst, 0, dst_len);
    for (int i = 0; i < 8; ++i) {
        dst[dst_len - 8 + i] = (unsigned char)((x >> (8 * (7 - i))) & 0xFF);
    }
}

static int load_bytes(const char *filename, void *buf, size_t size)
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

#if SYM_SIZE != 2 && SYM_SIZE != 4 && SYM_SIZE != 8
  #error "You must define SYM_SIZE to one of 2, 4, or 8."
#endif
static unsigned char exp_buf[SYM_SIZE];
static unsigned char base_buf[SYM_SIZE];
static unsigned char mod_buf[SYM_SIZE];

/* User-provided entry that consumes the prepared buffers. */
int driver_main(const unsigned char *exp_buf, const unsigned char *base_buf, const unsigned char *mod_buf, size_t len);

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

    #ifdef KLEE_CF
        klee_make_symbolic_sc(exp_buf, sizeof(exp_buf), "exp", 1);
        // exp_buf > 0
        klee_assume(buf_nonzero(exp_buf, SYM_SIZE) != 0);

        unsigned int bitlen;
        klee_make_symbolic_sc(&bitlen, sizeof(bitlen), "exp_bitlen", 0);
        // exp and exp' must be of the same bit length
        klee_assume(buf_bitlen(exp_buf, SYM_SIZE) == bitlen);
    #elif defined(REPLAY)
        if (!load_bytes(exp_filename, exp_buf, sizeof(exp_buf))) return 1;
    #elif defined(ABACUS)
        char *type = "1";
        abacus_make_symbolic(type, &exp_buf, sizeof(exp_buf));
    #endif

    #ifdef CONCRETE_PUBS
        #if SYM_SIZE == 2
            uint16_t base_i = 251; // Closest prime less than uint8_t max
            uint16_t mod_i = 65521; // Closest prime less than uint16_t max
            be_store_u16_tail(base_buf, sizeof(base_buf), base_i);
            be_store_u16_tail(mod_buf, sizeof(mod_buf), mod_i);
        #elif SYM_SIZE == 4
            uint32_t base_i = 251; // Closest prime less than uint8_t max
            uint32_t mod_i = 4294967291; // Closest prime less than uint32_t max
            be_store_u32_tail(base_buf, sizeof(base_buf), base_i);
            be_store_u32_tail(mod_buf, sizeof(mod_buf), mod_i);
        #elif SYM_SIZE == 8
            uint64_t base_i = 251; // Closest prime less than uint8_t max
            uint64_t mod_i = 18446744073709551557; // Closest prime less than uint64_t max
            be_store_u64_tail(base_buf, sizeof(base_buf), base_i);
            be_store_u64_tail(mod_buf, sizeof(mod_buf), mod_i);
        #endif
    #else
        #ifdef KLEE_CF
            klee_make_symbolic_sc(base_buf, sizeof(base_buf), "base", 0);
            klee_make_symbolic_sc(mod_buf, sizeof(mod_buf), "mod", 0);
            // base_buf > 0 and mod_buf > 0
            klee_assume(buf_nonzero(base_buf, SYM_SIZE) != 0);
            klee_assume(buf_nonzero(mod_buf, SYM_SIZE) != 0);
            // mod_buf is odd
            klee_assume(mod_buf[SYM_SIZE - 1] & 1);
        #elif defined(REPLAY)
            if (!load_bytes(base_filename, base_buf, sizeof(base_buf))) return 1;
            if (!load_bytes(mod_filename, mod_buf, sizeof(mod_buf))) return 1;
        #endif
    #endif

    exit(driver_main(exp_buf, base_buf, mod_buf, SYM_SIZE));
}

#endif // COMMON_H
