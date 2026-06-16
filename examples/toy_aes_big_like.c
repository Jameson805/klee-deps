/*
 * Purpose: benchmark-like reproducer for table-driven crypto behavior that was
 * previously pathological for klee-self-comp. The key property is that secret
 * bytes flow into repeated lookup-table indices across two rounds.
 *
 * Usage:
 *   source ./activate-workspace.sh
 *   clang -I./klee-self-comp/include -O0 -g -emit-llvm -c \
 *     examples/toy_aes_big_like.c -o /tmp/toy_aes_big_like.bc
 *   klee-self-comp --output-dir=/tmp/toy_aes_big_like.out \
 *     --external-calls=all --kdalloc --kdalloc-constants-size=5 \
 *     --kdalloc-globals-size=5 --kdalloc-heap-size=20 \
 *     --kdalloc-stack-size=10 --search=dfs --max-solver-time=30s \
 *     --max-memory=10000 --max-time=60s --emit-all-errors=true \
 *     /tmp/toy_aes_big_like.bc
 */
#include "klee/klee.h"
#include <assert.h>
#include <stdint.h>

static const uint32_t sbox[256] = {
    0xA56363C6u, 0x847C7CF8u, 0x997777EEu, 0x8D7B7BF6u,
    0x0DF2F2FFu, 0xBD6B6BD6u, 0xB16F6FDEu, 0x54C5C591u,
    0x50303060u, 0x03010102u, 0xA96767CEu, 0x7D2B2B56u,
    0x19FEFEE7u, 0x62D7D7B5u, 0xE6ABAB4Du, 0x9A7676ECu,
    0x45CACA8Fu, 0x9D82821Fu, 0x40C9C989u, 0x877D7DFAu,
    0x15FAFAEFu, 0xEB5959B2u, 0xC947478Eu, 0x0BF0F0FBu,
    0xECADAD41u, 0x67D4D4B3u, 0xFDA2A25Fu, 0xEAAFAF45u,
    0xBF9C9C23u, 0xF7A4A453u, 0x967272E4u, 0x5BC0C09Bu,
    0xC2B7B775u, 0x1CFDFDE1u, 0xAE93933Du, 0x6A26264Cu,
    0x5A36366Cu, 0x413F3F7Eu, 0x02F7F7F5u, 0x4FCCCC83u,
    0x5C343468u, 0xF4A5A551u, 0x34E5E5D1u, 0x08F1F1F9u,
    0x937171E2u, 0x73D8D8ABu, 0x53313162u, 0x3F15152Au,
    0x0C040408u, 0x52C7C795u, 0x65232346u, 0x5EC3C39Du,
    0x28181830u, 0xA1969637u, 0x0F05050Au, 0xB59A9A2Fu,
    0x0907070Eu, 0x36121224u, 0x9B80801Bu, 0x3DE2E2DFu,
    0x26EBEBCDu, 0x6927274Eu, 0xCDB2B27Fu, 0x9F7575EAu,
    0x1B090912u, 0x9E83831Du, 0x742C2C58u, 0x2E1A1A34u,
    0x2D1B1B36u, 0xB26E6EDCu, 0xEE5A5AB4u, 0xFBA0A05Bu,
    0xF65252A4u, 0x4D3B3B76u, 0x61D6D6B7u, 0xCEB3B37Du,
    0x7B292952u, 0x3EE3E3DDu, 0x712F2F5Eu, 0x97848413u,
    0xF55353A6u, 0x68D1D1B9u, 0x00000000u, 0x2CEDEDC1u,
    0x60202040u, 0x1FFCFCE3u, 0xC8B1B179u, 0xED5B5BB6u,
    0xBE6A6AD4u, 0x46CBCB8Du, 0xD9BEBE67u, 0x4B393972u,
    0xDE4A4A94u, 0xD44C4C98u, 0xE85858B0u, 0x4ACFCF85u,
    0x6BD0D0BBu, 0x2AEFEFC5u, 0xE5AAAA4Fu, 0x16FBFBEDu,
    0xC5434386u, 0xD74D4D9Au, 0x55333366u, 0x94858511u,
    0xCF45458Au, 0x10F9F9E9u, 0x06020204u, 0x817F7FFEu,
    0xF05050A0u, 0x443C3C78u, 0xBA9F9F25u, 0xE3A8A84Bu,
    0xF35151A2u, 0xFEA3A35Du, 0xC0404080u, 0x8A8F8F05u,
    0xAD92923Fu, 0xBC9D9D21u, 0x48383870u, 0x04F5F5F1u,
    0xDFBCBC63u, 0xC1B6B677u, 0x75DADAAFu, 0x63212142u,
    0x30101020u, 0x1AFFFFE5u, 0x0EF3F3FDu, 0x6DD2D2BFu,
    0x4CCDCD81u, 0x140C0C18u, 0x35131326u, 0x2FECECC3u,
    0xE15F5FBEu, 0xA2979735u, 0xCC444488u, 0x3917172Eu,
    0x57C4C493u, 0xF2A7A755u, 0x827E7EFCu, 0x473D3D7Au,
    0xAC6464C8u, 0xE75D5DBAu, 0x2B191932u, 0x957373E6u,
    0xA06060C0u, 0x98818119u, 0xD14F4F9Eu, 0x7FDCDCA3u,
    0x66222244u, 0x7E2A2A54u, 0xAB90903Bu, 0x8388880Bu,
    0xCA46468Cu, 0x29EEEEC7u, 0xD3B8B86Bu, 0x3C141428u,
    0x79DEDEA7u, 0xE25E5EBCu, 0x1D0B0B16u, 0x76DBDBADu,
    0x3BE0E0DBu, 0x56323264u, 0x4E3A3A74u, 0x1E0A0A14u,
    0xDB494992u, 0x0A06060Cu, 0x6C242448u, 0xE45C5CB8u,
    0x5DC2C29Fu, 0x6ED3D3BDu, 0xEFACAC43u, 0xA66262C4u,
    0xA8919139u, 0xA4959531u, 0x37E4E4D3u, 0x8B7979F2u,
    0x32E7E7D5u, 0x43C8C88Bu, 0x5937376Eu, 0xB76D6DDAu,
    0x8C8D8D01u, 0x64D5D5B1u, 0xD24E4E9Cu, 0xE0A9A949u,
    0xB46C6CD8u, 0xFA5656ACu, 0x07F4F4F3u, 0x25EAEACFu,
    0xAF6565CAu, 0x8E7A7AF4u, 0xE9AEAE47u, 0x18080810u,
    0xD5BABA6Fu, 0x887878F0u, 0x6F25254Au, 0x722E2E5Cu,
    0x241C1C38u, 0xF1A6A657u, 0xC7B4B473u, 0x51C6C697u,
    0x23E8E8CBu, 0x7CDDDDA1u, 0x9C7474E8u, 0x211F1F3Eu,
    0xDD4B4B96u, 0xDCBDBD61u, 0x868B8B0Du, 0x858A8A0Fu,
    0x907070E0u, 0x423E3E7Cu, 0xC4B5B571u, 0xAA6666CCu,
    0xD8484890u, 0x05030306u, 0x01F6F6F7u, 0x120E0E1Cu,
    0xA36161C2u, 0x5F35356Au, 0xF95757AEu, 0xD0B9B969u,
    0x91868617u, 0x58C1C199u, 0x271D1D3Au, 0xB99E9E27u,
    0x38E1E1D9u, 0x13F8F8EBu, 0xB398982Bu, 0x33111122u,
    0xBB6969D2u, 0x70D9D9A9u, 0x898E8E07u, 0xA7949433u,
    0xB69B9B2Du, 0x221E1E3Cu, 0x92878715u, 0x20E9E9C9u,
    0x49CECE87u, 0xFF5555AAu, 0x78282850u, 0x7ADFDFA5u,
    0x8F8C8C03u, 0xF8A1A159u, 0x80898909u, 0x170D0D1Au,
    0xDABFBF65u, 0x31E6E6D7u, 0xC6424284u, 0xB86868D0u,
    0xC3414182u, 0xB0999929u, 0x772D2D5Au, 0x110F0F1Eu,
    0xCBB0B07Bu, 0xFC5454A8u, 0xD6BBBB6Du, 0x3A16162Cu
};

static uint32_t load32_be(const uint8_t *src) {
    return ((uint32_t)src[0] << 24)
        | ((uint32_t)src[1] << 16)
        | ((uint32_t)src[2] << 8)
        | (uint32_t)src[3];
}

static uint32_t mix_word(uint32_t a, uint32_t b, uint32_t c, uint32_t d) {
    return sbox[(a >> 24) & 0xFFu]
        ^ sbox[(b >> 16) & 0xFFu]
        ^ sbox[(c >> 8) & 0xFFu]
        ^ sbox[d & 0xFFu];
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
        klee_assert(0 && "toy aes-big-like equality reached");
    }

    return 0;
}