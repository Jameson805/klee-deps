#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

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
    make CC=wllvm CFLAGS='-g -O0' -j
else
    echo "Skipping dependency builds."
fi

flags=( -g -O0 -I../include -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( library/libmbedtls.a library/libmbedx509.a library/libmbedcrypto.a )

wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SIZE} -DKLEE_CF klee_main.c "${libs[@]}" -o klee_var_pub
extract-bc klee_var_pub
wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SIZE} -DKLEE_CF -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub
extract-bc klee_fix_pub

clang "${flags[@]}" -DSYM_SIZE=${SIZE} -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay
clang "${flags[@]}" -DSYM_SIZE=${SIZE} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay