#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

export LLVM_COMPILER=clang

flags=( -g -O0 -I../include -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( build/library/libmbedtls.a build/library/libmbedx509.a build/library/libmbedcrypto.a )

wllvm "${flags[@]}" "${klee_flags[@]}" test_mod.c "${libs[@]}" -o test_mod
extract-bc test_mod