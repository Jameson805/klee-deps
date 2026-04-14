#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

KLEE_PATH="../../klee-controlflow"

usage() {
    echo "Usage: $0 [--skip-deps] [--sliced] (--klee-cf | --binsec | --abacus | --self-comp) --preset NAME"
    echo "  --skip-deps    Skip building OpenSSL (Configure/make)"
    echo "  --sliced       Link crypto/bin/bn_exp.c -> crypto/bin/bn_exp_sliced.c (default: -> bn_exp_orig.c)"
    echo "  --klee-cf      Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries"
    echo "  --abacus       Build Abacus binaries"
    echo "  --self-comp    Build self-composition KLEE bitcode"
    echo "  --preset NAME  Select the preset to materialize into generated runner artifacts"
}

SKIP_DEPS=0
SLICED=0
MODE=""
PRESET=""

# Flags that reduce indirect control-flow artifacts (e.g., PLT indirections / PIE thunks).
# Note: `-no-pie` is a linker flag, so keep it in LDFLAGS for dependency builds.
NOIND_CFLAGS=( -fno-pie -fno-plt )
NOIND_LDFLAGS=( -Wl,-no-pie )
NOIND_EXE_FLAGS=( "${NOIND_CFLAGS[@]}" "${NOIND_LDFLAGS[@]}" )

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-deps)
            SKIP_DEPS=1
            shift
            ;;
        --sliced)
            SLICED=1
            shift
            ;;
        --klee-cf|--binsec|--abacus|--self-comp)
            if [[ -n "$MODE" ]]; then
                echo "Multiple build modes specified. Choose exactly one of --klee-cf, --binsec, --abacus, --self-comp."
                exit 1
            fi
            case "$1" in
                --klee-cf)   MODE="klee_cf"   ;;
                --binsec)    MODE="binsec"    ;;
                --abacus)    MODE="abacus"    ;;
                --self-comp) MODE="self_comp" ;;
            esac
            shift
            ;;
        --preset)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --preset"
                exit 1
            fi
            if [[ -n "$PRESET" && "$PRESET" != "$2" ]]; then
                echo "Multiple preset values specified: $PRESET and $2"
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
if [[ -z "$PRESET" ]]; then
    echo "Missing required preset. Use --preset NAME."
    usage
    exit 1
fi
if ! [[ "$PRESET" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]]; then
    echo "Preset name contains unsupported characters: $PRESET"
    exit 1
fi

ensure_bn_exp_link() {
    local bn_dir="crypto/bn"
    local link_path="${bn_dir}/bn_exp.c"
    local target="${bn_dir}/$1"

    if [[ ! -d "${bn_dir}" ]]; then
        echo "Expected OpenSSL directory '${bn_dir}' not found"
        exit 1
    fi
    if [[ ! -f "${target}" ]]; then
        echo "Expected target '${target}' not found"
        exit 1
    fi

    cp -f "${target}" "${link_path}"
    echo "copy ${target} -> ${link_path}"
}

if [[ "$SLICED" -eq 1 ]]; then
    ensure_bn_exp_link "bn_exp_sliced.c"
else
    ensure_bn_exp_link "bn_exp_orig.c"
fi

mkdir -p generated
generator_args=(
    --config "$repo_root/configs/runner/modexp_runner_config.json"
    --header-out "$script_dir/generated/runner_config.generated.h"
    --preset "$PRESET"
)

if [[ "$MODE" == "binsec" ]]; then
    generator_args+=(
        --binsec-base "$repo_root/configs/binsec/binsec_base.cfg"
        --binsec-fix-pub-out "$script_dir/generated/binsec_fix_pub.cfg"
        --binsec-var-pub-out "$script_dir/generated/binsec_var_pub.cfg"
    )
fi

python "$repo_root/tools/generate_runner_artifacts.py" "${generator_args[@]}"

if [ "$SKIP_DEPS" -eq 0 ]; then
    echo "Building dependencies..."

    CC=clang
    if [[ "$MODE" == "abacus" ]]; then
        CC=gcc
    elif [[ "$MODE" == "klee_cf" || "$MODE" == "self_comp" ]]; then
        export LLVM_COMPILER=clang
        CC=wllvm
    fi

    CFLAGS=( -g -O0 )
    LDFLAGS=( )
    ARCH_FLAGS=( linux-generic64 )
    if [[ "$MODE" == "binsec" || "$MODE" == "abacus" ]]; then
        CFLAGS+=( -m32 )
        LDFLAGS+=( -m32 )
        ARCH_FLAGS=( linux-generic32 )
    fi
    if [[ "$MODE" == "binsec" ]]; then
        CFLAGS+=( "${NOIND_CFLAGS[@]}" )
        LDFLAGS+=( "${NOIND_LDFLAGS[@]}" )
    fi

    # The no-asm part of the code will be constant time
    ./Configure no-shared no-asm no-tests -DOPENSSL_AES_CONST_TIME "${ARCH_FLAGS[@]}"
    make clean
    make CC=${CC} CFLAGS="${CFLAGS[*]}" LDFLAGS="${LDFLAGS[*]}" -j
else
    echo "Skipping dependency builds."
fi

flags=( -g -O0 -I"$repo_root/include" -Iinclude -Igenerated )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( libcrypto.a )

record_branch() {
    pass_path="../../branch-recorder/build/libBranchRecorder.so"
    opt -load "${pass_path}" \
        -load-pass-plugin="${pass_path}" \
        -passes=branch-recorder \
        "$1" -o "$1"
}

algos=( recp mont mont_consttime mont_word )
for algo in "${algos[@]}"; do
    macro=$(echo "$algo" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')

    if [[ "$MODE" == "klee_cf" ]]; then
        # KLEE-controlflow bitcode builds
        wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF -D${macro} klee_main.c "${libs[@]}" -o "klee_var_pub_${algo}"
        extract-bc "klee_var_pub_${algo}"
        wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF -D${macro} -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_${algo}"
        extract-bc "klee_fix_pub_${algo}"

        # Replay builds
        clang "${flags[@]}" -static -D${macro} -DREPLAY klee_main.c "${libs[@]}" -o "klee_var_pub_replay_${algo}"
        clang "${flags[@]}" -static -D${macro} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_replay_${algo}"
    fi

    if [[ "$MODE" == "binsec" ]]; then
        # BINSEC builds
        clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DBINSEC klee_main.c "${libs[@]}" -o "binsec_var_pub_${algo}"
        clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "binsec_fix_pub_${algo}"

        # Replay binaries for BINSEC (built separately; REPLAY and BINSEC are mutually exclusive)
        clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DREPLAY klee_main.c "${libs[@]}" -o "binsec_var_pub_replay_${algo}"
        clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "binsec_fix_pub_replay_${algo}"
    fi

    if [[ "$MODE" == "abacus" ]]; then
        # Abacus builds
        gcc "${flags[@]}" -m32 -pthread -D${macro} -DABACUS klee_main.c "${libs[@]}" -ldl -o "abacus_fix_pub_${algo}"
    fi

    if [[ "$MODE" == "self_comp" ]]; then
        case "$algo" in
            recp)           fun="BN_mod_exp_recp" ;;
            mont)           fun="BN_mod_exp_mont" ;;
            mont_consttime) fun="BN_mod_exp_mont_consttime" ;;
            mont_word)      fun="BN_mod_exp_mont_word" ;;
        esac

        wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP -D${macro} klee_main.c "${libs[@]}" -o "self_comp_var_pub_${algo}"
        extract-bc "self_comp_var_pub_${algo}"
        record_branch "self_comp_var_pub_${algo}.bc" "${fun}"

        wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP -D${macro} -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "self_comp_fix_pub_${algo}"
        extract-bc "self_comp_fix_pub_${algo}"
        record_branch "self_comp_fix_pub_${algo}.bc" "${fun}"
    fi
done
