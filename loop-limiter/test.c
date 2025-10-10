#include <stdio.h>
#include "klee/klee.h"

// A normal optimized function
int add(int a, int b) {
    return a + b;
}

// A function that is explicitly marked with optnone (disable optimization)
__attribute__((optnone))
int sub(int a, int b) {
    return a - b;
}

// A static helper
static int mul(int a, int b) {
    return a * b;
}

int main() {
    int n;
    klee_make_symbolic(&n, sizeof(n), "n");
    klee_assume(n >= 0 & n <= 10);

    int s = 0;
    for (int i = 0; i < n; ++i)
    {
        s = add(s, i);
        printf("i:%d s:%d\n", i, s);
    }

    return 0;
}
