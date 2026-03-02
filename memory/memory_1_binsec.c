#include <stdio.h>
#include <stdlib.h>

int sec;
int a[4];

int main()
{
    sec &= 3;

    if (sec & 1)
    {
        a[sec & 1] = 1;
        a[sec & 2] = 1;
        a[sec] = 1;
    }
    
    exit(0);
}
