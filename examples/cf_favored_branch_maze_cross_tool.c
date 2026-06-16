#include <assert.h>
#include <stdint.h>
#include <stddef.h>

#ifndef SECRET_BYTES
#define SECRET_BYTES 8
#endif

#ifndef SECRET_ROUNDS
#define SECRET_ROUNDS 192
#endif

void klee_make_symbolic_sc(void *addr, size_t nbytes, const char *name, int is_secret) {
  (void)addr;
  (void)nbytes;
  (void)name;
  (void)is_secret;
}

int main(void)
{
    uint8_t secret[SECRET_BYTES];
    uint64_t acc;
    unsigned round;

    klee_make_symbolic_sc(secret, sizeof(secret), "secret", 1);

    acc = 1;
    for (round = 0; round < SECRET_ROUNDS; ++round) {
        uint64_t byte;

        byte = (uint64_t)secret[round & 7U];
        acc = acc * 33 + byte + (uint64_t)round;
        acc ^= acc >> 7;
    }

    if ((acc & 1U) == 0U) {
        assert(0 && "cf-favored counterexample reached");
    }

    return 0;
}
