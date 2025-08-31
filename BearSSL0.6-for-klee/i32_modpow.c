#include "klee/klee.h"

/*
 * Copyright (c) 2016 Thomas Pornin <pornin@bolet.org>
 *
 * Permission is hereby granted, free of charge, to any person obtaining 
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be 
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include "inner.h"

/* see inner.h */
void
br_i32_modpow(uint32_t *x,
	const unsigned char *e, size_t elen,
	const uint32_t *m, uint32_t m0i, uint32_t *t1, uint32_t *t2)
{
	size_t mlen;
	uint32_t k;

	/*
	 * 'mlen' is the length of m[] expressed in bytes (including
	 * the "bit length" first field).
	 */
	mlen = ((m[0] + 63) >> 5) * sizeof m[0];

	/*
	 * Throughout the algorithm:
	 * -- t1[] is in Montgomery representation; it contains x, x^2,
	 * x^4, x^8...
	 * -- The result is accumulated, in normal representation, in
	 * the x[] array.
	 * -- t2[] is used as destination buffer for each multiplication.
	 *
	 * Note that there is no need to call br_i32_from_monty().
	 */
	memcpy(t1, x, mlen);
	br_i32_to_monty(t1, m);
	br_i32_zero(x, m[0]);
	x[1] = 1;
	for (k = 0; k < ((uint32_t)elen << 3); k ++) {
		uint32_t ctl;

		ctl = (e[elen - 1 - (k >> 3)] >> (k & 7)) & 1;
		br_i32_montymul(t2, x, t1, m, m0i);
		CCOPY(ctl, x, t2, mlen);
		br_i32_montymul(t2, t1, t1, m, m0i);
		memcpy(t1, t2, mlen);
	}
}

void br_i32_modpow_wrapper() {
    uint32_t x[32], m[32], t1[32], t2[32];
    unsigned char e[32];
    size_t elen;
    uint32_t m0i;

    // --- Prepare modulus m ---

    // Announce an explicit bit-length of 128 bits
    m[0] = 128;  // announced bit-length in bits
    // Symbolic value for least-significant limb (must be odd)
    uint32_t m1;
    klee_make_symbolic_sc(&m1, sizeof(m1), "m1", 0);
    m[1] = m1;
    // Constrain m[1] to be odd and non-zero
    klee_assume((m[1] & 1) == 1);
    klee_assume(m[1] != 0);
    // Zero out the rest of m
    for (int i = 2; i < 32; i++) {
        m[i] = 0;
    }

    // --- Prepare base x (must < m and share same bit-length) ---

    x[0] = m[0];  // same announced length
    uint32_t x1;
    klee_make_symbolic_sc(&x1, sizeof(x1), "x1", 1);
    x[1] = x1;
    // restrict x[1] < m[1]
    klee_assume(x[1] < m[1]);
    for (int i = 2; i < 32; i++) {
        x[i] = 0;
    }

    // --- Prepare exponent e ---

    elen = 1;
    char e0;
    klee_make_symbolic_sc(&e0, sizeof(e0), "e0", 1);  // least-significant byte
    e[0] = e0;
    // Avoid trivial exponent of zero
    klee_assume(e[0] != 0);

    // --- Prepare Montgomery pre-inverse m0i ---

    klee_make_symbolic_sc(&m0i, sizeof(m0i), "m0i", 0);
    // Constrain to match m[1]: m[1] * m0i ≡ -1 mod 2^32
    klee_assume((((uint64_t)m[1] * m0i) & 0xffffffffull) == 0xffffffffu);

    // Zero-clear temporaries
    for (int i = 0; i < 32; i++) {
        t1[i] = t2[i] = 0;
    }

    // --- Now call the modular exponentiation ---

    br_i32_modpow(x, e, elen, m, m0i, t1, t2);
}

// void br_i32_modpow_wrapper() {
//   uint32_t x[32];
//   unsigned char e[32]; // Not const
//   size_t elen;
//   uint32_t m[32];     // Not const
//   uint32_t m0i;
//   uint32_t t1[32];
//   uint32_t t2[32];

//   // Set a specific bit length for 'm' to control the loop in br_i32_sub
//   // (m[0] + 63) >> 5 determines the loop iterations in br_i32_sub.
//   // Let's set m[0] to 128 bits. This would result in (128 + 63) >> 5 = 191 >> 5 = 5 iterations.
//   // If we set m[0] to, say, 256 bits, it would be (256 + 63) >> 5 = 319 >> 5 = 9 iterations.
//   // Let's choose m[0] = 128 bits for this example.
//   m[0] = 32; // Announce a 128-bit modulus
//   uint32_t m1;
//   klee_make_symbolic_sc(&m1, sizeof(m1), "m", 0);
//   m[1] = m1;

//   // Populate other necessary values for m, x, e, m0i.
//   // For br_i32_modpow to work correctly, m[1] must be odd.
// //   m[1] = m[2] = m[3] = m[4] = 7; // Least significant word of m, making it odd.
//   // The rest of m can be 0 or other values for this example's purpose
//   // as long as m[0] determines the length.
//   // for (int i = 0; i < 16; i++) {
//   //     m[i] = 0xff;
//   // }
//   // for (int i = 16; i < 32; i++) {
//   //     m[i] = 0;
//   // }

//   // Initialize x (should be an integer modulo m)
//   // x[0] = m[0]; // x has the same announced bit length as m
//   // x[1] = x[2] = x[3] = x[4] = 8;    // A sample value for x
//   // for (int i = 5; i < 32; i++) {
//   //     x[i] = 0;
//   // }
//   x[0] = 32; // Announce a 128-bit modulus
//   uint32_t x1;
//   klee_make_symbolic_sc(&x1, sizeof(x1), "x", 0);
//   x[1] = x1;

//   // Initialize exponent e and elen
// //   elen = 1; // Exponent length in bytes
// //   e[0] = 3; // Exponent value (e.g., 3)

//   elen = 1;
//   char e1;
//   klee_make_symbolic_sc(&e1, sizeof(e1), "e", 1);
//   e[1] = e1;

//   // Initialize m0i. For m[1]=1, m0i is 0xFFFFFFFF (-(1/1) mod 2^32)
//   // m0i = 0xFFFFFFFF; // Or klee_make_symbolic(&m0i, sizeof(m0i), "m0i"); for symbolic execution
//   klee_make_symbolic_sc(&m0i, sizeof(m0i), "m0i", 0);

//   br_i32_modpow(x, e, elen, m, m0i, t1, t2);
// }

int main()
{
	br_i32_modpow_wrapper();
	return 0;
}