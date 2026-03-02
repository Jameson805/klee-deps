#!/usr/bin/env bash
cd "$(dirname "$0")"

gcc -g -O0 -m32 -static memory_1_binsec.c -o memory_1_binsec

jump_enum=3
max_time=60

run_binsec() {
    local sse_script="$1"      # e.g. binsec_fix_pub.cfg
    local stats_file="$2"      # e.g. mbedtls_fix_pub.toml (filename only)
    local executable="$3"      # e.g. mbedtls-3.2.1/binsec_fix_pub
    binsec -sse -checkct \
        -sse-timeout "$max_time" \
        -sse-jump-enum "$jump_enum" \
        -sse-script "$sse_script" \
        -checkct-stats-file "$stats_file" \
        "$executable"
}

run_binsec "memory_1.cfg" "memory_1.toml" "memory_1_binsec"
