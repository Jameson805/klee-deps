#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

export PATH="/usr/lib/llvm-13/bin:$PATH"
export CC=wllvm
export LLVM_COMPILER=clang

usage() {
    echo "Usage: $0 [--skip-deps] SIZE"
    echo "  --skip-deps    Skip building libgpg-error and libgcrypt"
    echo "  SIZE           Mandatory integer, passed to -DSYM_SIZE"
}

SKIP_DEPS=0
SIZE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-deps)
            SKIP_DEPS=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [[ -z "$SIZE" ]]; then
                SIZE="$1"
                shift
            else
                echo "Unexpected argument: $1"
                usage
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$SIZE" ]]; then
    echo "Missing required SIZE argument."
    usage
    exit 1
fi
if ! [[ "$SIZE" =~ ^[0-9]+$ ]]; then
    echo "SIZE must be a non-negative integer, got: $SIZE"
    exit 1
fi

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
flags=( -g -O0 -I../include -Ilibgcrypt-1.10.1/src )
klee_flags=( -I"$KLEE_PATH/include" -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" -lkleeRuntest )
libs=( libgcrypt-1.10.1/src/.libs/libgcrypt.a libgpg-error-1.44/src/.libs/libgpg-error.a )

# KLEE-controlflow bitcode builds
wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SIZE} -DKLEE_CF klee_main.c "${libs[@]}" -o klee_var_pub
extract-bc klee_var_pub

wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SIZE} -DKLEE_CF -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub
extract-bc klee_fix_pub

wllvm "${flags[@]}" "${klee_flags[@]}" -DUSE_SLICED -DSYM_SIZE=${SIZE} -DKLEE_CF klee_main.c powm_sliced.c "${libs[@]}" -o klee_var_pub_sliced
extract-bc klee_var_pub_sliced

wllvm "${flags[@]}" "${klee_flags[@]}" -DUSE_SLICED -DSYM_SIZE=${SIZE} -DKLEE_CF -DCONCRETE_PUBS klee_main.c powm_sliced.c "${libs[@]}" -o klee_fix_pub_sliced
extract-bc klee_fix_pub_sliced

# Replay builds
clang "${flags[@]}" -DSYM_SIZE=${SIZE} -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay
clang "${flags[@]}" -DSYM_SIZE=${SIZE} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay

clang "${flags[@]}" -DUSE_SLICED -DSYM_SIZE=${SIZE} -DREPLAY klee_main.c powm_sliced.c "${libs[@]}" -o klee_var_pub_sliced_replay
clang "${flags[@]}" -DUSE_SLICED -DSYM_SIZE=${SIZE} -DREPLAY -DCONCRETE_PUBS klee_main.c powm_sliced.c "${libs[@]}" -o klee_fix_pub_sliced_replay

# BINSEC builds
clang "${flags[@]}" -static -DSYM_SIZE=${SIZE} -DBINSEC klee_main.c "${libs[@]}" -o binsec_var_pub
clang "${flags[@]}" -static -DSYM_SIZE=${SIZE} -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub

clang "${flags[@]}" -static -DUSE_SLICED -DSYM_SIZE=${SIZE} -DBINSEC klee_main.c powm_sliced.c "${libs[@]}" -o binsec_var_pub_sliced
clang "${flags[@]}" -static -DUSE_SLICED -DSYM_SIZE=${SIZE} -DBINSEC -DCONCRETE_PUBS klee_main.c powm_sliced.c "${libs[@]}" -o binsec_fix_pub_sliced
