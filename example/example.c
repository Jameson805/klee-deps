#include "klee/klee.h"
#include <stdio.h>

int main()
{
    int pub, sec;
    klee_make_symbolic_sc(&pub, sizeof(pub), "pub", 0);
    klee_make_symbolic_sc(&sec, sizeof(sec), "sec", 1);
    if (sec > 0)
    {
        if (sec > pub)
        {
            if (sec > pub)
                ;
        }
        else
        {
            sec += 1;
            if (sec > pub)
                ;
        }
    }
}
