#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KLEE_PATH="../../klee-controlflow"

usage() {
    echo "Usage: $0 [--skip-deps] (--klee-cf | --binsec | --abacus | --self-comp) --sym-size N"
    echo "  --skip-deps    Skip building libgpg-error and libgcrypt"
    echo "  --klee-cf      Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries"
    echo "  --abacus       Build Abacus binaries"
    echo "  --self-comp    Build self-composition KLEE bitcode"
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
        --klee-cf|--binsec|--abacus|--self-comp)
            if [[ -n "$MODE" ]]; then
                echo "Multiple build modes specified. Choose exactly one of --klee-cf, --binsec, --abacus, --self-comp."
                exit 1
            fi
            case "$1" in
                --klee-cf)   MODE="klee_cf" ;;
                --binsec)    MODE="binsec"  ;;
                --abacus)    MODE="abacus"  ;;
                --self-comp) MODE="self_comp"  ;;
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
    echo "Missing required build mode. Choose exactly one of --klee-cf, --binsec, --abacus, --self-comp."
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
    if [[ "$MODE" == "klee_cf" || "$MODE" == "self_comp" ]]; then
        export LLVM_COMPILER=clang
        CC=wllvm
    fi

    CFLAGS=( -g -O0 )
    LDFLAGS=( )
    if [[ "$MODE" == "abacus" ]]; then
        CFLAGS+=( -m32 )
        LDFLAGS+=( -m32 )
    fi

    rm -rf build
    mkdir build
    cd build
    cmake -DENABLE_TESTING=Off \
        -DCMAKE_C_COMPILER=${CC} \
        -DCMAKE_C_FLAGS="${CFLAGS[*]}" \
        -DCMAKE_EXE_LINKER_FLAGS="${LDFLAGS[*]}" \
        ..
    cmake --build . -j

    cd -
else
    echo "Skipping dependency builds."
fi

flags=( -g -O0 -I../include -Iinclude )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( build/library/libmbedtls.a build/library/libmbedx509.a build/library/libmbedcrypto.a )

if [[ "$MODE" == "klee_cf" ]]; then
    # KLEE-controlflow bitcode builds
    wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SYM_SIZE} -DKLEE_CF klee_main.c "${libs[@]}" -o klee_var_pub
    extract-bc klee_var_pub
    wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SYM_SIZE} -DKLEE_CF -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub
    extract-bc klee_fix_pub

    # Replay builds
    clang "${flags[@]}" -static -DSYM_SIZE=${SYM_SIZE} -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay
    clang "${flags[@]}" -static -DSYM_SIZE=${SYM_SIZE} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay
fi

if [[ "$MODE" == "binsec" ]]; then
    # BINSEC builds
    gcc "${flags[@]}" -static -DSYM_SIZE=${SYM_SIZE} -DBINSEC klee_main.c "${libs[@]}" -o binsec_var_pub
    gcc "${flags[@]}" -static -DSYM_SIZE=${SYM_SIZE} -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub
fi

if [[ "$MODE" == "abacus" ]]; then
    # Abacus builds
    gcc "${flags[@]}" -static -m32 -DSYM_SIZE=${SYM_SIZE} -DABACUS klee_main.c "${libs[@]}" -o abacus_fix_pub
fi

record_branch() {
    pass_path="../../branch-recorder/build/libBranchRecorder.so"
    target_fun="mbedtls_mpi_exp_mod"
    opt -load "${pass_path}" \
        -load-pass-plugin="${pass_path}" \
        -passes=branch-recorder \
        -whitelist="${target_fun}" \
        "$1" -o "$1"
}

if [[ "$MODE" == "self_comp" ]]; then
    wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SYM_SIZE} -DSELF_COMP klee_main.c "${libs[@]}" -o self_comp_var_pub
    extract-bc self_comp_var_pub
    record_branch self_comp_var_pub.bc
    wllvm "${flags[@]}" "${klee_flags[@]}" -DSYM_SIZE=${SYM_SIZE} -DSELF_COMP -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o self_comp_fix_pub
    extract-bc self_comp_fix_pub
    record_branch self_comp_fix_pub.bc
fi
