/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub, secret
// PUBLIC: pub
// KLEE_TARGET_BRANCH_LINE: 20


__attribute__((noinline))
int test_branch(int pub, int secret) {
    int ret = -1;

    for (int i = 0; i < pub; i++) {
        if (secret == i) {
            ret = i;
            break;
        }
    }

    return ret;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_assume(pub >= 0);
    klee_assume(pub < 128);
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    return 0;
}
