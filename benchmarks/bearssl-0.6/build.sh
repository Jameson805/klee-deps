#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <klee_controlflow_path>"
    exit 1
fi

KLEE_PATH="$1"

export LLVM_COMPILER=clang
make CONF=ct -j

wllvm \
    -I "$KLEE_PATH/include" \
    -I inc -I src \
    -L "$KLEE_PATH/build/lib" \
    -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest -g -O0 \
    klee_main.c build/libbearssl.a -o build/klee_main

extract-bc build/klee_main