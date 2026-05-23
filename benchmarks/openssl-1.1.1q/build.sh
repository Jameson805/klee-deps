#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

source "$repo_root/scripts/shared/klee_tool_env.sh"
load_klee_tool_layout "$repo_root"

resolve_runner_config_path() {
    local variant="default"
    if [[ "$SLICED" -eq 1 ]]; then
        variant="sliced"
    fi
    python -m tools.resolve_runner_profile \
        --library "openssl" \
        --variant "$variant" \
        --field config
}

usage() {
    echo "Usage: $0 [--skip-deps] [--sliced] (--klee | --binsec | --abacus) --preset NAME"
    echo "  --skip-deps    Skip building OpenSSL (Configure/make)"
    echo "  --sliced       Link crypto/bin/bn_exp.c -> crypto/bin/bn_exp_sliced.c (default: -> bn_exp_orig.c)"
    echo "  --klee         Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries (native arch)"
    echo "  --abacus       Build Abacus binaries"
    echo "  --preset NAME  Select the preset to materialize into generated runner artifacts"
}

SKIP_DEPS=0
SLICED=0
MODE=""
PRESET=""

# Flags that reduce indirect control-flow artifacts (e.g., PLT indirections / PIE thunks).
# Use a compiler-specific link flag so gcc keeps `-no-pie` while clang/wllvm get
# the linker-prefixed form they forward correctly.
NOIND_CFLAGS=( -fno-pie -fno-plt )
NOIND_LDFLAGS=()
NOIND_EXE_FLAGS=()

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
        --klee|--binsec|--abacus)
            if [[ -n "$MODE" ]]; then
                echo "Multiple build modes specified. Choose exactly one of --klee, --binsec, or --abacus."
                exit 1
            fi
            case "$1" in
                --klee)      MODE="klee"      ;;
                --binsec)    MODE="binsec"    ;;
                --abacus)    MODE="abacus"    ;;
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
    echo "Missing required build mode. Choose exactly one of --klee, --binsec, or --abacus."
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

if [[ "$MODE" == "abacus" ]]; then
    NOIND_LDFLAGS=( -no-pie )
else
    NOIND_LDFLAGS=( -Wl,-no-pie )
fi
NOIND_EXE_FLAGS=( "${NOIND_CFLAGS[@]}" "${NOIND_LDFLAGS[@]}" )

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

generator_args=(
    --config "$(resolve_runner_config_path)"
    --preset "$PRESET"
)

if [ "$SKIP_DEPS" -eq 0 ]; then
    echo "Building dependencies..."

    CC=clang
    if [[ "$MODE" == "abacus" ]]; then
        CC=gcc
    elif [[ "$MODE" == "klee" ]]; then
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
    CFLAGS+=( "${NOIND_CFLAGS[@]}" )
    LDFLAGS+=( "${NOIND_LDFLAGS[@]}" )

    # The no-asm part of the code will be constant time
    ./Configure no-shared no-asm no-tests -DOPENSSL_AES_CONST_TIME "${ARCH_FLAGS[@]}"
    make clean
    make CC=${CC} CFLAGS="${CFLAGS[*]}" LDFLAGS="${LDFLAGS[*]}" -j
else
    echo "Skipping dependency builds."
fi

flags_base=( -g -O0 -I"$repo_root/include" -Iinclude )
klee_flags=(\
    -I"$KLEE_TOOL_INCLUDE_DIR" \
    -L"$KLEE_TOOL_RUNTIME_LIB_DIR" -Wl,-rpath="$KLEE_TOOL_RUNTIME_LIB_DIR" \
    -lkleeRuntest \
)
libs=( libcrypto.a )

algos=( recp mont mont_consttime mont_word )
for algo in "${algos[@]}"; do
    macro=$(echo "$algo" | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9]/_/g')
    generated_dir="$script_dir/generated/$algo"
    mkdir -p "$generated_dir"

    tool_flags=( "${flags_base[@]}" -I"$generated_dir" )
    generator_args_for_algo=(
        "${generator_args[@]}"
        --header-out "$generated_dir/runner_config.generated.h"
    )
    if [[ "$MODE" == "binsec" ]]; then
        generator_args_for_algo+=(
            --binsec-base "$repo_root/configs/binsec/binsec_base.cfg"
            --binsec-fix-pub-out "$generated_dir/binsec_fix_pub.cfg"
            --binsec-var-pub-out "$generated_dir/binsec_var_pub.cfg"
        )
    fi
    python -m tools.generate_runner_artifacts "${generator_args_for_algo[@]}"

    if [[ "$MODE" == "klee" ]]; then
        # KLEE bitcode builds
        wllvm "${tool_flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DKLEE_CF -D${macro} klee_main.c "${libs[@]}" -o "klee_var_pub_${algo}"
        extract-bc "klee_var_pub_${algo}"
        wllvm "${tool_flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DKLEE_CF -D${macro} -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_${algo}"
        extract-bc "klee_fix_pub_${algo}"

        # Replay builds
        clang "${tool_flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DREPLAY klee_main.c "${libs[@]}" -o "klee_var_pub_replay_${algo}"
        clang "${tool_flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "klee_fix_pub_replay_${algo}"
    fi

    if [[ "$MODE" == "binsec" ]]; then
        # BINSEC builds
        clang "${tool_flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DBINSEC klee_main.c "${libs[@]}" -o "binsec_var_pub_${algo}"
        clang "${tool_flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "binsec_fix_pub_${algo}"

        # Replay binaries for BINSEC (built separately; REPLAY and BINSEC are mutually exclusive)
        clang "${tool_flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DREPLAY klee_main.c "${libs[@]}" -o "binsec_var_pub_replay_${algo}"
        clang "${tool_flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -D${macro} -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o "binsec_fix_pub_replay_${algo}"
    fi

    if [[ "$MODE" == "abacus" ]]; then
        # Abacus builds
        gcc "${tool_flags[@]}" -m32 -pthread "${NOIND_EXE_FLAGS[@]}" -D${macro} -DABACUS klee_main.c "${libs[@]}" -ldl -o "abacus_fix_pub_${algo}"
    fi

done
