#!/usr/bin/env bash
set -euo pipefail

KLEE_PATH="../../klee-controlflow"

export LLVM_COMPILER=clang

make CC=wllvm CFLAGS='-g -O0' -j

flags=( -g -O0 -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( library/libmbedtls.a library/libmbedx509.a library/libmbedcrypto.a )

wllvm "${flags[@]}" "${klee_flags[@]}" klee_main.c "${libs[@]}" -o klee_var_pub
extract-bc klee_var_pub
wllvm "${flags[@]}" "${klee_flags[@]}" -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub
extract-bc klee_fix_pub

clang "${flags[@]}" -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay
clang "${flags[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay