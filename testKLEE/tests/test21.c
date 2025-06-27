/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: secret, input
// PUBLIC: input
// KLEE_TARGET_BRANCH_LINE: 17


int insecure_equals(int secret, int input) {
    for (int i = 0; i < 32; i++) {
        if (((secret >> i) & 1) != ((input >> i) & 1)) {
            return 0;
        }
    }
    return 1;
}


int main() {
    int secret, input;

    klee_make_symbolic(&input, sizeof(input), "input");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    insecure_equals(secret, input);
    return 0;
}
