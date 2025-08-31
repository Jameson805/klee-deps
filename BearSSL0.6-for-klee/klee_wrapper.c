#include "klee/klee.h"
#include "inner.h"

void br_i32_modpow_wrapper() {
    #define INPUT_WORDS 2
    uint32_t x[INPUT_WORDS + 1], m[INPUT_WORDS + 1], t1[INPUT_WORDS + 1], t2[INPUT_WORDS + 1];
    unsigned char e[INPUT_WORDS * 4];
    size_t elen = INPUT_WORDS * 4;
    uint32_t m0i;

    // --- Prepare modulus m ---
    uint32_t m_val[INPUT_WORDS]; // value of m
    klee_make_symbolic_sc(m_val, sizeof(m_val), "m_val", 0);
    klee_assume((m_val[0] & 1) == 1); // m is odd
    for (int i = 0; i < INPUT_WORDS; ++i) m[i + 1] = m_val[i];
    m[0] = br_i32_bit_length(m_val, INPUT_WORDS); // size of m

    // --- Prepare base x (must < m and share same bit-length) ---
    uint32_t xp_val[INPUT_WORDS]; // value of xp
    klee_make_symbolic_sc(xp_val, sizeof(xp_val), "xp_val", 0);
    uint32_t xp[INPUT_WORDS + 1];
    for (int i = 0; i < INPUT_WORDS; ++i) xp[i + 1] = xp_val[i];
    xp[0] = br_i32_bit_length(xp_val, INPUT_WORDS); // size of xp
    br_i32_reduce(x, xp, m); // x = xp % m

    // --- Prepare exponent e ---
    uint32_t ep_val[INPUT_WORDS]; // value of ep
    klee_make_symbolic_sc(ep_val, sizeof(ep_val), "ep_val", 0);
    uint32_t ep[INPUT_WORDS + 1];
    for (int i = 0; i < INPUT_WORDS; ++i) ep[i + 1] = ep_val[i];
    ep[0] = br_i32_bit_length(ep_val, INPUT_WORDS); // size of ep
    br_i32_encode(e, elen, ep); // e = ep in big-endian

    // --- Prepare Montgomery pre-inverse m0i ---
    m0i = br_i32_ninv32(m[1]);

    // --- Now call the modular exponentiation ---
    br_i32_modpow(x, e, elen, m, m0i, t1, t2);
}

int main()
{
	br_i32_modpow_wrapper();
	return 0;
}