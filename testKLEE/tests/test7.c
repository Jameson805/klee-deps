/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

int branch_taken = -1;


__attribute__((noinline))
int foo(int x) {
    if (x > 0) {
        branch_taken = 1;
        return 1;
    } else {
        branch_taken = 0;
        return 0;
    }
}


__attribute__((noinline))
int test_branch(int pub, int secret) {
    int ret1 = foo(secret);
    int ret2 = foo(pub);
    return ret1 + ret2;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_assume(pub >= 0);
    klee_assume(pub < 128);
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    klee_print_expr("branch_taken = ", branch_taken);
    return 0;
}
