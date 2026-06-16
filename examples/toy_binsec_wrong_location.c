/*
 * Minimal BINSEC wrong-location reproducer.
 *
 * This example does not try to look like AES. It only keeps the minimal shape
 * needed for the issue:
 *   - one secret integer,
 *   - two different source statements,
 *   - both statements perform secret-dependent table lookups.
 *
 * BINSEC can report the second lookup as insecure, while replay with BINSEC's
 * witness still diverges first at the earlier lookup. That is a real location
 * mismatch because the two lookups are separate statements.
 *
 * Build:
 *   source ./activate-workspace.sh
 *   clang -O0 -g -fno-omit-frame-pointer -no-pie \
 *     examples/toy_binsec_wrong_location.c \
 *     -o examples/toy_binsec_wrong_location
 *   clang -O0 -g -fno-omit-frame-pointer -no-pie -DREPLAY \
 *     examples/toy_binsec_wrong_location.c \
 *     -o examples/toy_binsec_wrong_location_replay
 *
 * Run BINSEC and keep the raw log that contains [checkct:result] lines:
 *   source ./activate-workspace.sh
 *   binsec -sse -checkct \
 *     -fml-solver z3 \
 *     -smt-solver z3 \
 *     -sse-timeout 60 \
 *     -sse-jump-enum 10 \
 *     -sse-script examples/toy_binsec_wrong_location_var_pub.cfg \
 *     -sse-depth 1000000 \
 *     -sse-heuristics nurs \
 *     -checkct-features control-flow,memory-access \
 *     -checkct-stats-file /tmp/toy_binsec_wrong_location.toml \
 *     examples/toy_binsec_wrong_location \
 *     2>&1 | tee /tmp/toy_binsec_wrong_location.log
 *
 * Convert and replay the BINSEC counterexamples:
 *   python -m tools.converters.binsec_toml_to_json \
 *     --toml /tmp/toy_binsec_wrong_location.toml \
 *     --output-log /tmp/toy_binsec_wrong_location.log \
 *     --executable examples/toy_binsec_wrong_location \
 *     --secret-input secret:4:secret_buf \
 *     --replay-executable examples/toy_binsec_wrong_location_replay \
 *     --reproduce \
 *     --out /tmp/toy_binsec_wrong_location.json \
 *     --code-path examples \
 *     --library unknown
 *
 * What to look for:
 *   BINSEC can report the second table lookup below, but replay can still land
 *   first on the first lookup because both depend on the same secret integer.
 */

#include <stdint.h>
#include <stdio.h>

uint32_t secret_buf;

static uint32_t table4[4];

#ifdef REPLAY
static int load_bytes(const char *path, unsigned char *dst, size_t size) {
    FILE *handle;
    size_t got;

    handle = fopen(path, "rb");
    if (handle == NULL) {
        return 0;
    }
    got = fread(dst, 1, size, handle);
    fclose(handle);
    return got == size;
}
#endif

int main(int argc, char **argv) {
    uint32_t first;
    uint32_t second;

#ifdef REPLAY
    if (argc != 2) {
        return 2;
    }
    if (!load_bytes(argv[1], (unsigned char *)&secret_buf, sizeof(secret_buf))) {
        return 3;
    }
#else
    (void)argc;
    (void)argv;
#endif

    /*
     * These are two different statements.
     *
     * Any witness that changes secret_buf also changes the first lookup, so
     * replay for the second statement naturally stops at the first one.
     */
    first = table4[secret_buf & 0x03u];
    second = table4[(secret_buf + 1u) & 0x03u];

    return (int)(first ^ second);
}
