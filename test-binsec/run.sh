#!/usr/bin/env bash
cd "$(dirname "$0")"

clang -g -O0 -m32 -static -fno-pie -Wl,-no-pie -fno-plt test.c -o test
# clang -g -O0 -m32 -static test.c -o test
# clang -g -O0 -m32 -static -fno-plt test.c -o test

jump_enum=3
max_time=180
sse_depth=10000

run_binsec() {
    local sse_script="$1"      # e.g. binsec_fix_pub.cfg
    local stats_file="$2"      # e.g. mbedtls_fix_pub.toml (filename only)
    local executable="$3"      # e.g. mbedtls-3.2.1/binsec_fix_pub
    binsec -sse -checkct \
        -sse-timeout "$max_time" \
        -sse-jump-enum "$jump_enum" \
        -sse-script "$sse_script" \
        -sse-depth "$sse_depth" \
        -sse-heuristics nurs \
        -checkct-features control-flow,memory-access \
        -checkct-stats-file "$stats_file" \
        "$executable"
}

run_binsec "test.cfg" "test.toml" "test"
