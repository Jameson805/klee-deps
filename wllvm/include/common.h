#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>


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

#if SYM_SIZE != 1 && SYM_SIZE != 2 && SYM_SIZE != 4 && SYM_SIZE != 8 && SYM_SIZE != 16
    #error "You must define SYM_SIZE to one of 1, 2, 4, 8, or 16."
#endif

#ifdef SELF_COMP

    #include "klee/klee.h"

    static unsigned char exp_1_buf[SYM_SIZE];
    static unsigned char exp_2_buf[SYM_SIZE];
    static unsigned char base_buf[SYM_SIZE];
    static unsigned char mod_buf[SYM_SIZE];

    #define MAX_BRANCH_RECORDS 65536

    typedef struct {
        int decision;
        const char *file;
        int line;
        int col;
    } BranchRecord;

    static BranchRecord branchRecords[MAX_BRANCH_RECORDS];
    static int branchRecordsLen;

    static BranchRecord branchRecords1[MAX_BRANCH_RECORDS];
    static int branchRecords1Len;

    void __record_branch(int decision, const char *file, int line, int col) {
        klee_assert(branchRecordsLen < MAX_BRANCH_RECORDS);
        branchRecords[branchRecordsLen].decision = decision;
        branchRecords[branchRecordsLen].file = file;
        branchRecords[branchRecordsLen].line = line;
        branchRecords[branchRecordsLen].col = col;
        branchRecordsLen++;
    }

    /* User-provided entry that consumes the prepared buffers. */
    int driver_main(const unsigned char *exp_buf, const unsigned char *base_buf, const unsigned char *mod_buf, size_t len);

    int main(int argc, char *argv[]) {
        klee_make_symbolic(exp_1_buf, SYM_SIZE, "exp_1");
        klee_make_symbolic(exp_2_buf, SYM_SIZE, "exp_2");
        klee_assume(exp_1_buf[0] & 0x80); // Set highest bit
        klee_assume(exp_2_buf[0] & 0x80); // Set highest bit

        #ifdef CONCRETE_PUBS
            #if SYM_SIZE == 1
                uint8_t base_i = 3;
                uint8_t mod_i = 251; // Closest prime less than uint8_t max
                base_buf[0] = base_i;
                mod_buf[0] = mod_i;
            #elif SYM_SIZE == 2
                uint16_t base_i = 251; // Closest prime less than uint8_t max
                uint16_t mod_i = 65521; // Closest prime less than uint16_t max
                be_store_u16_tail(base_buf, SYM_SIZE, base_i);
                be_store_u16_tail(mod_buf, SYM_SIZE, mod_i);
            #elif SYM_SIZE == 4
                uint32_t base_i = 251; // Closest prime less than uint8_t max
                uint32_t mod_i = 4294967291; // Closest prime less than uint32_t max
                be_store_u32_tail(base_buf, SYM_SIZE, base_i);
                be_store_u32_tail(mod_buf, SYM_SIZE, mod_i);
            #elif SYM_SIZE == 8
                uint64_t base_i = 251; // Closest prime less than uint8_t max
                uint64_t mod_i = 18446744073709551557; // Closest prime less than uint64_t max
                be_store_u64_tail(base_buf, SYM_SIZE, base_i);
                be_store_u64_tail(mod_buf, SYM_SIZE, mod_i);
            #elif SYM_SIZE == 16
                uint64_t base_i = 251; // Closest prime less than uint8_t max
                uint64_t mod_i = 18446744073709551557; // Closest prime less than uint64_t max
                be_store_u64_tail(base_buf, 8, base_i);
                be_store_u64_tail(mod_buf, 8, mod_i);
                be_store_u64_tail(mod_buf + 8, 8, mod_i);
            #endif
        #else
            klee_make_symbolic(base_buf, SYM_SIZE, "base");
            klee_make_symbolic(mod_buf, SYM_SIZE, "mod");
            // Set highest bit
            klee_assume(base_buf[0] & 0x80);
            klee_assume(mod_buf[0] & 0x80);
            // mod_buf is odd
            klee_assume(mod_buf[SYM_SIZE - 1] & 1);
        #endif

        if (driver_main(exp_1_buf, base_buf, mod_buf, SYM_SIZE)) return 1;

        memcpy(branchRecords1, branchRecords, sizeof(branchRecords));
        branchRecords1Len = branchRecordsLen;
        branchRecordsLen = 0;

        if (driver_main(exp_2_buf, base_buf, mod_buf, SYM_SIZE)) return 1;

        // Compare traces
        int minLen = (branchRecordsLen < branchRecords1Len) ? branchRecordsLen : branchRecords1Len;
        for (int i = 0; i < minLen; ++i) {
            BranchRecord *a = &branchRecords[i];
            BranchRecord *b = &branchRecords1[i];

            int sameLoc = (a->line == b->line) && (a->col == b->col) && (strcmp(a->file, b->file) == 0);
            int sameDecision = (a->decision == b->decision);

            if (sameLoc && !sameDecision) {
                // Case 1: differs just by condition
                fprintf(stderr, "[NON-CT BRANCH] %s:%d:%d\n", a->file, a->line, a->col);
                klee_assert(0 && "non-CT branch");
            }

            if (!sameLoc) {
                // Case 2: location differs (report both)
                fprintf(stderr, "[NON-CT BRANCH] mismatch %s:%d:%d (dec=%d) vs %s:%d:%d (dec=%d)\n",
                        a->file, a->line, a->col, a->decision,
                        b->file, b->line, b->col, b->decision);
                klee_assert(0 && "non-CT branch");
            }
        }

        if (branchRecordsLen != branchRecords1Len) {
            // Case 3: length differs; report the extra branch at index minLen
            BranchRecord *extra;
            if (branchRecordsLen > branchRecords1Len) {
                extra = &branchRecords[minLen];
            } else {
                extra = &branchRecords1[minLen];
            }
            fprintf(stderr, "[NON-CT BRANCH] extra %s:%d:%d\n", extra->file, extra->line, extra->col);
            klee_assert(0 && "non-CT branch");
        }

        return 0;
    }

#else // !SELF_COMP

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
            klee_make_symbolic_sc(exp_buf, SYM_SIZE, "exp", 1);
            klee_assume(exp_buf[0] & 0x80); // Set highest bit
        #elif defined(REPLAY)
            if (!load_bytes(exp_filename, exp_buf, SYM_SIZE)) return 1;
        #elif defined(ABACUS)
            #if SYM_SIZE == 1
                uint8_t exp_i = 241; // Second closest prime less than uint8_t max
                exp_buf[0] = exp_i;
            #elif SYM_SIZE == 2
                uint16_t exp_i = 65519; // Second closest prime less than uint16_t max
                be_store_u16_tail(exp_buf, SYM_SIZE, exp_i);
            #elif SYM_SIZE == 4
                uint32_t exp_i = 4294967279; // Second closest prime less than uint32_t max
                be_store_u32_tail(exp_buf, SYM_SIZE, exp_i);
            #elif SYM_SIZE == 8
                uint64_t exp_i = 18446744073709551533; // Second Closest prime less than uint64_t max
                be_store_u64_tail(exp_buf, SYM_SIZE, exp_i);
            #elif SYM_SIZE == 16
                uint64_t exp_i = 18446744073709551533; // Second closest prime less than uint64_t max
                be_store_u64_tail(exp_buf, 8, exp_i);
                be_store_u64_tail(exp_buf + 8, 8, exp_i);
            #endif

            char *type = "1";
            abacus_make_symbolic(type, &exp_buf, SYM_SIZE);

            exp_buf[0] |= 0x80; // Set highest bit
        #endif

        #ifdef CONCRETE_PUBS
            #if SYM_SIZE == 1
                uint8_t base_i = 3;
                uint8_t mod_i = 251; // Closest prime less than uint8_t max
                base_buf[0] = base_i;
                mod_buf[0] = mod_i;
            #elif SYM_SIZE == 2
                uint16_t base_i = 251; // Closest prime less than uint8_t max
                uint16_t mod_i = 65521; // Closest prime less than uint16_t max
                be_store_u16_tail(base_buf, SYM_SIZE, base_i);
                be_store_u16_tail(mod_buf, SYM_SIZE, mod_i);
            #elif SYM_SIZE == 4
                uint32_t base_i = 251; // Closest prime less than uint8_t max
                uint32_t mod_i = 4294967291; // Closest prime less than uint32_t max
                be_store_u32_tail(base_buf, SYM_SIZE, base_i);
                be_store_u32_tail(mod_buf, SYM_SIZE, mod_i);
            #elif SYM_SIZE == 8
                uint64_t base_i = 251; // Closest prime less than uint8_t max
                uint64_t mod_i = 18446744073709551557; // Closest prime less than uint64_t max
                be_store_u64_tail(base_buf, SYM_SIZE, base_i);
                be_store_u64_tail(mod_buf, SYM_SIZE, mod_i);
            #elif SYM_SIZE == 16
                uint64_t base_i = 251; // Closest prime less than uint8_t max
                uint64_t mod_i = 18446744073709551557; // Closest prime less than uint64_t max
                be_store_u64_tail(base_buf, 8, base_i);
                be_store_u64_tail(mod_buf, 8, mod_i);
                be_store_u64_tail(mod_buf + 8, 8, mod_i);
            #endif
        #else
            #ifdef KLEE_CF
                klee_make_symbolic_sc(base_buf, SYM_SIZE, "base", 0);
                klee_make_symbolic_sc(mod_buf, SYM_SIZE, "mod", 0);
                // Set highest bit
                klee_assume(base_buf[0] & 0x80);
                klee_assume(mod_buf[0] & 0x80);
                // mod_buf is odd
                klee_assume(mod_buf[SYM_SIZE - 1] & 1);
            #elif defined(REPLAY)
                if (!load_bytes(base_filename, base_buf, SYM_SIZE)) return 1;
                if (!load_bytes(mod_filename, mod_buf, SYM_SIZE)) return 1;
            #endif
        #endif

        exit(driver_main(exp_buf, base_buf, mod_buf, SYM_SIZE));
    }

#endif // SELF_COMP

#endif // COMMON_H
