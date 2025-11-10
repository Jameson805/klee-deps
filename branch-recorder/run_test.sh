#!/usr/bin/env bash
cd "$(dirname "$0")"
clang -O0 -g -emit-llvm -c test.c -o test.bc
llvm-dis test.bc
opt -load ./build/libBranchRecorder.so -load-pass-plugin=./build/libBranchRecorder.so \
    -passes=branch-recorder -whitelist=f test.bc -o test_instrumented.bc
llvm-dis test_instrumented.bc
lli test_instrumented.bc
