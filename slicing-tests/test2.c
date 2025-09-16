#include <stdio.h>

int compute(int x, int y) {
    int z = 2 * x;

    //@ slice_preserve_ctrl;
    if (y > 0) {
        y = y;
    } else {
        y = -y;
    }

    int w = 3 * x;
    return y;
}

int main() {
    int result = compute(3, 5);
    return 0;
}
