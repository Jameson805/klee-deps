/*
Author: Jameson DiPalma
*/

#include <klee/klee.h>
#include <assert.h>
#include <stdio.h>

// VARS: pub, secret
// PUBLIC: pub
// KLEE_TARGET_BRANCH_LINE: 20


//fast exponentiation function from Yuxiang
__attribute__((noinline))
int test_branch(int base, int exp) {
	int res = 1;
	int w = 1;
	for (int i = 0; i < 32; ++i) {
		if (exp & 1) res *= base;
		exp >>= 1;
		w *= 2;
	}
	return res;
}


int main() {
    int pub, secret;

    klee_make_symbolic(&pub, sizeof(pub), "pub");
    klee_make_symbolic(&secret, sizeof(secret), "secret");

    test_branch(pub, secret);
    return 0;
}
