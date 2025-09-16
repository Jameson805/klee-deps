#include <stdio.h>

int compute(int x, int y) {
    int z = 2 * x;

    int branch;
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
    int result = compute(3, 5);
    return 0;
}

/* 
Command: frama-c test1.c   -slice-annot="compute"   -kernel-msg-key annot-error=inactive  -then-on 'Slicing export' -print > test1_sliced.c
*/
