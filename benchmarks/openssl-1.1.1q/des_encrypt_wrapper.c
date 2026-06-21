#include "runner_config.generated.h"

#include <openssl/des.h>

int driver_main(void)
{
    DES_cblock key;
    DES_cblock input;
    DES_cblock ivec;
    DES_cblock output;
    DES_key_schedule schedule;
    volatile unsigned char sink = 0;

    for (size_t index = 0; index < sizeof(key); ++index) {
        key[index] = key_buf[index];
        input[index] = data_buf[index];
        ivec[index] = iv_buf[index];
    }

    DES_set_key_unchecked(&key, &schedule);
    DES_ncbc_encrypt(input, output, sizeof(input), &schedule, &ivec, DES_ENCRYPT);
    sink ^= output[0];

    (void) sink;
    return 0;
}