/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include "branch_tracker.h"

__attribute__((noinline))
int test_branch(int pub, int secret) {
    int ret;

    if (secret > 0) {
        record_branch_hit(1);  // true branch taken
        ret = pub + 1;
    } else {
        record_branch_hit(0);  // false branch taken
        ret = pub - 1;
    }

    return ret;
}

int main() {
    int pub, secret1, secret2;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_make_symbolic(&secret1, sizeof(secret1), "secret1");
    klee_make_symbolic(&secret2, sizeof(secret2), "secret2");
    klee_assume(secret1 != secret2);

    reset_branch_history();

    program_run = 1;
    test_branch(pub, secret1);
    program_run = 2;
    test_branch(pub, secret2);

    assert(branch_histories_equal());
    return 0;
}
