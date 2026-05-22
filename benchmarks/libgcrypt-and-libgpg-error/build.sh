#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

export PATH="/usr/lib/llvm-13/bin:$PATH"
export CC=wllvm
export LLVM_COMPILER=clang

source "$repo_root/scripts/shared/klee_tool_env.sh"
load_klee_tool_layout "$repo_root"

resolve_runner_config_path() {
    local variant="default"
    if [[ "$SLICED" -eq 1 ]]; then
        variant="sliced"
    fi
    python -m tools.resolve_runner_profile \
        --library "libgcrypt" \
        --variant "$variant" \
        --field config
}

usage() {
    echo "Usage: $0 [--skip-deps] [--sliced] (--klee | --binsec | --abacus) --preset NAME"
    echo "  --skip-deps    Skip building libgpg-error and libgcrypt"
    echo "  --sliced       Build libgcrypt-1.10.1-sliced instead of libgcrypt-1.10.1"
    echo "  --klee         Build KLEE bitcode and Replay binaries"
    echo "  --binsec       Build BINSEC binaries"
    echo "  --abacus       Build Abacus binaries"
    echo "  --preset NAME  Select the preset to materialize into generated runner artifacts"
}

SKIP_DEPS=0
SLICED=0
MODE=""
PRESET=""

# Flags that reduce indirect control-flow artifacts (e.g., PLT indirections / PIE thunks).
# We also force "no PIE" through the compiler driver. Since some autotools projects
# build shared libraries by default, we configure deps with --disable-shared
# (static-only) so this flag cannot accidentally affect a shared-library link.
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

install_root=$(realpath "./build")

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
    LDFLAGS=()
    ARCH_FLAGS=()
    if [[ "$MODE" == "binsec" || "$MODE" == "abacus" ]]; then
        CFLAGS+=( -m32 )
        LDFLAGS+=( -m32 )
        ARCH_FLAGS+=( --host=i686-pc-linux-gnu )
    fi
    CFLAGS+=( "${NOIND_CFLAGS[@]}" )
    LDFLAGS+=( "${NOIND_LDFLAGS[@]}" )

    CONFIGURE_STATIC_ONLY_FLAGS=( --enable-static --disable-shared )

    cd libgpg-error-1.44
    ./configure CC=${CC} CFLAGS="${CFLAGS[*]}" LDFLAGS="${LDFLAGS[*]}" \
        "${CONFIGURE_STATIC_ONLY_FLAGS[@]}" \
        --disable-doc \
        --prefix="${install_root}" \
        "${ARCH_FLAGS[@]}"
    make clean
    make -j
    make install
    cd -

    LIBGCRYPT_DIR="libgcrypt-1.10.1"
    if [ "$SLICED" -eq 1 ]; then
        LIBGCRYPT_DIR="libgcrypt-1.10.1-sliced"
    fi
    cd "$LIBGCRYPT_DIR"
    CFLAGS+=( -DNO_ASM )
    ./configure CC=${CC} CFLAGS="${CFLAGS[*]}" LDFLAGS="${LDFLAGS[*]}" \
        "${CONFIGURE_STATIC_ONLY_FLAGS[@]}" \
        --disable-asm \
        --disable-doc \
        --with-sysroot="${install_root}" \
        --prefix="${install_root}" \
        "${ARCH_FLAGS[@]}"
    make clean
    make -j
    make install
    cd -
else
    echo "Skipping dependency builds."
fi

# Flags and libraries
flags=( -g -O0 -I"$repo_root/include" -Igenerated/modexp -isystem "${install_root}/include" )
klee_flags=( -I"$KLEE_TOOL_INCLUDE_DIR" -L"$KLEE_TOOL_RUNTIME_LIB_DIR" -Wl,-rpath="$KLEE_TOOL_RUNTIME_LIB_DIR" -lkleeRuntest )
libs=( "${install_root}/lib/libgcrypt.a" "${install_root}/lib/libgpg-error.a" )

if [[ "$MODE" == "klee" ]]; then
    # KLEE bitcode builds
    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DKLEE_CF klee_main.c "${libs[@]}" -o klee_var_pub_modexp
    extract-bc klee_var_pub_modexp

    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DKLEE_CF -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_modexp
    extract-bc klee_fix_pub_modexp

    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DKLEE_CF klee_main.c powm_sliced.c "${libs[@]}" -o klee_var_pub_modexp_sliced
    extract-bc klee_var_pub_modexp_sliced

    wllvm "${flags[@]}" "${klee_flags[@]}" "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DKLEE_CF -DCONCRETE_PUBS klee_main.c powm_sliced.c "${libs[@]}" -o klee_fix_pub_modexp_sliced
    extract-bc klee_fix_pub_modexp_sliced

    # Replay builds
    clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY klee_main.c "${libs[@]}" -o klee_var_pub_replay_modexp
    clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o klee_fix_pub_replay_modexp

    # clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DREPLAY klee_main.c powm_sliced.c "${libs[@]}" -o klee_var_pub_replay_modexp_sliced
    # clang "${flags[@]}" -static "${NOIND_EXE_FLAGS[@]}" -DUSE_SLICED -DREPLAY -DCONCRETE_PUBS klee_main.c powm_sliced.c "${libs[@]}" -o klee_fix_pub_replay_modexp_sliced
fi

if [[ "$MODE" == "binsec" ]]; then
    # BINSEC builds
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DBINSEC klee_main.c "${libs[@]}" -o binsec_var_pub_modexp
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DBINSEC -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub_modexp

    # Replay binaries for BINSEC (built separately; REPLAY and BINSEC are mutually exclusive)
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY klee_main.c "${libs[@]}" -o binsec_var_pub_replay_modexp
    clang "${flags[@]}" -m32 -static "${NOIND_EXE_FLAGS[@]}" -DREPLAY -DCONCRETE_PUBS klee_main.c "${libs[@]}" -o binsec_fix_pub_replay_modexp

    # clang "${flags[@]}" -static -DUSE_SLICED -DBINSEC klee_main.c powm_sliced.c "${libs[@]}" -o binsec_var_pub_modexp_sliced
    # clang "${flags[@]}" -static -DUSE_SLICED -DBINSEC -DCONCRETE_PUBS klee_main.c powm_sliced.c "${libs[@]}" -o binsec_fix_pub_modexp_sliced
fi

if [[ "$MODE" == "abacus" ]]; then
    # Abacus builds
    gcc "${flags[@]}" -m32 "${NOIND_EXE_FLAGS[@]}" -DABACUS klee_main.c "${libs[@]}" -o abacus_fix_pub_modexp
    # clang "${flags[@]}" -m32 -DUSE_SLICED -DABACUS klee_main.c powm_sliced.c "${libs[@]}" -o abacus_fix_pub_modexp_sliced
fi

