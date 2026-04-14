#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

usage() {
    cat <<EOF
Usage: $0 (--klee-cf | --klee-eager | --self-comp | --binsec | --abacus) --preset NAME

Builds Constantine MVP benchmarks for the requested mode.

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
    echo "Unsupported preset for Constantine build: $PRESET (expected size_N)" >&2
    exit 1
fi
if ! [[ "$SYM_SIZE" =~ ^[0-9]+$ ]]; then
    echo "Derived SYM_SIZE must be a non-negative integer, got: $SYM_SIZE" >&2
    exit 1
fi

if command -v wllvm >/dev/null 2>&1 && [[ -z "${LLVM_COMPILER:-}" ]]; then
    export LLVM_COMPILER=clang
fi

# Keep benchmark IDs stable across all experiment runners.
bench_ids=(
    "binsec_tls_rempad_luk13"
    "pycrypto_arc4"
)

bench_src_for_id() {
    local id="$1"
    case "$id" in
        binsec_tls_rempad_luk13)
            echo "binsec/tls-rempad-luk13.c"
            ;;
        pycrypto_arc4)
            echo "pycrypto/ARC4.c"
            ;;
        *)
            echo ""
            ;;
    esac
}

build_klee_mode() {
    local id="$1"
    local src="$2"

    local var_exe="klee_var_pub_${id}"
    local fix_exe="klee_fix_pub_${id}"
    local var_obj="${var_exe}.o"
    local fix_obj="${fix_exe}.o"

    # Constantine MVP sources may not be natively linkable standalone; generate bitcode from objects.
    wllvm -g -O0 -c -DSYM_SIZE="${SYM_SIZE}" "$src" -o "$var_obj"
    extract-bc "$var_obj"
    mv -f "${var_obj}.bc" "${var_exe}.bc"
    rm -f "$var_obj"

    # For Constantine MVP we start with identical fix/var binaries and refine public concretization later.
    wllvm -g -O0 -c -DSYM_SIZE="${SYM_SIZE}" -DCONCRETE_PUBS "$src" -o "$fix_obj"
    extract-bc "$fix_obj"
    mv -f "${fix_obj}.bc" "${fix_exe}.bc"
    rm -f "$fix_obj"
}

build_self_comp_mode() {
    local id="$1"
    local src="$2"

    local var_exe="self_comp_var_pub_${id}"
    local fix_exe="self_comp_fix_pub_${id}"
    local var_obj="${var_exe}.o"
    local fix_obj="${fix_exe}.o"

    wllvm -g -O0 -c -DSYM_SIZE="${SYM_SIZE}" -DSELF_COMP "$src" -o "$var_obj"
    extract-bc "$var_obj"
    mv -f "${var_obj}.bc" "${var_exe}.bc"
    rm -f "$var_obj"

    wllvm -g -O0 -c -DSYM_SIZE="${SYM_SIZE}" -DSELF_COMP -DCONCRETE_PUBS "$src" -o "$fix_obj"
    extract-bc "$fix_obj"
    mv -f "${fix_obj}.bc" "${fix_exe}.bc"
    rm -f "$fix_obj"
}

build_binsec_mode() {
    local id="$1"
    local src="$2"

    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie -DSYM_SIZE="${SYM_SIZE}" -DBINSEC "$src" -o "binsec_var_pub_${id}"
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie -DSYM_SIZE="${SYM_SIZE}" -DBINSEC -DCONCRETE_PUBS "$src" -o "binsec_fix_pub_${id}"

    # Replay binaries are built separately; BINSEC and REPLAY are treated as distinct modes.
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie -DSYM_SIZE="${SYM_SIZE}" -DREPLAY "$src" -o "binsec_var_pub_replay_${id}"
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie -DSYM_SIZE="${SYM_SIZE}" -DREPLAY -DCONCRETE_PUBS "$src" -o "binsec_fix_pub_replay_${id}"
}

build_abacus_mode() {
    local id="$1"
    local src="$2"

    gcc -g -O0 -m32 -DSYM_SIZE="${SYM_SIZE}" -DABACUS "$src" -o "abacus_fix_pub_${id}"
}

for id in "${bench_ids[@]}"; do
    src="$(bench_src_for_id "$id")"
    if [[ -z "$src" || ! -f "$src" ]]; then
        echo "Error: missing source for benchmark ID '$id' (resolved path '$src')" >&2
        exit 2
    fi

    echo "Building Constantine MVP benchmark: $id ($src)"
    case "$MODE" in
        klee_cf|klee_eager)
            build_klee_mode "$id" "$src"
            ;;
        self_comp)
            build_self_comp_mode "$id" "$src"
            ;;
        binsec)
            build_binsec_mode "$id" "$src"
            ;;
        abacus)
            build_abacus_mode "$id" "$src"
            ;;
        *)
            echo "Error: unsupported mode '$MODE'" >&2
            exit 2
            ;;
    esac
done

printf 'Done. mode=%s sym_size=%s targets=%s\n' "$MODE" "$SYM_SIZE" "${#bench_ids[@]}"
