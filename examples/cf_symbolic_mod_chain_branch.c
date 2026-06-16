#include <assert.h>
#include <stdint.h>
#include <stddef.h>

#ifndef MOD_ROUNDS
#define MOD_ROUNDS 4
#endif

uint64_t secret[2];

void klee_make_symbolic_sc(void *addr, size_t nbytes, const char *name, int is_secret) {
  (void)addr;
  (void)nbytes;
  (void)name;
  (void)is_secret;
}

int main(void)
{
    uint64_t base;
    uint64_t modulus;
    uint64_t result;
    unsigned round;

    klee_make_symbolic_sc(secret, sizeof(secret), "secret", 1);

    base = secret[0];
    modulus = secret[1] | 1ULL;
    result = 1ULL;

    for (round = 0; round < MOD_ROUNDS; ++round) {
        result = (result * base + (uint64_t)round + 1ULL) % modulus;
        base = (base * base + 3ULL) % modulus;
    }

    if ((result & 1ULL) != 0ULL) {
        assert(0 && "symbolic modular chain branch");
    }

    return 0;
}
