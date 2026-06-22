#include <stdint.h>

int __attribute__((optimize(0)))
abacus_make_symbolic(char *name, void *addr, uint32_t length) {
	(void)name;
	(void)addr;
	(void)length;
	return 1;
}

static uint8_t lookup_table[64] __attribute__((aligned(64))) = {
	0, 1, 2, 3, 4, 5, 6, 7,
	8, 9, 10, 11, 12, 13, 14, 15,
	16, 17, 18, 19, 20, 21, 22, 23,
	24, 25, 26, 27, 28, 29, 30, 31,
	32, 33, 34, 35, 36, 37, 38, 39,
	40, 41, 42, 43, 44, 45, 46, 47,
	48, 49, 50, 51, 52, 53, 54, 55,
	56, 57, 58, 59, 60, 61, 62, 63,
};

static volatile uint8_t sink;

int main(void) {
	uint16_t secret = 0;
	uint8_t index;

	abacus_make_symbolic("secret", &secret, sizeof(secret));
	index = (uint8_t)(secret & 63);
	sink = lookup_table[index];
	return sink;
}