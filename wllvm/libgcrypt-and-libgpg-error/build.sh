#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

export PATH="/usr/lib/llvm-13/bin:$PATH"
export CC=wllvm
export LLVM_COMPILER=clang
export CFLAGS='-g -O0'

echo "wllvm version: $(wllvm --version || echo 'wllvm not found')"
echo "llvm-link: $(which llvm-link-13)"
echo "llvm-ar: $(which llvm-ar-13)"

cd libgpg-error-1.44
make clean || true
make distclean || true
./configure --enable-static --disable-shared
make -j1 V=1  
cd -

cd libgcrypt-1.10.1
make clean || true
make distclean || true
./configure --enable-static --disable-shared --disable-asm \
    --with-libgpg-error-prefix=../libgpg-error-1.44
make -j1 V=1
cd -

flags=( -g -O0 -Ilibgcrypt-1.10.1/src )
klee_flags=(
    -I"$KLEE_PATH/include"
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib"
    -lkleeRuntest
)
libs=(
    libgcrypt-1.10.1/src/.libs/libgcrypt.a
    libgpg-error-1.44/src/.libs/libgpg-error.a
)

wllvm "${flags[@]}" "${klee_flags[@]}" klee_main.c modpow_sliced.c "${libs[@]}" -o klee_var_pub
extract-bc klee_var_pub

wllvm "${flags[@]}" "${klee_flags[@]}" -DCONCRETE_PUBS klee_main.c modpow_sliced.c "${libs[@]}" -o klee_fix_pub
extract-bc klee_fix_pub

clang "${flags[@]}" -DREPLAY klee_main.c modpow_sliced.c "${libs[@]}" -o klee_var_pub_replay
clang "${flags[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c modpow_sliced.c "${libs[@]}" -o klee_fix_pub_replay
