/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub, secret
// PUBLIC: pub
// KLEE_TARGET_BRANCH_LINE: 19


__attribute__((noinline))
int test_branch(int pub, int secret) {
    int ret = 0;

    if (secret > 0) {
        ret = pub + 1;
    } else {
        ret = pub - 1;
    }

    return ret;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    return 0;
}
