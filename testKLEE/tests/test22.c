/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: secret, input
// PUBLIC: input
// KLEE_TARGET_BRANCH_LINE: 18


int secure_equals(int secret, int input) {
    int diff = secret ^ input;
    int result = 0;
    for (int i = 0; i < 32; i++) {
        result |= (diff >> i) & 1;
    }
    return result == 0;
}


int main() {
    int secret, input;

    klee_make_symbolic(&input, sizeof(input), "input");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    secure_equals(secret, input);
    return 0;
}
