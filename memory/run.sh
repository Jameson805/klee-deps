#!/usr/bin/env bash
cd "$(dirname "$0")"
bin_path=$(realpath ../klee-controlflow/build/bin)

clang -I../klee-controlflow/include -O0 -g -emit-llvm -c memory_1.c -o memory_1.bc

# set virtual memory limit to 70GB to prevent excessive memory usage
ulimit -v 70000000

$bin_path/klee \
    --external-calls=all \
    --kdalloc \
    --kdalloc-constants-size=5 \
    --kdalloc-globals-size=5 \
    --kdalloc-heap-size=20 \
    --kdalloc-stack-size=10 \
    memory_1.bc