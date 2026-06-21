#include "runner_config.generated.h"

#include <openssl/bn.h>
#include <openssl/ec.h>
#include <openssl/ecdsa.h>
#include <openssl/err.h>
#include <openssl/obj_mac.h>
#include <openssl/rand.h>

#include <string.h>

static const unsigned char *dummy_rand_bytes_src;
static size_t dummy_rand_bytes_len;

static int dummy_rand_bytes(unsigned char *buf, int num)
{
    int copied = 0;

    while (copied < num) {
        size_t chunk = dummy_rand_bytes_len;
        if (chunk > (size_t) (num - copied)) {
            chunk = (size_t) (num - copied);
        }
        memcpy(buf + copied, dummy_rand_bytes_src, chunk);
        copied += (int) chunk;
    }
    return 1;
}

static int dummy_rand_status(void)
{
    return 1;
}

int driver_main(void)
{
    EC_KEY *key = NULL;
    const EC_GROUP *group = NULL;
    EC_POINT *public_key = NULL;
    BN_CTX *ctx = NULL;
    BIGNUM *private_key = NULL;
    BIGNUM *kinv = NULL;
    BIGNUM *rp = NULL;
    const RAND_METHOD *old_rand = NULL;
    RAND_METHOD dummy_rand;
    ECDSA_SIG *signature = NULL;
    const BIGNUM *sig_r = NULL;
    const BIGNUM *sig_s = NULL;
    int rand_installed = 0;
    volatile unsigned long sink = 0;

    key = EC_KEY_new_by_curve_name(NID_X9_62_prime192v1);
    private_key = BN_bin2bn(private_key_buf, sizeof(private_key_buf), NULL);
    ctx = BN_CTX_new();
    if (key == NULL || private_key == NULL || ctx == NULL) {
        goto fail;
    }
    group = EC_KEY_get0_group(key);
    public_key = EC_POINT_new(group);
    if (group == NULL || public_key == NULL) {
        goto fail;
    }
    if (!EC_KEY_set_private_key(key, private_key)
        || !EC_POINT_mul(group, public_key, private_key, NULL, NULL, ctx)
        || !EC_KEY_set_public_key(key, public_key)) {
        goto fail;
    }

    old_rand = RAND_get_rand_method();
    if (old_rand == NULL) {
        goto fail;
    }
    dummy_rand = *old_rand;
    dummy_rand.bytes = dummy_rand_bytes;
    dummy_rand.pseudorand = dummy_rand_bytes;
    dummy_rand.status = dummy_rand_status;
    dummy_rand_bytes_src = nonce_buf;
    dummy_rand_bytes_len = sizeof(nonce_buf);
    if (!RAND_set_rand_method(&dummy_rand)) {
        goto fail;
    }
    rand_installed = 1;

    if (!ECDSA_sign_setup(key, ctx, &kinv, &rp)) {
        goto fail;
    }
    if (!RAND_set_rand_method(old_rand)) {
        goto fail;
    }
    rand_installed = 0;

    signature = ECDSA_do_sign_ex(digest_buf, sizeof(digest_buf), kinv, rp, key);
    if (signature == NULL) {
        goto fail;
    }
    ECDSA_SIG_get0(signature, &sig_r, &sig_s);
    if (sig_r != NULL) {
        sink ^= BN_get_word(sig_r);
    }
    if (sig_s != NULL) {
        sink ^= BN_get_word(sig_s);
    }

    (void) sink;
    ECDSA_SIG_free(signature);
    EC_POINT_free(public_key);
    BN_CTX_free(ctx);
    BN_free(rp);
    BN_free(kinv);
    BN_free(private_key);
    EC_KEY_free(key);
    return 0;

fail:
    if (rand_installed && old_rand != NULL) {
        RAND_set_rand_method(old_rand);
    }
    ERR_print_errors_fp(stderr);
    ECDSA_SIG_free(signature);
    EC_POINT_free(public_key);
    BN_CTX_free(ctx);
    BN_free(rp);
    BN_free(kinv);
    BN_free(private_key);
    EC_KEY_free(key);
    return 1;
}