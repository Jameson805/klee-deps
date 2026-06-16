/*
 * Purpose: control reproducer for the table-driven toy benchmark. It keeps the
 * same symbolic inputs, round structure, and final equality check as the table
 * version but replaces lookup-table reads with straight-line arithmetic.
 *
 * Usage:
 *   source ./activate-workspace.sh
 *   clang -I./klee-self-comp/include -O0 -g -emit-llvm -c \
 *     examples/toy_aes_big_like_no_tables.c -o /tmp/toy_aes_big_like_no_tables.bc
 *   klee-self-comp --output-dir=/tmp/toy_aes_big_like_no_tables.out \
 *     --external-calls=all --kdalloc --kdalloc-constants-size=5 \
 *     --kdalloc-globals-size=5 --kdalloc-heap-size=20 \
 *     --kdalloc-stack-size=10 --search=dfs --max-solver-time=30s \
 *     --max-memory=10000 --max-time=60s --emit-all-errors=true \
 *     /tmp/toy_aes_big_like_no_tables.bc
 */
#include "klee/klee.h"
#include <assert.h>
#include <stdint.h>

static uint32_t load32_be(const uint8_t *src) {
    return ((uint32_t)src[0] << 24)
        | ((uint32_t)src[1] << 16)
        | ((uint32_t)src[2] << 8)
        | (uint32_t)src[3];
}

static uint32_t rotl32(uint32_t value, unsigned count) {
    return (value << count) | (value >> (32 - count));
}

static uint32_t mix_word(uint32_t a, uint32_t b, uint32_t c, uint32_t d) {
    uint32_t x;

    x = rotl32(a ^ b, 5);
    x ^= rotl32(b + c, 11);
    x ^= rotl32(c ^ d, 17);
    x += rotl32(d + a, 23);
    x ^= 0x9E3779B9u;
    return rotl32(x, 3) ^ (x >> 7);
}

int main(void) {
    uint8_t round_keys[48];
    uint8_t data[16];
    uint32_t s0;
    uint32_t s1;
    uint32_t s2;
    uint32_t s3;
    uint32_t next0;
    uint32_t next1;
    uint32_t next2;
    uint32_t next3;

    klee_make_symbolic_sc(round_keys, sizeof(round_keys), "round_keys", 1);
    klee_make_symbolic_sc(data, sizeof(data), "data", 1);

    s0 = load32_be(&data[0]) ^ load32_be(&round_keys[0]);
    s1 = load32_be(&data[4]) ^ load32_be(&round_keys[4]);
    s2 = load32_be(&data[8]) ^ load32_be(&round_keys[8]);
    s3 = load32_be(&data[12]) ^ load32_be(&round_keys[12]);

    next0 = mix_word(s0, s1, s2, s3) ^ load32_be(&round_keys[16]);
    next1 = mix_word(s1, s2, s3, s0) ^ load32_be(&round_keys[20]);
    next2 = mix_word(s2, s3, s0, s1) ^ load32_be(&round_keys[24]);
    next3 = mix_word(s3, s0, s1, s2) ^ load32_be(&round_keys[28]);

    s0 = mix_word(next0, next1, next2, next3) ^ load32_be(&round_keys[32]);
    s1 = mix_word(next1, next2, next3, next0) ^ load32_be(&round_keys[36]);
    s2 = mix_word(next2, next3, next0, next1) ^ load32_be(&round_keys[40]);
    s3 = mix_word(next3, next0, next1, next2) ^ load32_be(&round_keys[44]);

    if (((s0 ^ s1) & 0xFFu) == ((s2 ^ s3) & 0xFFu)) {
        klee_assert(0 && "toy no-table equality reached");
    }

    return 0;
}