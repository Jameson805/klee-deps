#ifndef RUNNER_H
#define RUNNER_H

/*
 * The generated header defines benchmark-specific buffers, preset constants, and
 * replay-argc constants before it includes this file. Keeping that contract in
 * one direction avoids include-order surprises while still letting this header
 * own the generic runner interface.
 */
#if defined(KLEE_CF) + defined(REPLAY) + defined(BINSEC) + defined(ABACUS) + defined(SELF_COMP) != 1
#error "You must define exactly one of KLEE_CF, REPLAY, BINSEC, ABACUS, or SELF_COMP."
#endif

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(KLEE_CF) || defined(SELF_COMP)
#include "klee/klee.h"
#endif

/*
 * These helpers stay as explicit loops instead of libc calls so the analysis
 * backends see simple byte-wise effects instead of summarized library behavior.
 */
int load_bytes(const char *filename, void *buf, size_t size) {
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

void runner_copy_bytes(void *dst_void, const void *src_void, size_t size) {
    unsigned char *dst = (unsigned char *)dst_void;
    const unsigned char *src = (const unsigned char *)src_void;
    for (size_t i = 0; i < size; ++i) {
        dst[i] = src[i];
    }
}

#ifdef ABACUS
#ifndef RUNNER_ABACUS_PUBLIC_FIXED
#error "Generated runner headers must define RUNNER_ABACUS_PUBLIC_FIXED before including runner.h."
#endif
#if RUNNER_ABACUS_PUBLIC_FIXED
#define CONCRETE_PUBS
#endif
int __attribute__((optimize(0)))
abacus_make_symbolic(char *name, void *addr, uint32_t length) {
    (void)name;
    (void)addr;
    (void)length;
    return 1;
}
#endif

#ifndef RUNNER_REPLAY_ARGC_CONCRETE
#error "Generated runner headers must define RUNNER_REPLAY_ARGC_CONCRETE before including runner.h."
#endif

#ifndef RUNNER_REPLAY_ARGC_SYMBOLIC
#error "Generated runner headers must define RUNNER_REPLAY_ARGC_SYMBOLIC before including runner.h."
#endif

#ifdef CONCRETE_PUBS
#define RUNNER_EXPECTED_REPLAY_ARGC RUNNER_REPLAY_ARGC_CONCRETE
#else
#define RUNNER_EXPECTED_REPLAY_ARGC RUNNER_REPLAY_ARGC_SYMBOLIC
#endif

/*
 * Replay is the only mode that genuinely consumes argv. The macro keeps the
 * two main definitions visually aligned without carrying dead argc/argv code in
 * the other modes.
 */
#ifdef REPLAY
#define RUNNER_MAIN_SIGNATURE int main(int argc, char *argv[])
#else
#define RUNNER_MAIN_SIGNATURE int main(void)
#endif

/*
 * These declarations are the stable contract between runner.h and generated
 * headers. The generated header should only provide benchmark-specific data and
 * implementations, not redefine the generic interface shape.
 */
int runner_apply_preset(void);
int runner_load_replay_inputs(int argc, char *argv[]);

#if defined(KLEE_CF) || defined(SELF_COMP)
void runner_apply_klee_assumptions(void);
#endif

#ifdef KLEE_CF
void runner_make_klee_secret_inputs(void);
void runner_make_klee_public_inputs(void);
#endif

#ifdef SELF_COMP
void runner_make_selfcomp_secret_variants(void);
void runner_copy_secret_input_variant_1(void);
void runner_copy_secret_input_variant_2(void);
void runner_make_selfcomp_public_inputs(void);
void runner_dump_counterexample(FILE *stream, int include_public_inputs);
#endif

#ifdef ABACUS
void runner_make_abacus_secret_inputs(void);
#endif

int driver_main(void);

#ifdef SELF_COMP

#define MAX_BRANCH_RECORDS 1000000

typedef struct {
    int decision;
    const char *file;
    int line;
    int col;
} BranchRecord;

typedef struct {
    const char *file;
    int line;
    int col;
} ReportedLocation;

BranchRecord branchRecords[MAX_BRANCH_RECORDS];
int branchRecordsLen;
BranchRecord branchRecords1[MAX_BRANCH_RECORDS];
int branchRecords1Len;
int branchRecordingEnabled;

ReportedLocation reportedLocations[MAX_BRANCH_RECORDS];
int reportedLocationsLen;

int location_already_reported(const char *file, int line, int col) {
    for (int i = 0; i < reportedLocationsLen; ++i) {
        if (reportedLocations[i].line == line && reportedLocations[i].col == col && strcmp(reportedLocations[i].file, file) == 0) {
            return 1;
        }
    }
    return 0;
}

void report_non_ct_with_counterexample(
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

    fprintf(stderr, "[NON-CT CEX] %s:%d:%d", file, line, col);
#ifdef CONCRETE_PUBS
    runner_dump_counterexample(stderr, 0);
#else
    runner_dump_counterexample(stderr, 1);
#endif
    fprintf(stderr, "\n");
}

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

RUNNER_MAIN_SIGNATURE {
    runner_make_selfcomp_secret_variants();

#ifdef CONCRETE_PUBS
    if (!runner_apply_preset()) {
        fprintf(stderr, "ERROR: failed to apply generated preset defaults\n");
        return 1;
    }
#else
    runner_make_selfcomp_public_inputs();
    runner_apply_klee_assumptions();
#endif

    branchRecordsLen = 0;
    branchRecords1Len = 0;
    reportedLocationsLen = 0;
    branchRecordingEnabled = 0;

    runner_copy_secret_input_variant_1();
    int run1_ret = driver_main();
    branchRecordingEnabled = 0;
    if (run1_ret) {
        return 1;
    }

    runner_copy_bytes(branchRecords1, branchRecords, sizeof(branchRecords));
    branchRecords1Len = branchRecordsLen;
    branchRecordsLen = 0;

    runner_copy_secret_input_variant_2();
    int run2_ret = driver_main();
    branchRecordingEnabled = 0;
    if (run2_ret) {
        return 1;
    }

    int minLen = (branchRecordsLen < branchRecords1Len) ? branchRecordsLen : branchRecords1Len;
    for (int i = 0; i < minLen; ++i) {
        BranchRecord *a = &branchRecords[i];
        BranchRecord *b = &branchRecords1[i];

        int sameLoc = (a->line == b->line) && (a->col == b->col) && (strcmp(a->file, b->file) == 0);
        int sameDecision = (a->decision == b->decision);

        if (sameLoc && !sameDecision) {
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

#else  /* !SELF_COMP */

RUNNER_MAIN_SIGNATURE {
#ifdef REPLAY
    assert(RUNNER_EXPECTED_REPLAY_ARGC > 0 && "Generated replay argc must be positive");
    assert(argc == RUNNER_EXPECTED_REPLAY_ARGC && "Replay input count does not match configured runner inputs");
#endif

#ifdef KLEE_CF
    runner_make_klee_secret_inputs();
#elif defined(REPLAY)
    if (!runner_load_replay_inputs(argc, argv)) {
        return 1;
    }
#elif defined(ABACUS)
    runner_make_abacus_secret_inputs();
#endif

#ifdef CONCRETE_PUBS
    if (!runner_apply_preset()) {
        fprintf(stderr, "ERROR: failed to apply generated preset defaults\n");
        return 1;
    }
#else
#ifdef KLEE_CF
    runner_make_klee_public_inputs();
    runner_apply_klee_assumptions();
#endif
#endif

    return driver_main();
}

#endif /* SELF_COMP */

#endif /* RUNNER_H */
