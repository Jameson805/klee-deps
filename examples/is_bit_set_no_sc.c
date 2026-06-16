#include "klee/klee.h"
#include <stdio.h>

#define BN_BITS2 32
#define BN_MASK2 0xFFFFFFFF

int in[2];

int isBitSet(const int *a, int n)
{
    int i, j;
    i = n / (sizeof(int) * 8);
    j = n % (sizeof(int) * 8);
    return (a[i] >> j) & 1;
}

// Mimics BN_num_bits_word (for 32-bit words)
int BN_num_bits_word_mimic(unsigned int l)
{
    unsigned int x, mask;
    int bits = (l != 0);

    // Note: OpenSSL handles 64-bit check here (#if BN_BITS2 > 32)
    // We skip that because standard 'int' is usually 32-bit.

    // Check top 16 bits
    x = l >> 16;
    mask = (0 - x) & BN_MASK2; // Create mask: all 1s if x!=0, else 0
    mask = (0 - (mask >> (BN_BITS2 - 1))); // Ensure sign extension
    bits += 16 & mask;
    l ^= (x ^ l) & mask; // If top 16 bits were set, we keep them. If not, we keep bottom.

    // Check top 8 bits of the remaining
    x = l >> 8;
    mask = (0 - x) & BN_MASK2;
    mask = (0 - (mask >> (BN_BITS2 - 1)));
    bits += 8 & mask;
    l ^= (x ^ l) & mask;

    // Check top 4 bits
    x = l >> 4;
    mask = (0 - x) & BN_MASK2;
    mask = (0 - (mask >> (BN_BITS2 - 1)));
    bits += 4 & mask;
    l ^= (x ^ l) & mask;

    // Check top 2 bits
    x = l >> 2;
    mask = (0 - x) & BN_MASK2;
    mask = (0 - (mask >> (BN_BITS2 - 1)));
    bits += 2 & mask;
    l ^= (x ^ l) & mask;

    // Check top 1 bit
    x = l >> 1;
    mask = (0 - x) & BN_MASK2;
    mask = (0 - (mask >> (BN_BITS2 - 1)));
    bits += 1 & mask;

    return bits;
}

// Mimics BN_num_bits
int bitLen_openSSL_style(const int *a, int size)
{
    // 1. Find the top word (OpenSSL does a->top - 1)
    int i = size - 1;
    
    // Scan backwards to find the highest non-zero word
    // (OpenSSL assumes a->top is normalized or checks specifically)
    while (i >= 0 && a[i] == 0) {
        i--;
    }

    if (i < 0) return 0; // Equivalent to BN_is_zero(a)

    // 2. Calculate bits: (Index * Bits_Per_Word) + Bits_In_Top_Word
    return (i * BN_BITS2) + BN_num_bits_word_mimic((unsigned int)a[i]);
}

// Your harness updated
int main()
{
    int in1[2], in2[2];
    klee_make_symbolic(&in1, sizeof(in1), "in1");
    klee_make_symbolic(&in2, sizeof(in2), "in2");
    
    // Example setup
    in1[0] |= 0x80000000; 
    in2[0] |= 0x80000000; 

    // Calculate length using OpenSSL logic
    int t1 = bitLen_openSSL_style(in1, sizeof(in1) / sizeof(int)) - 1;
    int t2 = bitLen_openSSL_style(in2, sizeof(in2) / sizeof(int)) - 1;
    
    // Check bit
    if (isBitSet(in1, t1) == isBitSet(in2, t2))
    {
         // Logic
    }
    return 0;
}
