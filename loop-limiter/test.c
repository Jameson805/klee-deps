#include <stdio.h>
#include "klee/klee.h"

void a(int n) {
    int s = 0;
    for (int i = 0; i < n; ++i) {
        s += i;
        printf("a - i:%d s:%d\n", i, s);
    }
}

void b(int n) {
    int s = 0;
    for (int i = 0; i < n; ++i) {
        s += i;
        printf("b - i:%d s:%d\n", i, s);
    }
}

int main() {
    int n;
    klee_make_symbolic(&n, sizeof(n), "n");
    klee_assume(n >= 0 & n <= 10);
    int m;
    klee_make_symbolic(&m, sizeof(m), "m");
    klee_assume(m >= 0 & m <= 10);

    a(n);
    b(m);

    return 0;
}
