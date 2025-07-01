/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub, secret
// PUBLIC: pub
// KLEE_TARGET_BRANCH_LINE: 17


__attribute__((noinline))
int foo(int x, int y) {
    if (x > 0) {
        return y;
    } else {
        return -y;
    }
}


__attribute__((noinline))
int test_branch(int pub, int secret) {
    int ret1 = foo(pub, secret);
    int ret2 = foo(secret, pub);
    return ret1 + ret2;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    return 0;
}
