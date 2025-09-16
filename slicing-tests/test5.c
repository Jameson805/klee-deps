#include <stdio.h>

int compute(int x, int y) {
    int z = 2 * x;

    int branch;
    //@ slice_preserve_ctrl;
    //@ slice_preserve_stmt;
    if (y > 0) {
        y = y;
        branch = 1;
    } else {
        y = -y;
        branch = -1;
    }
    //@ slice_preserve_expr branch;

    int w = 3 * x;
    return y;
}

int main() {
    // Change y for differing results
    int result = compute(3, -5);
    return 0;
}
