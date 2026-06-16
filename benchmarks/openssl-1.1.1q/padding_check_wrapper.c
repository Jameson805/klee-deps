#include "runner_config.generated.h"

#include <openssl/evp.h>
#include <openssl/rsa.h>

#if defined(OPENSSL_RSA_PADDING_CHECK_PKCS1_TYPE_2) + \
    defined(OPENSSL_RSA_PADDING_CHECK_OAEP_MGF1) + \
    defined(OPENSSL_RSA_PADDING_CHECK_SSLV23) != 1
#error "Define exactly one OpenSSL padding check target macro."
#endif

int driver_main(void)
{
    unsigned char output[sizeof(encoded_buf)];
    int ret;

#if defined(OPENSSL_RSA_PADDING_CHECK_PKCS1_TYPE_2)
    ret = RSA_padding_check_PKCS1_type_2(output, sizeof(output),
                                         encoded_buf, sizeof(encoded_buf),
                                         sizeof(encoded_buf));
#elif defined(OPENSSL_RSA_PADDING_CHECK_OAEP_MGF1)
    ret = RSA_padding_check_PKCS1_OAEP_mgf1(output, sizeof(output),
                                            encoded_buf, sizeof(encoded_buf),
                                            sizeof(encoded_buf),
                                            NULL, 0,
                                            EVP_sha256(), EVP_sha256());
#else
    ret = RSA_padding_check_SSLv23(output, sizeof(output),
                                   encoded_buf, sizeof(encoded_buf),
                                   sizeof(encoded_buf));
#endif

    (void) ret;
    return 0;
}
