#include "klee/klee.h"
#include "inner.h"

#define CONCRETE_PUBS

void br_i32_modpow_wrapper() {
    #define INPUT_WORDS 2
    uint32_t x[INPUT_WORDS + 1], m[INPUT_WORDS + 1], t1[INPUT_WORDS + 1], t2[INPUT_WORDS + 1];
    unsigned char e[INPUT_WORDS * 4];
    size_t elen = INPUT_WORDS * 4;
    uint32_t m0i;

    // --- Prepare modulus m ---
    uint32_t m_val[INPUT_WORDS]; // value of m
    #ifdef CONCRETE_PUBS
        m[0] = INPUT_WORDS * 32;
        m[1] = 1000000009;
        m[2] = 0;
    #else
        klee_make_symbolic_sc(m_val, sizeof(m_val), "m_val", 0);
        klee_assume((m_val[0] & 1) == 1); // m is odd
        for (int i = 0; i < INPUT_WORDS; ++i) m[i + 1] = m_val[i];
        // m[0] = br_i32_bit_length(m_val, INPUT_WORDS); // size of m
        m[0] = INPUT_WORDS * 32;
    #endif

    // --- Prepare base x (must < m and share same bit-length) ---
    #ifdef CONCRETE_PUBS
        x[0] = INPUT_WORDS * 32;
        x[1] = 100003;
        x[2] = 0;
    #else
        uint32_t xp_val[INPUT_WORDS]; // value of xp
        klee_make_symbolic_sc(xp_val, sizeof(xp_val), "xp_val", 0);
        uint32_t xp[INPUT_WORDS + 1];
        for (int i = 0; i < INPUT_WORDS; ++i) xp[i + 1] = xp_val[i];
        // xp[0] = br_i32_bit_length(xp_val, INPUT_WORDS); // size of xp
        xp[0] = INPUT_WORDS * 32;
        br_i32_reduce(x, xp, m); // x = xp % m
    #endif

    // --- Prepare exponent e ---
    // uint32_t ep_val[INPUT_WORDS]; // value of ep
    // klee_make_symbolic_sc(ep_val, sizeof(ep_val), "ep_val", 0);
    // uint32_t ep[INPUT_WORDS + 1];
    // for (int i = 0; i < INPUT_WORDS; ++i) ep[i + 1] = ep_val[i];
    // ep[0] = br_i32_bit_length(ep_val, INPUT_WORDS); // size of ep
    // br_i32_encode(e, elen, ep); // e = ep in big-endian
    klee_make_symbolic_sc(e, sizeof(e), "e", 1);

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