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
int test_branch(int pub, int secret) {
    for (int i=0; i < secret ; i++) {
        pub++;
    }
    return pub;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_assume(pub == 0);
    klee_make_symbolic(&secret, sizeof(secret), "secret");
    klee_assume(secret >= 0);
    klee_assume(secret < 64);

    test_branch(pub, secret);
    return 0;
}
