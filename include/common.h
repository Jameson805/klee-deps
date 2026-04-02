#ifndef COMMON_H
#define COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>


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
void be_store_u16_tail(unsigned char *dst, size_t dst_len, uint16_t x) {
    assert(dst_len >= 2);
    for (size_t i = 0; i < dst_len; ++i) {
        dst[i] = 0;
    }
    for (int i = 0; i < 2; ++i) {
        dst[dst_len - 2 + i] = (unsigned char)((x >> (8 * (1 - i))) & 0xFF);
    }
}

/* Store 32-bit big-endian value at end of buffer; zero pad leading bytes. */
void be_store_u32_tail(unsigned char *dst, size_t dst_len, uint32_t x) {
    assert(dst_len >= 4);
    for (size_t i = 0; i < dst_len; ++i) {
        dst[i] = 0;
    }
    for (int i = 0; i < 4; ++i) {
        dst[dst_len - 4 + i] = (unsigned char)((x >> (8 * (3 - i))) & 0xFF);
    }
}

/* Store 64-bit big-endian value at end of buffer; zero pad leading bytes. */
void be_store_u64_tail(unsigned char *dst, size_t dst_len, uint64_t x) {
    assert(dst_len >= 8);
    for (size_t i = 0; i < dst_len; ++i) {
        dst[i] = 0;
    }
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

#if SYM_SIZE != 1 && SYM_SIZE != 2 && SYM_SIZE != 4 && SYM_SIZE != 8 && SYM_SIZE != 16
    #error "You must define SYM_SIZE to one of 1, 2, 4, 8, or 16."
#endif

#ifdef SELF_COMP

    #include "klee/klee.h"

    unsigned char exp_1_buf[SYM_SIZE];
    unsigned char exp_2_buf[SYM_SIZE];
    unsigned char base_buf[SYM_SIZE];
    unsigned char mod_buf[SYM_SIZE];

    #define MAX_BRANCH_RECORDS 65536

    typedef struct {
        int decision;
        const char *file;
        int line;
        int col;
    } BranchRecord;

    BranchRecord branchRecords[MAX_BRANCH_RECORDS];
    int branchRecordsLen;

    BranchRecord branchRecords1[MAX_BRANCH_RECORDS];
    int branchRecords1Len;
    int branchRecordingEnabled;

    typedef struct {
        const char *file;
        int line;
        int col;
    } ReportedLocation;

    ReportedLocation reportedLocations[MAX_BRANCH_RECORDS];
    int reportedLocationsLen;

    void __record_branch(int decision, const char *file, int line, int col) {
        if (!branchRecordingEnabled) {
            return;
        }

        klee_assert(branchRecordsLen < MAX_BRANCH_RECORDS);
        branchRecords[branchRecordsLen].decision = decision;
        branchRecords[branchRecordsLen].file = file;
        branchRecords[branchRecordsLen].line = line;
        branchRecords[branchRecordsLen].col = col;
        branchRecordsLen++;
    }

    static void buf_to_hex(const unsigned char *buf, size_t len, char *out) {
        static const char hex[] = "0123456789abcdef";
        out[0] = '0';
        out[1] = 'x';
        for (size_t i = 0; i < len; ++i) {
            /* Force concrete model bytes before formatting so output is stable ASCII hex. */
            unsigned char b = (unsigned char)klee_get_value_i32((unsigned)buf[i]);
            out[2 + i * 2] = hex[(b >> 4) & 0x0F];
            out[2 + i * 2 + 1] = hex[b & 0x0F];
        }
        out[2 + len * 2] = '\0';
    }

    static int location_already_reported(const char *file, int line, int col) {
        for (int i = 0; i < reportedLocationsLen; ++i) {
            if (reportedLocations[i].line == line && reportedLocations[i].col == col && strcmp(reportedLocations[i].file, file) == 0) {
                return 1;
            }
        }
        return 0;
    }

    static void report_non_ct_with_counterexample(
        const char *kind,
        const char *file,
        int line,
        int col,
        const char *other_file,
        int other_line,
        int other_col,
        int len_a,
        int len_b
    ) {
        if (location_already_reported(file, line, col)) {
            return;
        }

        klee_assert(reportedLocationsLen < MAX_BRANCH_RECORDS);
        reportedLocations[reportedLocationsLen].file = file;
        reportedLocations[reportedLocationsLen].line = line;
        reportedLocations[reportedLocationsLen].col = col;
        reportedLocationsLen++;

        fprintf(stderr, "[NON-CT BRANCH] %s:%d:%d type=%s", file, line, col, kind);
        if (other_file != NULL) {
            fprintf(stderr, " other=%s:%d:%d", other_file, other_line, other_col);
        }
        if (len_a >= 0 && len_b >= 0) {
            fprintf(stderr, " len_a=%d len_b=%d", len_a, len_b);
        }
        fprintf(stderr, "\n");

        char exp_hex[2 * SYM_SIZE + 3];
        char exp_prime_hex[2 * SYM_SIZE + 3];
        buf_to_hex(exp_1_buf, SYM_SIZE, exp_hex);
        buf_to_hex(exp_2_buf, SYM_SIZE, exp_prime_hex);

        #ifdef CONCRETE_PUBS
            fprintf(stderr,
                    "[NON-CT CEX] %s:%d:%d exp=%s exp__prime=%s\n",
                    file,
                    line,
                    col,
                    exp_hex,
                    exp_prime_hex);
        #else
            char base_hex[2 * SYM_SIZE + 3];
            char mod_hex[2 * SYM_SIZE + 3];
            buf_to_hex(base_buf, SYM_SIZE, base_hex);
            buf_to_hex(mod_buf, SYM_SIZE, mod_hex);
            fprintf(stderr,
                    "[NON-CT CEX] %s:%d:%d exp=%s exp__prime=%s base=%s mod=%s\n",
                    file,
                    line,
                    col,
                    exp_hex,
                    exp_prime_hex,
                    base_hex,
                    mod_hex);
        #endif
    }

    /* User-provided entry that consumes the prepared buffers. */
    int driver_main(const unsigned char *exp_buf, const unsigned char *base_buf, const unsigned char *mod_buf, size_t len);

    int main(int argc, char *argv[]) {
        klee_make_symbolic(exp_1_buf, SYM_SIZE, "exp_1");
        klee_make_symbolic(exp_2_buf, SYM_SIZE, "exp_2");
        // klee_assume(exp_1_buf[0] & 0x80); // Set highest bit
        // klee_assume(exp_2_buf[0] & 0x80); // Set highest bit

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
                // Closest prime less than uint128_t max
                uint64_t mod_i_high = 18446744073709551615;
                uint64_t mod_i_low = 18446744073709551457;
                be_store_u64_tail(base_buf, 16, base_i);
                be_store_u64_tail(mod_buf, 8, mod_i_high);
                be_store_u64_tail(mod_buf + 8, 8, mod_i_low);
            #endif
        #else
            klee_make_symbolic(base_buf, SYM_SIZE, "base");
            klee_make_symbolic(mod_buf, SYM_SIZE, "mod");
            // Set highest bit
            // klee_assume(base_buf[0] & 0x80);
            klee_assume(mod_buf[0] & 0x80);
            // mod_buf is odd
            klee_assume(mod_buf[SYM_SIZE - 1] & 1);
        #endif

        branchRecordsLen = 0;
        branchRecords1Len = 0;
        reportedLocationsLen = 0;
        branchRecordingEnabled = 0;
        int run1_ret = driver_main(exp_1_buf, base_buf, mod_buf, SYM_SIZE);
        branchRecordingEnabled = 0;
        if (run1_ret) return 1;

        memcpy(branchRecords1, branchRecords, sizeof(branchRecords));
        branchRecords1Len = branchRecordsLen;
        branchRecordsLen = 0;

        branchRecordingEnabled = 0;
        int run2_ret = driver_main(exp_2_buf, base_buf, mod_buf, SYM_SIZE);
        branchRecordingEnabled = 0;
        if (run2_ret) return 1;

        // Compare traces
        int minLen = (branchRecordsLen < branchRecords1Len) ? branchRecordsLen : branchRecords1Len;
        for (int i = 0; i < minLen; ++i) {
            BranchRecord *a = &branchRecords[i];
            BranchRecord *b = &branchRecords1[i];

            int sameLoc = (a->line == b->line) && (a->col == b->col) && (strcmp(a->file, b->file) == 0);
            int sameDecision = (a->decision == b->decision);

            if (sameLoc && !sameDecision) {
                // Case 1: differs just by condition.
                report_non_ct_with_counterexample(
                    "condition",
                    a->file,
                    a->line,
                    a->col,
                    NULL,
                    -1,
                    -1,
                    -1,
                    -1
                );
                klee_assert(0 && "non-CT branch");
            }

            if (!sameLoc) {
                // Case 2: location differs; report first divergence from first run.
                report_non_ct_with_counterexample(
                    "location",
                    a->file,
                    a->line,
                    a->col,
                    b->file,
                    b->line,
                    b->col,
                    -1,
                    -1
                );
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
            report_non_ct_with_counterexample(
                "length",
                extra->file,
                extra->line,
                extra->col,
                NULL,
                -1,
                -1,
                branchRecordsLen,
                branchRecords1Len
            );
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

    unsigned char exp_buf[SYM_SIZE];
    unsigned char base_buf[SYM_SIZE];
    unsigned char mod_buf[SYM_SIZE];

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
            // klee_assume(exp_buf[0] & 0x80); // Set highest bit
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
                uint64_t exp_i = 18446744073709551533; // Second closest prime less than uint64_t max
                be_store_u64_tail(exp_buf, SYM_SIZE, exp_i);
            #elif SYM_SIZE == 16
                // Second closest prime less than uint128_t max
                uint64_t exp_i_high = 18446744073709551615;
                uint64_t exp_i_low = 18446744073709551443;
                be_store_u64_tail(exp_buf, 8, exp_i_high);
                be_store_u64_tail(exp_buf + 8, 8, exp_i_low);
            #endif

            char *type = "1";
            abacus_make_symbolic(type, &exp_buf, SYM_SIZE);

            // exp_buf[0] |= 0x80; // Set highest bit
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
                // Closest prime less than uint128_t max
                uint64_t mod_i_high = 18446744073709551615;
                uint64_t mod_i_low = 18446744073709551457;
                be_store_u64_tail(base_buf, 16, base_i);
                be_store_u64_tail(mod_buf, 8, mod_i_high);
                be_store_u64_tail(mod_buf + 8, 8, mod_i_low);
            #endif
        #else
            #ifdef KLEE_CF
                klee_make_symbolic_sc(base_buf, SYM_SIZE, "base", 0);
                klee_make_symbolic_sc(mod_buf, SYM_SIZE, "mod", 0);
                // Set highest bit
                // klee_assume(base_buf[0] & 0x80);
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
