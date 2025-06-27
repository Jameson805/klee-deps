/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub1, pub2, secret1, secret2
// PUBLIC: pub1, pub2
// KLEE_TARGET_BRANCH_LINE: 18


__attribute__((noinline))
int test_branch(int pub1, int pub2, int secret1, int secret2) {
    int score = 0;
    if (pub1 > 50 && pub2 < 25) {
        score += secret1;
    } else {
        score -= secret2;
    }
    return score;
}


int main() {
    int pub1, pub2, secret1, secret2;

    klee_make_symbolic(&pub1, sizeof(pub1), "pub1");
    klee_make_symbolic(&pub2, sizeof(pub2), "pub2");
    klee_make_symbolic(&secret1, sizeof(secret1), "secret1");
    klee_make_symbolic(&secret2, sizeof(secret2), "secret2");

    test_branch(pub1, pub2, secret1, secret2);
    return 0;
}
