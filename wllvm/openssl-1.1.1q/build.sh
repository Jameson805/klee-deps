#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

export LLVM_COMPILER=clang

# The no-asm part of the code will be constant time
./config no-shared no-asm -DOPENSSL_AES_CONST_TIME
make CC=wllvm CFLAGS='-g -O0' -j

flags=( -g -O0 -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( libcrypto.a )

algos=( recp mont mont_consttime mont_word )
for algo in "${algos[@]}"; do
    macro=$(echo "$algo" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')

    wllvm "${flags[@]}" "${klee_flags[@]}" -D${macro} klee_main.c "${libs[@]}" -o "klee_var_pub_${algo}"
    extract-bc "klee_var_pub_${algo}"
    wllvm "${flags[@]}" "${klee_flags[@]}" -D${macro} -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_${algo}"
    extract-bc "klee_fix_pub_${algo}"

    clang "${flags[@]}" -D${macro} -DREPLAY klee_main.c "${libs[@]}" -o "klee_var_pub_replay_${algo}"
    clang "${flags[@]}" -D${macro} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_replay_${algo}"
done
