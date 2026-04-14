#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

KLEE_PATH="../../klee-controlflow"

usage() {
    echo "Usage: $0 [--skip-deps] (--klee-cf | --binsec | --abacus | --self-comp) --preset NAME"
    echo "  --skip-deps    Skip building libgpg-error and libgcrypt"
    echo "  --klee-cf      Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries"
    echo "  --abacus       Build Abacus binaries"
    echo "  --self-comp    Build self-composition KLEE bitcode"
    echo "  --preset NAME  Select the preset to materialize into generated runner artifacts"
}

SKIP_DEPS=0
MODE=""
PRESET=""

# Flags that reduce indirect control-flow artifacts (e.g., PLT indirections / PIE thunks).
# Note: `-no-pie` is a linker flag, so keep it in LDFLAGS for library builds.
NOIND_CFLAGS=( -fno-pie -fno-plt )
NOIND_LDFLAGS=( -Wl,-no-pie )
NOIND_EXE_FLAGS=( "${NOIND_CFLAGS[@]}" "${NOIND_LDFLAGS[@]}" )

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

if command -v wllvm >/dev/null 2>&1 && [[ -z "${LLVM_COMPILER:-}" ]]; then
    export LLVM_COMPILER=clang
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
    if [[ "$MODE" == "binsec" || "$MODE" == "abacus" ]]; then
        CFLAGS+=( -m32 )
        LDFLAGS+=( -m32 )
    fi
    if [[ "$MODE" == "binsec" ]]; then
        CFLAGS+=( "${NOIND_CFLAGS[@]}" )
        LDFLAGS+=( "${NOIND_LDFLAGS[@]}" )
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

flags=( -g -O0 -I"$repo_root/include" -Iinclude -Igenerated )
klee_flags=(\
    -I"$KLEE_PATH/include" \
    -L"$KLEE_PATH/build/lib" -Wl,-rpath="$KLEE_PATH/build/lib" \
    -lkleeRuntest \
)
libs=( build/library/libmbedtls.a build/library/libmbedx509.a build/library/libmbedcrypto.a )

if [[ "$MODE" == "klee_cf" ]]; then
    # KLEE-controlflow bitcode builds
    wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF klee_main.c "${libs[@]}" -o klee_var_pub
    extract-bc klee_var_pub
    wllvm "${flags[@]}" "${klee_flags[@]}" -DKLEE_CF -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub
    extract-bc klee_fix_pub

    wllvm "${flags[@]}" "${klee_flags[@]}" -DUSE_SLICED -DKLEE_CF klee_main.c bignum_sliced.c "${libs[@]}" -o klee_var_pub_sliced
    extract-bc klee_var_pub_sliced
    wllvm "${flags[@]}" "${klee_flags[@]}" -DUSE_SLICED -DKLEE_CF -DCONCRETE_PUBS klee_main.c bignum_sliced.c "${libs[@]}" -o klee_fix_pub_sliced
    extract-bc klee_fix_pub_sliced

    # Replay builds
    clang "${flags[@]}" -static -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay
    clang "${flags[@]}" -static -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay

    clang "${flags[@]}" -static -DUSE_SLICED -DREPLAY klee_main.c bignum_sliced.c "${libs[@]}" -o klee_var_pub_sliced_replay
    clang "${flags[@]}" -static -DUSE_SLICED -DREPLAY -DCONCRETE_PUBS klee_main.c bignum_sliced.c "${libs[@]}" -o klee_fix_pub_sliced_replay
fi

if [[ "$MODE" == "binsec" ]]; then
    # BINSEC builds
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DBINSEC klee_main.c "${libs[@]}" -o binsec_var_pub
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub

    # Replay binaries for BINSEC (built separately; REPLAY and BINSEC are mutually exclusive)
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY klee_main.c "${libs[@]}" -o binsec_var_pub_replay
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub_replay
fi

if [[ "$MODE" == "abacus" ]]; then
    # Abacus builds
    gcc "${flags[@]}" -m32 -DABACUS klee_main.c "${libs[@]}" -o abacus_fix_pub
fi

record_branch() {
    pass_path="../../branch-recorder/build/libBranchRecorder.so"
    opt -load "${pass_path}" \
        -load-pass-plugin="${pass_path}" \
        -passes=branch-recorder \
        "$1" -o "$1"
}

if [[ "$MODE" == "self_comp" ]]; then
    wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP klee_main.c "${libs[@]}" -o self_comp_var_pub
    extract-bc self_comp_var_pub
    record_branch self_comp_var_pub.bc
    wllvm "${flags[@]}" "${klee_flags[@]}" -DSELF_COMP -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o self_comp_fix_pub
    extract-bc self_comp_fix_pub
    record_branch self_comp_fix_pub.bc
fi
