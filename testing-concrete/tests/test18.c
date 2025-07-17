/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub1, pub2, secret
// PUBLIC: pub1, pub2
// KLEE_TARGET_BRANCH_LINE: 25


__attribute__((noinline))
int test_branch(int pub1, int pub2, int secret) {
    int acc = 0;

    for (int i = 0; i < pub1; i++) {
        acc += pub2 % (i + 1);

        if ((pub2 + i) % 5 == 0) acc += i;

        // Problematic branch
        if ((secret >> i) & 1) {
            acc += 100;
        } else {
            acc -= 100;
        }
    }

    if (pub1 > 20) {
        acc ^= pub2;
    }

    return acc;
}


int main() {
    int pub1, pub2, secret;

    klee_make_symbolic(&pub1, sizeof(pub1), "pub1");
    klee_assume(pub1 >= 0);
    klee_assume(pub1 < 16);
    klee_make_symbolic(&pub2, sizeof(pub2), "pub2");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub1, pub2, secret);
    return 0;
}
