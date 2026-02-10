#include "klee/klee.h"
#include <stdio.h>

int a[4];

int main()
{
    int sec;
    klee_make_symbolic_sc(&sec, sizeof(sec), "sec", 1);
    sec &= 3;

    if (sec & 1)
    {
        a[sec & 1] = 1;
        a[sec & 2] = 1;
        a[sec] = 1;
    }
    
    return 0;
}
