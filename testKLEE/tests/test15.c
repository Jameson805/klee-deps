/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: secret
// PUBLIC:
// KLEE_TARGET_BRANCH_LINE: 17


__attribute__((noinline))
int test_branch(int secret) {
    if (secret % 2 == 0) {
        return 1;
    } else {
        return 0;
    }
}


int main() {
    int secret;

    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(secret);
    return 0;
}
