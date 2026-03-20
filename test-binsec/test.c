#include <stdlib.h>
#include <string.h>
#include <assert.h>

int sec[2];

// void * f()
// {
//     return sec;
// }

// static void * (* const volatile fp_vol)() = f;

static void * (* const volatile memset_func)( void *, int, size_t ) = memset;

int main()
{
    // int *ptr = (int *)calloc(10, sizeof(int));
    int *ptr = (int *)malloc(10 * sizeof(int));
    // int ptr[2];
    for (int i = 0; i < 2; i++)
        ptr[i] = sec[i];
    // if (ptr[0])
    // {
    //     memset_func(ptr, 0, 10 * sizeof(int));
    // }
    memset_func(ptr, 0, 10 * sizeof(int));
    assert(0);
    exit(0);
}
