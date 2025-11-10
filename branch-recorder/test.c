#include <stdio.h>

void __record_branch(int decision, const char *file, int line, int col) {
    printf("[BRANCH] %s:%d:%d -> %d\n", file, line, col, decision);
}

void f(int n) {
   if (n > 0) {
   }
   for (int i = 0; i < n; ++i) {
   }
}

void g(int n) {
    if (n > 0) {
    }
}

int main() {
    f(3);
    g(1);
    return 0;
}
