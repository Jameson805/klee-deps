/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub
// PUBLIC: pub
// KLEE_TARGET_BRANCH_LINE: 17


__attribute__((noinline))
int test_branch(int pub) {
    if (pub > 100) {
        return 1;
    } else {
        return 0;
    }
}


int main() {
    int pub;

    klee_make_symbolic(&pub, sizeof(pub), "pub");

    test_branch(pub);
    return 0;
}
