#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

export PATH="/usr/lib/llvm-13/bin:$PATH"
export CC=wllvm
export LLVM_COMPILER=clang

# Optional flag, pass 1 to skip dependency builds
SKIP_DEPS=${1:-0}   
if [ "$SKIP_DEPS" -eq 0 ]; then
    echo "Building dependencies..."

    cd libgpg-error-1.44
    ./configure CC=wllvm CFLAGS='-g -O0' --enable-static
    make -j
    cd -

    cd libgcrypt-1.10.1
    ./configure CC=wllvm CFLAGS='-g -O0 -DNO_ASM' --enable-static --disable-asm \
        --with-libgpg-error-prefix=../libgpg-error-1.44/src/.libs
    make -j
    cd -
else
    echo "Skipping dependency builds."
fi

# Flags and libraries
flags=( -g -O0 -Ilibgcrypt-1.10.1/src )
klee_flags=( -I"$KLEE_PATH/include" -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" -lkleeRuntest )
libs=( libgcrypt-1.10.1/src/.libs/libgcrypt.a libgpg-error-1.44/src/.libs/libgpg-error.a )


# KLEE bitcode builds
wllvm "${flags[@]}" "${klee_flags[@]}" klee_main.c "${libs[@]}" -o klee_var_pub
extract-bc klee_var_pub

wllvm "${flags[@]}" "${klee_flags[@]}" -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub
extract-bc klee_fix_pub

wllvm "${flags[@]}" "${klee_flags[@]}" -DUSE_SLICED klee_main.c modpow_sliced.c "${libs[@]}" -o klee_var_pub_sliced
extract-bc klee_var_pub_sliced

wllvm "${flags[@]}" "${klee_flags[@]}" -DUSE_SLICED -DCONCRETE_PUBS klee_main.c modpow_sliced.c "${libs[@]}" -o klee_fix_pub_sliced
extract-bc klee_fix_pub_sliced

# Replay builds
clang "${flags[@]}" -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay
clang "${flags[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay

clang "${flags[@]}" -DUSE_SLICED -DREPLAY klee_main.c modpow_sliced.c "${libs[@]}" -o klee_var_pub_sliced_replay
clang "${flags[@]}" -DUSE_SLICED -DREPLAY -DCONCRETE_PUBS klee_main.c modpow_sliced.c "${libs[@]}" -o klee_fix_pub_sliced_replay
