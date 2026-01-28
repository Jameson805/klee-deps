#!/usr/bin/env bash
clang -I../klee-controlflow/include -O0 -g -emit-llvm -c example.c -o example.bc
llvm-dis example.bc -o example.ll
clang -I../klee-controlflow/include -O0 -g -emit-llvm -c is_bit_set.c -o is_bit_set.bc
clang -I../klee-controlflow/include -O0 -g -emit-llvm -c is_bit_set_no_sc.c -o is_bit_set_no_sc.bc
