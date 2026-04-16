#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

KLEE_PATH="../../klee-controlflow"

usage() {
    cat <<EOF
Usage: $0 (--klee-cf | --klee-eager | --self-comp | --binsec | --abacus) [--preset NAME]

Builds the BearSSL aes_big/des_tab benchmark wrappers for the requested mode.

Modes:
  --klee-cf     Build KLEE-CF executables and bitcode
  --klee-eager  Build KLEE-Eager executables and bitcode
  --self-comp   Build self-comp bitcode artifacts
  --binsec      Build BINSEC executables (32-bit)
  --abacus      Build Abacus executables (32-bit)

Options:
    --preset NAME  Optional preset name. If omitted, the sole preset in each config is used.
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
if [[ -n "$PRESET" ]] && ! [[ "$PRESET" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]]; then
    echo "Preset name contains unsupported characters: $PRESET" >&2
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
    -I "$repo_root/include"
    -I bearssl-0.6/inc
    -I bearssl-0.6/src
)

klee_flags=(
    -I "$KLEE_PATH/include"
    -L "$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib"
    -lkleeRuntest
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

bench_config_for_id() {
    local id="$1"
    case "$id" in
        binsec_aes_big)
            printf '%s\n' "$repo_root/configs/runner/bearssl_aes_big_runner_config.json"
            ;;
        appliedcryp_des)
            printf '%s\n' "$repo_root/configs/runner/bearssl_des_tab_runner_config.json"
            ;;
        *)
            return 1
            ;;
    esac
}

bench_generated_dir_for_id() {
    local id="$1"
    printf '%s\n' "$script_dir/generated/$id"
}

generate_runner_artifacts_for_id() {
    local id="$1"
    local generated_dir
    local generator_args

    generated_dir="$(bench_generated_dir_for_id "$id")"
    mkdir -p "$generated_dir"

    generator_args=(
        --config "$(bench_config_for_id "$id")"
        --header-out "$generated_dir/runner_config.generated.h"
    )

    if [[ -n "$PRESET" ]]; then
        generator_args+=(--preset "$PRESET")
    fi

    if [[ "$MODE" == "binsec" ]]; then
        generator_args+=(
            --binsec-base "$repo_root/configs/binsec/binsec_base.cfg"
            --binsec-fix-pub-out "$generated_dir/binsec_fix_pub.cfg"
            --binsec-var-pub-out "$generated_dir/binsec_var_pub.cfg"
        )
    fi

    python "$repo_root/tools/generate_runner_artifacts.py" "${generator_args[@]}"
}

record_branch() {
    local pass_path="../../branch-recorder/build/libBranchRecorder.so"
    opt -load "$pass_path" \
        -load-pass-plugin="$pass_path" \
        -passes=branch-recorder \
        "$1" -o "$1"
}

build_klee_mode() {
    local id="$1"
    local generated_dir
    local flags

    generate_runner_artifacts_for_id "$id"
    mapfile -t sources < <(bench_sources_for_id "$id")
    generated_dir="$(bench_generated_dir_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    local var_exe="klee_var_pub_${id}"
    local fix_exe="klee_fix_pub_${id}"
    local var_replay="klee_var_pub_replay_${id}"
    local fix_replay="klee_fix_pub_replay_${id}"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF "${sources[@]}" -o "$var_exe"
    extract-bc "$var_exe"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF -DCONCRETE_PUBS "${sources[@]}" -o "$fix_exe"
    extract-bc "$fix_exe"

    clang "${flags[@]}" -DREPLAY "${sources[@]}" -o "$var_replay"
    clang "${flags[@]}" -DREPLAY -DCONCRETE_PUBS "${sources[@]}" -o "$fix_replay"
}

build_self_comp_mode() {
    local id="$1"
    local generated_dir
    local flags

    generate_runner_artifacts_for_id "$id"
    mapfile -t sources < <(bench_sources_for_id "$id")
    generated_dir="$(bench_generated_dir_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    local var_exe="self_comp_var_pub_${id}"
    local fix_exe="self_comp_fix_pub_${id}"
    local var_replay="klee_var_pub_replay_${id}"
    local fix_replay="klee_fix_pub_replay_${id}"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP "${sources[@]}" -o "$var_exe"
    extract-bc "$var_exe"
    record_branch "$var_exe.bc"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP -DCONCRETE_PUBS "${sources[@]}" -o "$fix_exe"
    extract-bc "$fix_exe"
    record_branch "$fix_exe.bc"

    clang "${flags[@]}" -DREPLAY "${sources[@]}" -o "$var_replay"
    clang "${flags[@]}" -DREPLAY -DCONCRETE_PUBS "${sources[@]}" -o "$fix_replay"
}

build_binsec_mode() {
    local id="$1"
    local generated_dir
    local flags

    generate_runner_artifacts_for_id "$id"
    mapfile -t sources < <(bench_sources_for_id "$id")
    generated_dir="$(bench_generated_dir_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DBINSEC "${flags[@]}" "${sources[@]}" -o "binsec_var_pub_${id}"
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DBINSEC -DCONCRETE_PUBS "${flags[@]}" "${sources[@]}" -o "binsec_fix_pub_${id}"

    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DREPLAY "${flags[@]}" "${sources[@]}" -o "binsec_var_pub_replay_${id}"
    clang -g -O0 -m32 -static -fno-pie -fno-plt -Wl,-no-pie \
        -DREPLAY -DCONCRETE_PUBS "${flags[@]}" "${sources[@]}" -o "binsec_fix_pub_replay_${id}"
}

build_abacus_mode() {
    local id="$1"
    local generated_dir
    local flags

    generate_runner_artifacts_for_id "$id"
    mapfile -t sources < <(bench_sources_for_id "$id")
    generated_dir="$(bench_generated_dir_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    gcc -g -O0 -m32 -DABACUS "${flags[@]}" "${sources[@]}" -o "abacus_fix_pub_${id}"
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

printf 'Done. mode=%s preset=%s targets=%s\n' "$MODE" "${PRESET:-<default>}" "${#bench_ids[@]}"
