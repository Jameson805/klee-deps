#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <klee_controlflow_path>"
    exit 1
fi

KLEE_PATH="$1"

export LLVM_COMPILER=clang

make CC=wllvm CFLAGS='-g -O0' -j

wllvm \
    -I "$KLEE_PATH/include" \
    -I include \
    -L "$KLEE_PATH/build/lib" \
    -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest -g -O0 \
    klee_main.c \
    library/libmbedtls.a \
    library/libmbedx509.a \
    library/libmbedcrypto.a \
    -o klee_main

extract-bc klee_main