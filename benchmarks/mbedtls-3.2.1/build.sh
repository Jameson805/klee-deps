#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

source "$repo_root/scripts/shared/klee_tool_env.sh"
load_klee_tool_layout "$repo_root"

resolve_runner_config_path() {
    local variant="default"
    python -m tools.resolve_runner_profile \
        --library "mbedtls" \
        --variant "$variant" \
        --field config
}

usage() {
    echo "Usage: $0 [--skip-deps] (--klee | --binsec | --abacus) --preset NAME"
    echo "  --skip-deps    Skip building libgpg-error and libgcrypt"
    echo "  --klee         Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries"
    echo "  --abacus       Build Abacus binaries"
    echo "  --preset NAME  Select the preset to materialize into generated runner artifacts"
}

SKIP_DEPS=0
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
        --klee|--binsec|--abacus)
            if [[ -n "$MODE" ]]; then
                echo "Multiple build modes specified. Choose exactly one of --klee, --binsec, or --abacus."
                exit 1
            fi
            case "$1" in
                --klee)      MODE="klee" ;;
                --binsec)    MODE="binsec"  ;;
                --abacus)    MODE="abacus"  ;;
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

if command -v wllvm >/dev/null 2>&1 && [[ -z "${LLVM_COMPILER:-}" ]]; then
    export LLVM_COMPILER=clang
fi

mkdir -p generated
generator_args=(
    --config "$(resolve_runner_config_path)"
    --header-out "$script_dir/generated/modexp/runner_config.generated.h"
    --preset "$PRESET"
)

if [[ "$MODE" == "binsec" ]]; then
    mkdir -p "$script_dir/generated/modexp"
    generator_args+=(
        --binsec-base "$repo_root/configs/binsec/binsec_base.cfg"
        --binsec-fix-pub-out "$script_dir/generated/modexp/binsec_fix_pub.cfg"
        --binsec-var-pub-out "$script_dir/generated/modexp/binsec_var_pub.cfg"
    )
fi

mkdir -p "$script_dir/generated/modexp"

python -m tools.generate_runner_artifacts "${generator_args[@]}"

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
    if [[ "$MODE" == "binsec" || "$MODE" == "abacus" ]]; then
        CFLAGS+=( -m32 )
        LDFLAGS+=( -m32 )
    fi
    CFLAGS+=( "${NOIND_CFLAGS[@]}" )
    LDFLAGS+=( "${NOIND_LDFLAGS[@]}" )

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

flags=( -g -O0 -I"$repo_root/include" -Iinclude -Igenerated/modexp )
klee_flags=(\
    -I"$KLEE_TOOL_INCLUDE_DIR" \
    -L"$KLEE_TOOL_RUNTIME_LIB_DIR" -Wl,-rpath="$KLEE_TOOL_RUNTIME_LIB_DIR" \
    -lkleeRuntest \
)
libs=( build/library/libmbedtls.a build/library/libmbedx509.a build/library/libmbedcrypto.a )

if [[ "$MODE" == "klee" ]]; then
    # KLEE bitcode builds
    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DKLEE_CF klee_main.c "${libs[@]}" -o klee_var_pub_modexp
    extract-bc klee_var_pub_modexp
    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DKLEE_CF -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_modexp
    extract-bc klee_fix_pub_modexp

    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DKLEE_CF klee_main.c bignum_sliced.c "${libs[@]}" -o klee_var_pub_modexp_sliced
    extract-bc klee_var_pub_modexp_sliced
    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DKLEE_CF -DCONCRETE_PUBS klee_main.c bignum_sliced.c "${libs[@]}" -o klee_fix_pub_modexp_sliced
    extract-bc klee_fix_pub_modexp_sliced

    # Replay builds
    clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay_modexp
    clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay_modexp

    clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DREPLAY klee_main.c bignum_sliced.c "${libs[@]}" -o klee_var_pub_replay_modexp_sliced
    clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DREPLAY -DCONCRETE_PUBS klee_main.c bignum_sliced.c "${libs[@]}" -o klee_fix_pub_replay_modexp_sliced
fi

if [[ "$MODE" == "binsec" ]]; then
    # BINSEC builds
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DBINSEC klee_main.c "${libs[@]}" -o binsec_var_pub_modexp
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub_modexp

    # Replay binaries for BINSEC (built separately; REPLAY and BINSEC are mutually exclusive)
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY klee_main.c "${libs[@]}" -o binsec_var_pub_replay_modexp
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub_replay_modexp
fi

if [[ "$MODE" == "abacus" ]]; then
    # Abacus builds
    gcc "${flags[@]}" -m32 "${NOIND_EXE_FLAGS[@]}" -DABACUS klee_main.c "${libs[@]}" -o abacus_fix_pub_modexp
fi

