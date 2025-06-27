/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub, secret
// PUBLIC: pub
// KLEE_TARGET_BRANCH_LINE: 18


__attribute__((noinline))
int test_branch(int base, int exp) {
    int result = 1;
    for (int i = 0; i < 8; ++i) {
        int bit = (exp >> i) & 1;
        result *= (1 - bit) + bit * base;
    }
    return result;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    return 0;
}
