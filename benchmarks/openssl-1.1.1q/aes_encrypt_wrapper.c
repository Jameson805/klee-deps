#include "runner_config.generated.h"

#include <openssl/aes.h>

int driver_main(void)
{
    AES_KEY aes_key;
    unsigned char iv[sizeof(iv_buf)] = {0};
    unsigned char output[sizeof(data_buf)] = {0};
    volatile unsigned char sink = 0;

    if (AES_set_encrypt_key(key_buf, 128, &aes_key) != 0) {
        return 1;
    }
    runner_copy_bytes(iv, iv_buf, sizeof(iv));
    AES_cbc_encrypt(data_buf, output, sizeof(data_buf), &aes_key, iv, AES_ENCRYPT);
    sink ^= output[0];

    (void) sink;
    return 0;
}