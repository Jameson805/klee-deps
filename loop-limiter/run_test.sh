#!/usr/bin/env bash
cd "$(dirname "$0")"
clang -I../klee-controlflow/include -O0 -g -emit-llvm -c test.c -o test.bc
llvm-dis test.bc
opt -load ./build/libLoopLimiter.so -load-pass-plugin=./build/libLoopLimiter.so -passes=loop-limiter -max-iterations=5 -functions=a test.bc -o test_instrumented.bc
llvm-dis test_instrumented.bc
