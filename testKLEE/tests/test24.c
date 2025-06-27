/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: secret
// PUBLIC:
// KLEE_TARGET_BRANCH_LINE: 22


int hamming_weight(int secret) {
    int weight = 0;
    for (int i = 0; i < 32; i++) {
        if ((secret >> i) & 1) {
            weight++;
        }
    }
    if (weight > 16) {
        return 1;
    } else {
        return 0;
    }
}


int main() {
    int secret;

    klee_make_symbolic(&secret, sizeof(secret), "secret");
    klee_assume(secret >= 0);
    klee_assume(secret < 256);

    hamming_weight(secret);
    return 0;
}
