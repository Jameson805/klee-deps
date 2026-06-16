#!/usr/bin/env bash
cd "$(dirname "$0")"
bin_path=$(realpath ../build/klee-cf/bin)
#bin_path=$(realpath ../klee-eager/build/bin)

# set virtual memory limit to 70GB to prevent excessive memory usage
ulimit -v 70000000

$bin_path/klee \
    --external-calls=all \
    --kdalloc \
    --kdalloc-constants-size=5 \
    --kdalloc-globals-size=5 \
    --kdalloc-heap-size=20 \
    --kdalloc-stack-size=10 \
    example.bc

# $bin_path/klee \
#     --libc=uclibc \
#     --external-calls=all \
#     --posix-runtime \
#     --kdalloc \
#     --kdalloc-constants-size=5 \
#     --kdalloc-globals-size=5 \
#     --kdalloc-heap-size=20 \
#     --kdalloc-stack-size=10 \
#     --product-program-fallback=false \
#     example.bc

