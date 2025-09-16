#include <stdio.h>

int compute(int x, int y) {
    int z = 2 * x;

    if (y > 0) {
        //@ slice_preserve_ctrl;
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
