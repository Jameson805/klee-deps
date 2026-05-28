#ifndef RUNNER_H
#define RUNNER_H

/*
 * The generated header defines benchmark-specific buffers, preset constants, and
 * replay-argc constants before it includes this file. Keeping that contract in
 * one direction avoids include-order surprises while still letting this header
 * own the generic runner interface.
 */
#if defined(KLEE_CF) + defined(REPLAY) + defined(BINSEC) + defined(ABACUS) != 1
#error "You must define exactly one of KLEE_CF, REPLAY, BINSEC, or ABACUS."
#endif

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(KLEE_CF)
#include "klee/klee.h"
#endif

#ifdef REPLAY
/*
 * Replay uses file-backed test vectors; keep the byte copies explicit so the
 * non-replay backends do not inherit unnecessary libc dependencies.
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
#endif

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

#ifdef REPLAY
int runner_load_replay_inputs(int argc, char *argv[]);
#endif

#if defined(KLEE_CF)
void runner_apply_klee_assumptions(void);
#endif

#ifdef KLEE_CF
void runner_make_klee_secret_inputs(void);
void runner_make_klee_public_inputs(void);
#endif

#ifdef ABACUS
void runner_make_abacus_secret_inputs(void);
#endif

int driver_main(void);

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
#ifdef REPLAY
        fprintf(stderr, "ERROR: failed to apply generated preset defaults\n");
#endif
    #ifdef BINSEC
        exit(1);
    #else
        return 1;
    #endif
    }
#else
#ifdef KLEE_CF
    runner_make_klee_public_inputs();
    runner_apply_klee_assumptions();
#endif
#endif

#ifdef BINSEC
    exit(driver_main());
#else
    return driver_main();
#endif
}

#endif /* RUNNER_H */
