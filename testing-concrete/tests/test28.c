/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <stdio.h>

// VARS: arr[4], secret
// PUBLIC: arr[0]
// KLEE_TARGET_BRANCH_LINE: 17


__attribute__((noinline))
int test_array_branch(int arr[4], int secret) {
    int ret = 0;

    if (arr[0] > secret) {  // Branch at line 17
        ret = arr[1] + secret;
    } else {
        ret = arr[2] - secret;
    }

    return ret;
}


int main() {
    int arr[4], secret;

    klee_make_symbolic(arr, sizeof(arr), "arr");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_array_branch(arr, secret);
    return 0;
}
