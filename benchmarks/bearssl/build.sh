#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$script_dir"

usage() {
    cat <<EOF
Usage: $0 (--klee-cf | --klee-eager | --self-comp | --binsec | --abacus) --preset NAME

Builds the BearSSL aes_big/des_tab benchmark wrappers for the requested mode.

Modes:
  --klee-cf     Build KLEE-CF executables and bitcode
  --klee-eager  Build KLEE-Eager executables and bitcode
  --self-comp   Build self-comp bitcode artifacts
  --binsec      Build BINSEC executables (32-bit)
  --abacus      Build Abacus executables (32-bit)

Options:
    --preset NAME  Mandatory preset name. Current build logic expects size_N.
EOF
}

MODE=""
PRESET=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --klee-cf)
            MODE="klee_cf"
            shift
            ;;
        --klee-eager)
            MODE="klee_eager"
            shift
            ;;
        --self-comp)
            MODE="self_comp"
            shift
            ;;
        --binsec)
            MODE="binsec"
            shift
            ;;
        --abacus)
            MODE="abacus"
            shift
            ;;
        --preset)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --preset" >&2
                exit 1
            fi
            PRESET="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option or unexpected argument: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$MODE" ]]; then
    echo "Missing build mode" >&2
    usage
    exit 1
fi
if [[ -z "$PRESET" ]]; then
    echo "Missing required --preset argument" >&2
    usage
    exit 1
fi
if [[ "$PRESET" =~ ^size_([0-9]+)$ ]]; then
    SYM_SIZE="${BASH_REMATCH[1]}"
else
    echo "Unsupported preset for BearSSL build: $PRESET (expected size_N)" >&2
    exit 1
fi
if ! [[ "$SYM_SIZE" =~ ^[0-9]+$ ]]; then
    echo "Derived SYM_SIZE must be a non-negative integer, got: $SYM_SIZE" >&2
    exit 1
fi

if command -v wllvm >/dev/null 2>&1 && [[ -z "${LLVM_COMPILER:-}" ]]; then
    export LLVM_COMPILER=clang
fi

bench_ids=(
    "binsec_aes_big"
    "appliedcryp_des"
)

common_flags=(
    -g
    -O0
    -DSYM_SIZE="${SYM_SIZE}"
    -I bearssl-0.6/inc
    -I bearssl-0.6/src
)

bench_sources_for_id() {
    local id="$1"
    case "$id" in
        binsec_aes_big)
            printf '%s\n' \
                aes_big_wrapper.c \
                bearssl-0.6/src/symcipher/aes_big_cbcenc.c \
                bearssl-0.6/src/symcipher/aes_big_enc.c \
                bearssl-0.6/src/symcipher/aes_common.c
            ;;
        appliedcryp_des)
            printf '%s\n' \
                des_tab_wrapper.c \
                bearssl-0.6/src/symcipher/des_tab_cbcenc.c \
                bearssl-0.6/src/symcipher/des_tab.c \
                bearssl-0.6/src/symcipher/des_support.c
            ;;
        *)
            return 1
            ;;
    esac
}

build_klee_mode() {
    local id="$1"
    mapfile -t sources < <(bench_sources_for_id "$id")

    local var_exe="klee_var_pub_${id}"
    local fix_exe="klee_fix_pub_${id}"

    wllvm "${common_flags[@]}" "${sources[@]}" -o "$var_exe"
    extract-bc "$var_exe"

    wllvm "${common_flags[@]}" -DCONCRETE_PUBS "${sources[@]}" -o "$fix_exe"
    extract-bc "$fix_exe"
}

build_self_comp_mode() {
    local id="$1"
    mapfile -t sources < <(bench_sources_for_id "$id")

    local var_exe="self_comp_var_pub_${id}"
    local fix_exe="self_comp_fix_pub_${id}"

    wllvm "${common_flags[@]}" -DSELF_COMP "${sources[@]}" -o "$var_exe"
    extract-bc "$var_exe"

    wllvm "${common_flags[@]}" -DSELF_COMP -DCONCRETE_PUBS "${sources[@]}" -o "$fix_exe"
    extract-bc "$fix_exe"
}

build_binsec_mode() {
    local id="$1"
    mapfile -t sources < <(bench_sources_for_id "$id")

    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DBINSEC "${common_flags[@]}" "${sources[@]}" -o "binsec_var_pub_${id}"
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DBINSEC -DCONCRETE_PUBS "${common_flags[@]}" "${sources[@]}" -o "binsec_fix_pub_${id}"

    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DREPLAY "${common_flags[@]}" "${sources[@]}" -o "binsec_var_pub_replay_${id}"
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DREPLAY -DCONCRETE_PUBS "${common_flags[@]}" "${sources[@]}" -o "binsec_fix_pub_replay_${id}"
}

build_abacus_mode() {
    local id="$1"
    mapfile -t sources < <(bench_sources_for_id "$id")

    gcc -g -O0 -m32 -DABACUS "${common_flags[@]}" "${sources[@]}" -o "abacus_fix_pub_${id}"
}

for id in "${bench_ids[@]}"; do
    echo "Building BearSSL benchmark: $id"
    case "$MODE" in
        klee_cf|klee_eager)
            build_klee_mode "$id"
            ;;
        self_comp)
            build_self_comp_mode "$id"
            ;;
        binsec)
            build_binsec_mode "$id"
            ;;
        abacus)
            build_abacus_mode "$id"
            ;;
        *)
            echo "Error: unsupported mode '$MODE'" >&2
            exit 2
            ;;
    esac
done

printf 'Done. mode=%s sym_size=%s targets=%s\n' "$MODE" "$SYM_SIZE" "${#bench_ids[@]}"