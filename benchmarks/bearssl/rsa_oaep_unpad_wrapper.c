#include "runner_config.generated.h"

#include "inner.h"

int driver_main(void)
{
    unsigned char data[sizeof(encoded_buf)];
    volatile unsigned char sink = 0;
    size_t len = sizeof(data);
    uint32_t ret;

    runner_copy_bytes(data, encoded_buf, sizeof(data));
    ret = br_rsa_oaep_unpad(&br_sha1_vtable, NULL, 0, data, &len);
    sink ^= data[0] ^ (unsigned char) len ^ (unsigned char) ret;
    (void) sink;
    return 0;
}