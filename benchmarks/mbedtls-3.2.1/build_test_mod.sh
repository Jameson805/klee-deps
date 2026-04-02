#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

KLEE_PATH="../../klee-controlflow"

export LLVM_COMPILER=clang

flags=( -g -O0 -I"$repo_root/include" -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( build/library/libmbedtls.a build/library/libmbedx509.a build/library/libmbedcrypto.a )

wllvm "${flags[@]}" "${klee_flags[@]}" test_mod.c "${libs[@]}" -o test_mod
extract-bc test_mod