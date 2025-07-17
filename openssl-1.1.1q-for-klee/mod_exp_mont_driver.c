#include <openssl/bn.h>
#include <klee/klee.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define SYM_SIZE 32

int main() {
    BIGNUM *base = BN_new();
    BIGNUM *exp = BN_new();
    BIGNUM *mod = BN_new();
    BIGNUM *res = BN_new();

    BN_CTX *ctx = BN_CTX_new();

    unsigned char base_buf[SYM_SIZE];
    unsigned char exp_buf[SYM_SIZE];
    unsigned char mod_buf[SYM_SIZE];

    klee_make_symbolic(base_buf, SYM_SIZE, "base_buf");
    klee_make_symbolic(exp_buf, SYM_SIZE, "exp_buf");
    klee_make_symbolic(mod_buf, SYM_SIZE, "mod_buf");

    BN_bin2bn(base_buf, SYM_SIZE, base);
    BN_bin2bn(exp_buf, SYM_SIZE, exp);
    BN_bin2bn(mod_buf, SYM_SIZE, mod);

    if (BN_is_zero(mod)) return 0;

    BN_mod_exp_mont(res, base, exp, mod, ctx, NULL);

    BN_free(base);
    BN_free(exp);
    BN_free(mod);
    BN_free(res);
    BN_CTX_free(ctx);

    return 0;
}
