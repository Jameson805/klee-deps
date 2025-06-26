/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

int branch_taken = -1;


__attribute__((noinline))
int test_branch(int pub, int secret) {
    int ret = 0;

    if (secret > 0) {
        branch_taken = 1;
        ret = pub + 1;
    } else {
        branch_taken = 0;
        ret = pub - 1;
    }

    return ret;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_assume(pub == 0);
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    klee_print_expr("branch_taken = ", branch_taken);
    return 0;
}
