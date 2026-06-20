#include "runner_config.generated.h"

#include "bearssl.h"
#include "bearssl_rsa_benchmark_common.h"

int driver_main(void)
{
    unsigned char dp_full[sizeof(RSA_DP_BYTES)];
    unsigned char dq_full[sizeof(RSA_DQ_BYTES)];
    unsigned char data[sizeof(ciphertext_buf)];
    br_rsa_private_key key;
    volatile unsigned char sink = 0;
    size_t len = sizeof(data);
    uint32_t ret;

    key = load_symbolic_rsa_key(dp_full, dq_full,
                                dp_buf, sizeof(dp_buf),
                                dq_buf, sizeof(dq_buf));
    normalize_ciphertext(data, ciphertext_buf, sizeof(data));

    ret = br_rsa_i31_oaep_decrypt(&br_sha1_vtable, NULL, 0, &key, data, &len);
    sink ^= data[0] ^ (unsigned char) len ^ (unsigned char) ret;
    (void) sink;
    return 0;
}