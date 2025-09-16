#include <stdio.h>

int compute(int x, int y) {
    if (x > 0) {
        y++;

        //@ slice_preserve_ctrl;
        //@ slice_preserve_stmt;
        if (y > 0) {
            y = y;
        } else {
            y = -y;
        }

        return y;
    }
    return -x;
}

extern int Frama_C_interval(int, int);

int main() {
   int x = Frama_C_interval(-10, 10);
   int y = Frama_C_interval(-10,10);
   int result = compute(x, y);
   return 0;
}
