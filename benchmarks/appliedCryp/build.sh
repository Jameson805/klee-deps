#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

KLEE_PATH="../../klee-controlflow"

resolve_runner_config_path() {
    local profile_id="$1"
    python "$repo_root/tools/resolve_runner_profile.py" \
    --library "appliedcryp" \
    --variant "default" \
        --profile "$profile_id" \
        --field config
}

usage() {
    cat <<EOF
Usage: $0 (--klee | --self-comp | --binsec | --abacus) [--preset NAME]

Builds the appliedCryp 3way/des/loki91 benchmark wrappers for the requested mode.

Modes:
    --klee        Build KLEE executables and bitcode
  --self-comp   Build self-comp bitcode artifacts
  --binsec      Build BINSEC executables (32-bit)
  --abacus      Build Abacus executables (32-bit)

Options:
    --preset NAME  Optional preset name. If omitted, the sole preset in each config is used.
EOF
}

MODE=""
PRESET=""

NOIND_CFLAGS=(
    -fno-pie
    -fno-plt
)
NOIND_LDFLAGS=()
NOIND_EXE_FLAGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --klee)
            MODE="klee"
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

if [[ "$MODE" == "abacus" ]]; then
    NOIND_LDFLAGS=( -no-pie )
else
    NOIND_LDFLAGS=( -Wl,-no-pie )
fi
NOIND_EXE_FLAGS=( "${NOIND_CFLAGS[@]}" "${NOIND_LDFLAGS[@]}" )

if command -v wllvm >/dev/null 2>&1 && [[ -z "${LLVM_COMPILER:-}" ]]; then
    export LLVM_COMPILER=clang
fi

bench_ids=(
    "3way"
    "des"
    "loki91"
)

common_flags=(
    -g
    -O0
    -std=gnu89
    -I "$repo_root/include"
)

klee_flags=(
    -I "$KLEE_PATH/include"
    -L "$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib"
    -lkleeRuntest
)

bench_wrapper_for_id() {
    local id="$1"
    case "$id" in
        3way)
            printf '%s\n' 3way_wrapper.c
            ;;
        des)
            printf '%s\n' des_wrapper.c
            ;;
        loki91)
            printf '%s\n' loki91_wrapper.c
            ;;
        *)
            return 1
            ;;
    esac
}

bench_config_for_id() {
    local id="$1"
    case "$id" in
        3way)
            resolve_runner_config_path "3way"
            ;;
        des)
            resolve_runner_config_path "des"
            ;;
        loki91)
            resolve_runner_config_path "loki91"
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
    local wrapper
    local flags

    generate_runner_artifacts_for_id "$id"
    generated_dir="$(bench_generated_dir_for_id "$id")"
    wrapper="$(bench_wrapper_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    local var_exe="klee_var_pub_${id}"
    local fix_exe="klee_fix_pub_${id}"
    local var_replay="klee_var_pub_replay_${id}"
    local fix_replay="klee_fix_pub_replay_${id}"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF "$wrapper" -o "$var_exe"
    extract-bc "$var_exe"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF -DCONCRETE_PUBS "$wrapper" -o "$fix_exe"
    extract-bc "$fix_exe"

    clang "${flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DREPLAY "$wrapper" -o "$var_replay"
    clang "${flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS "$wrapper" -o "$fix_replay"
}

build_self_comp_mode() {
    local id="$1"
    local generated_dir
    local wrapper
    local flags

    generate_runner_artifacts_for_id "$id"
    generated_dir="$(bench_generated_dir_for_id "$id")"
    wrapper="$(bench_wrapper_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    local var_exe="self_comp_var_pub_${id}"
    local fix_exe="self_comp_fix_pub_${id}"
    local var_replay="klee_var_pub_replay_${id}"
    local fix_replay="klee_fix_pub_replay_${id}"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP "$wrapper" -o "$var_exe"
    extract-bc "$var_exe"
    record_branch "$var_exe.bc"

    wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP -DCONCRETE_PUBS "$wrapper" -o "$fix_exe"
    extract-bc "$fix_exe"
    record_branch "$fix_exe.bc"

    clang "${flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DREPLAY "$wrapper" -o "$var_replay"
    clang "${flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS "$wrapper" -o "$fix_replay"
}

build_binsec_mode() {
    local id="$1"
    local generated_dir
    local wrapper
    local flags

    generate_runner_artifacts_for_id "$id"
    generated_dir="$(bench_generated_dir_for_id "$id")"
    wrapper="$(bench_wrapper_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    local var_exe="binsec_var_pub_${id}"
    local fix_exe="binsec_fix_pub_${id}"
    local var_replay="binsec_var_pub_replay_${id}"
    local fix_replay="binsec_fix_pub_replay_${id}"

    clang -g -O0 -m32 -static "${NOIND_EXE_FLAGS[@]}" \
        -DBINSEC "${flags[@]}" "$wrapper" -o "$var_exe"
    clang -g -O0 -m32 -static "${NOIND_EXE_FLAGS[@]}" \
        -DBINSEC -DCONCRETE_PUBS "${flags[@]}" "$wrapper" -o "$fix_exe"

    clang -g -O0 -m32 -static "${NOIND_EXE_FLAGS[@]}" \
        -DREPLAY "${flags[@]}" "$wrapper" -o "$var_replay"
    clang -g -O0 -m32 -static "${NOIND_EXE_FLAGS[@]}" \
        -DREPLAY -DCONCRETE_PUBS "${flags[@]}" "$wrapper" -o "$fix_replay"
}

build_abacus_mode() {
    local id="$1"
    local generated_dir
    local wrapper
    local flags

    generate_runner_artifacts_for_id "$id"
    generated_dir="$(bench_generated_dir_for_id "$id")"
    wrapper="$(bench_wrapper_for_id "$id")"
    flags=("${common_flags[@]}" -I "$generated_dir")

    gcc -g -O0 -m32 -DABACUS -DCONCRETE_PUBS "${flags[@]}" "$wrapper" -o "abacus_fix_pub_${id}"
}

for id in "${bench_ids[@]}"; do
    echo "Building appliedCryp benchmark: $id"
    case "$MODE" in
        klee)
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
