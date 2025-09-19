#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <klee_controlflow_path>"
    exit 1
fi

KLEE_PATH="$1"

export LLVM_COMPILER=clang

cd libgpg-error-1.44
./configure CC=wllvm CFLAGS='-g -O0' --enable-static
make -j
cd -

cd libgcrypt-1.10.1
./configure CC=wllvm CFLAGS='-g -O0 -DNO_ASM' --enable-static --disable-asm \
    --with-libgpg-error-prefix=../libgpg-error-1.44/src/.libs
make -j
cd -

wllvm \
    -I "$KLEE_PATH/include" \
    -I libgcrypt-1.10.1/src \
    -L "$KLEE_PATH/build/lib" \
    -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest -g -O0 \
    klee_main.c \
    libgcrypt-1.10.1/src/.libs/libgcrypt.a \
    libgpg-error-1.44/src/.libs/libgpg-error.a \
    -o klee_main

extract-bc klee_main
