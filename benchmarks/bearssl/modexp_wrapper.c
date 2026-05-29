#include "runner_config.generated.h"
#include "inner.h"

int driver_main(void)
{
	size_t len = sizeof(exp_buf);
	size_t words = (len + sizeof(uint32_t) - 1) / sizeof(uint32_t);
	uint32_t mod[1 + words];
	uint32_t base_raw[1 + words];
	uint32_t base[1 + words];
	uint32_t t1[1 + words];
	uint32_t t2[1 + words];
	uint32_t m0i;

	br_i32_decode(mod, mod_buf, len);
	br_i32_decode(base_raw, base_buf, len);
	br_i32_reduce(base, base_raw, mod);

	m0i = br_i32_ninv32(mod[1]);
	if (m0i == 0) {
		fprintf(stderr, "ERROR: invalid odd modulus for br_i32_modpow\n");
		return 1;
	}

	br_i32_modpow(base, exp_buf, len, mod, m0i, t1, t2);
	return 0;
}