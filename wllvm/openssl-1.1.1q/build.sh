#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

usage() {
    echo "Usage: $0 [--skip-deps] (--klee-cf | --binsec | --abacus) --sym-size N"
    echo "  --skip-deps    Skip building libgpg-error and libgcrypt"
    echo "  --klee-cf      Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries"
    echo "  --abacus       Build Abacus binaries"
    echo "  --sym-size N   Mandatory non-negative integer to pass as -DSYM_SIZE"
}

SKIP_DEPS=0
MODE=""
SYM_SIZE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-deps)
            SKIP_DEPS=1
            shift
            ;;
        --klee-cf|--binsec|--abacus)
            if [[ -n "$MODE" ]]; then
                echo "Multiple build modes specified. Choose exactly one of --klee-cf, --binsec, --abacus."
                exit 1
            fi
            case "$1" in
                --klee-cf) MODE="klee_cf" ;;
                --binsec)  MODE="binsec"  ;;
                --abacus)  MODE="abacus"  ;;
            esac
            shift
            ;;
        --sym-size)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --sym-size"
                exit 1
            fi
            SYM_SIZE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option or unexpected argument: $1"
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$MODE" ]]; then
    echo "Missing required build mode. Choose exactly one of --klee-cf, --binsec, --abacus."
    usage
    exit 1
fi
if [[ -z "$SYM_SIZE" ]]; then
    echo "Missing required --sym-size argument."
    usage
    exit 1
fi
if ! [[ "$SYM_SIZE" =~ ^[0-9]+$ ]]; then
    echo "SYM_SIZE must be a non-negative integer, got: $SYM_SIZE"
    exit 1
fi

if [ "$SKIP_DEPS" -eq 0 ]; then
    echo "Building dependencies..."

    CC=gcc
    if [[ "$MODE" == "klee_cf" ]]; then
        export LLVM_COMPILER=clang
        CC=wllvm
    fi

    CFLAGS=( -g -O0 )
    LDFLAGS=( )
    ARCH_FLAGS=( linux-generic64 )
    if [[ "$MODE" == "abacus" ]]; then
        CFLAGS+=( -m32 )
        LDFLAGS+=( -m32 )
        ARCH_FLAGS=( linux-generic32 )
    fi

    # The no-asm part of the code will be constant time
    ./Configure no-shared no-asm -DOPENSSL_AES_CONST_TIME "${ARCH_FLAGS[@]}"
    make clean
    make CC=${CC} CFLAGS="${CFLAGS[*]}" LDFLAGS="${LDFLAGS[*]}" -j
else
    echo "Skipping dependency builds."
fi

flags=( -g -O0 -I../include -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( libcrypto.a )

algos=( recp mont mont_consttime mont_word )
for algo in "${algos[@]}"; do
    macro=$(echo "$algo" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')

    if [[ "$MODE" == "klee_cf" ]]; then
        # KLEE-controlflow bitcode builds
        wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SYM_SIZE} -DKLEE_CF -D${macro} klee_main.c "${libs[@]}" -o "klee_var_pub_${algo}"
        extract-bc "klee_var_pub_${algo}"
        wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SYM_SIZE} -DKLEE_CF -D${macro} -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_${algo}"
        extract-bc "klee_fix_pub_${algo}"

        # Replay builds
        clang "${flags[@]}" -D${macro} -DSYM_SIZE=${SYM_SIZE} -DREPLAY klee_main.c "${libs[@]}" -o "klee_var_pub_replay_${algo}"
        clang "${flags[@]}" -D${macro} -DSYM_SIZE=${SYM_SIZE} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_replay_${algo}"
    fi

    if [[ "$MODE" == "binsec" ]]; then
        # BINSEC builds
        gcc "${flags[@]}" -static -D${macro} -DSYM_SIZE=${SYM_SIZE} -DBINSEC klee_main.c "${libs[@]}" -o "binsec_var_pub_${algo}"
        gcc "${flags[@]}" -static -D${macro} -DSYM_SIZE=${SYM_SIZE} -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "binsec_fix_pub_${algo}"
    fi

    if [[ "$MODE" == "abacus" ]]; then
        # Abacus builds
        gcc "${flags[@]}" -m32 -pthread -D${macro} -DSYM_SIZE=${SYM_SIZE} -DABACUS klee_main.c "${libs[@]}" -ldl -o "abacus_fix_pub_${algo}"
    fi
done
