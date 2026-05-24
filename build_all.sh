#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/environment-build.yml}"
ENV_NAME="${ENV_NAME:-klee-deps-build}"
BUILD_ROOT="${BUILD_ROOT:-$ROOT_DIR/build}"
DEPS_ROOT="${DEPS_ROOT:-$BUILD_ROOT/deps}"
OPAM_ROOT="${OPAM_ROOT:-$BUILD_ROOT/opam-root}"
BINSEC_ROOT="${BINSEC_ROOT:-$DEPS_ROOT/src/binsec}"
JOBS="${JOBS:-$(nproc)}"
CMAKE_GENERATOR="${CMAKE_GENERATOR:-Ninja}"
CMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Release}"
STP_VERSION="${STP_VERSION:-2.3.3}"
STP_REPO_URL="${STP_REPO_URL:-https://github.com/stp/stp.git}"
KLEE_UCLIBC_REPO_URL="${KLEE_UCLIBC_REPO_URL:-https://github.com/klee/klee-uclibc.git}"
BINSEC_REPO_URL="${BINSEC_REPO_URL:-https://github.com/binsec/binsec.git}"
BINSEC_OCAML_COMPILER="${BINSEC_OCAML_COMPILER:-4.14.2}"
ENABLE_TCMALLOC="${ENABLE_TCMALLOC:-OFF}"

MODE="all"
declare -a REQUESTED_PROJECTS=()

log() {
    printf '[build_all] %s\n' "$*" >&2
}

die() {
    printf '[build_all] %s\n' "$*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage: ./build_all.sh [all|env|deps|binsec|klee|extras] [options]

Modes:
  all     Create or update the conda env, initialize submodules, build STP and
      klee-uclibc, build BINSEC in a local opam switch, then build all KLEE
      submodules plus branch-recorder and loop-limiter.
  env     Create or update the conda environment only.
  deps    Create or update the conda environment, initialize submodules, and
      build STP, klee-uclibc, and BINSEC.
  binsec  Create or update the conda environment and build BINSEC only.
  klee    Create or update the conda environment, initialize submodules, build
          STP plus klee-uclibc, then build selected KLEE submodules.
  extras  Create or update the conda environment and build branch-recorder plus
          loop-limiter.

Options:
  --project <name>   Build only the named KLEE project. Repeatable.
  --help             Show this help text.

Environment overrides:
  ENV_NAME, ENV_FILE, BUILD_ROOT, DEPS_ROOT, JOBS, CMAKE_GENERATOR,
  CMAKE_BUILD_TYPE, STP_VERSION, STP_REPO_URL, KLEE_UCLIBC_REPO_URL,
    BINSEC_REPO_URL, BINSEC_ROOT, BINSEC_OCAML_COMPILER, OPAM_ROOT,
    ENABLE_TCMALLOC, LLVM_DIR, LLVMCC, LLVMCXX, KLEE_CMAKE_EXTRA_ARGS.
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            all|env|deps|binsec|klee|extras)
                MODE="$1"
                ;;
            --project)
                [[ $# -ge 2 ]] || die "--project requires a value"
                REQUESTED_PROJECTS+=("$2")
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                die "Unknown argument: $1"
                ;;
        esac
        shift
    done
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

resolve_tool() {
    local candidate
    for candidate in "$@"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

contains_requested_project() {
    local project_name="$1"
    local requested

    if [[ ${#REQUESTED_PROJECTS[@]} -eq 0 ]]; then
        return 0
    fi

    for requested in "${REQUESTED_PROJECTS[@]}"; do
        if [[ "$requested" == "$project_name" ]]; then
            return 0
        fi
    done

    return 1
}

ensure_conda_environment() {
    require_command conda
    [[ -f "$ENV_FILE" ]] || die "Conda environment file not found: $ENV_FILE"

    # shellcheck disable=SC1091
    eval "$(conda shell.bash hook)"

    if conda env list | awk '{gsub(/\*/, "", $1); print $1}' | grep -qx "$ENV_NAME"; then
        log "Updating conda environment $ENV_NAME from $ENV_FILE"
        conda env update --prune --file "$ENV_FILE" --name "$ENV_NAME"
    else
        log "Creating conda environment $ENV_NAME from $ENV_FILE"
        conda env create --file "$ENV_FILE" --name "$ENV_NAME"
    fi

    conda activate "$ENV_NAME"
    export CONDA_ENV_NAME="$ENV_NAME"
    log "Activated conda environment $ENV_NAME"
}

ensure_opam_root() {
    require_command opam
    mkdir -p "$OPAM_ROOT"

    if [[ ! -f "$OPAM_ROOT/config" ]]; then
        log "Initializing opam root at $OPAM_ROOT"
        opam init --root "$OPAM_ROOT" --disable-sandboxing --bare --yes
    fi
}

ensure_submodules() {
    require_command git
    log "Initializing git submodules"
    git -C "$ROOT_DIR" submodule update --init --recursive
}

configure_toolchain() {
    require_command cmake
    require_command make

    local conda_include_dir="${CONDA_PREFIX:-}/include"
    local conda_lib_dir="${CONDA_PREFIX:-}/lib"
    local pkg_config_entries=()

    LLVM_CONFIG_BIN="${LLVM_CONFIG_BIN:-$(resolve_tool llvm-config-16 llvm-config || true)}"
    CLANG_BIN="${LLVMCC:-$(resolve_tool clang-16 clang || true)}"
    CLANGXX_BIN="${LLVMCXX:-$(resolve_tool clang++-16 clang++ || true)}"

    [[ -n "$LLVM_CONFIG_BIN" ]] || die "Could not find llvm-config inside the active conda environment"
    [[ -n "$CLANG_BIN" ]] || die "Could not find clang inside the active conda environment"
    [[ -n "$CLANGXX_BIN" ]] || die "Could not find clang++ inside the active conda environment"

    LLVM_DIR="${LLVM_DIR:-$($LLVM_CONFIG_BIN --cmakedir)}"
    CMAKE_PREFIX_PATH_VALUE="${CMAKE_PREFIX_PATH:-$CONDA_PREFIX}"

    export LLVM_CONFIG_BIN
    export CLANG_BIN
    export CLANGXX_BIN
    export LLVM_DIR
    export CMAKE_PREFIX_PATH_VALUE

    if [[ -n "${CONDA_PREFIX:-}" && -d "$conda_include_dir" ]]; then
        export CPPFLAGS="-I$conda_include_dir ${CPPFLAGS:-}"
        export CFLAGS="-I$conda_include_dir ${CFLAGS:-}"
        export CXXFLAGS="-I$conda_include_dir ${CXXFLAGS:-}"
    fi

    if [[ -n "${CONDA_PREFIX:-}" && -d "$conda_lib_dir" ]]; then
        export LDFLAGS="-L$conda_lib_dir ${LDFLAGS:-}"
        export LIBRARY_PATH="$conda_lib_dir${LIBRARY_PATH:+:$LIBRARY_PATH}"

        if [[ -d "$conda_lib_dir/pkgconfig" ]]; then
            pkg_config_entries+=("$conda_lib_dir/pkgconfig")
        fi
    fi

    if [[ -n "${CONDA_PREFIX:-}" && -d "$CONDA_PREFIX/share/pkgconfig" ]]; then
        pkg_config_entries+=("$CONDA_PREFIX/share/pkgconfig")
    fi

    if [[ ${#pkg_config_entries[@]} -gt 0 ]]; then
        export PKG_CONFIG_PATH="$(IFS=:; printf '%s' "${pkg_config_entries[*]}")${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    fi

    log "Using LLVM_DIR=$LLVM_DIR"
    log "Using clang=$CLANG_BIN"
    log "Using clang++=$CLANGXX_BIN"
}

clone_or_update_repo() {
    local repo_url="$1"
    local target_dir="$2"
    local ref="${3:-}"

    mkdir -p "$(dirname "$target_dir")"

    if [[ -d "$target_dir/.git" ]]; then
        log "Fetching updates for $(basename "$target_dir")"
        git -C "$target_dir" fetch --tags origin
    else
        log "Cloning $repo_url into $target_dir"
        git clone "$repo_url" "$target_dir"
    fi

    if [[ -n "$ref" ]]; then
        git -C "$target_dir" checkout "$ref"
    fi
}

install_binsec_wrapper() {
    local tool_name="$1"
    local source_path="$2"
    local target_path="$CONDA_PREFIX/bin/$tool_name"
    local opam_bin

    [[ -n "${CONDA_PREFIX:-}" ]] || die "CONDA_PREFIX is not set; cannot install BINSEC wrappers into the active environment"
    opam_bin="$(command -v opam)"
    [[ -n "$opam_bin" ]] || die "Could not resolve opam after activating the conda environment"
    [[ -x "$source_path" ]] || die "Expected executable not found: $source_path"

    cat > "$target_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
eval "\$($opam_bin env --root \"$OPAM_ROOT\" --set-switch --switch \"$BINSEC_ROOT\" --shell=bash)"
exec "$source_path" "\$@"
EOF
    chmod +x "$target_path"
}

build_binsec() {
    local switch_bin_dir

    ensure_opam_root
    clone_or_update_repo "$BINSEC_REPO_URL" "$BINSEC_ROOT"

    if [[ ! -d "$BINSEC_ROOT/_opam" ]]; then
        log "Creating BINSEC local opam switch in $BINSEC_ROOT"
        (
            cd "$BINSEC_ROOT"
            OPAMROOT="$OPAM_ROOT" OCAML_COMPILER="$BINSEC_OCAML_COMPILER" make switch
        )
    fi

    log "Installing required BINSEC opam packages"
    opam exec --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" -- \
        opam install --yes dune dune-site menhir grain_dypgen ocamlgraph zarith toml

    log "Building BINSEC"
    opam exec --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" -- make
    log "Installing BINSEC into the local opam switch"
    opam exec --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" -- make install

    switch_bin_dir="$BINSEC_ROOT/_opam/bin"
    install_binsec_wrapper binsec "$switch_bin_dir/binsec"
    install_binsec_wrapper dune "$switch_bin_dir/dune"

    log "BINSEC is available via $CONDA_PREFIX/bin/binsec"
    log "Dune is available via $CONDA_PREFIX/bin/dune"
}

build_stp() {
    local minisat_install
    local stp_src="$DEPS_ROOT/src/stp"
    local stp_build="$DEPS_ROOT/build/stp"
    local stp_install="$DEPS_ROOT/install/stp-$STP_VERSION"

    minisat_install="$(build_minisat)"

    clone_or_update_repo "$STP_REPO_URL" "$stp_src" "tags/$STP_VERSION"

    log "Configuring STP"
    cmake -S "$stp_src" -B "$stp_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$stp_install" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN" \
        -DCMAKE_PREFIX_PATH="$minisat_install;$CMAKE_PREFIX_PATH_VALUE"

    log "Building STP"
    cmake --build "$stp_build" --parallel "$JOBS"
    log "Installing STP"
    cmake --install "$stp_build"

    STP_DIR="$(find "$stp_install" -path '*/STPConfig.cmake' -print -quit | xargs -r dirname)"
    [[ -n "${STP_DIR:-}" ]] || die "Failed to locate STPConfig.cmake under $stp_install"
    export STP_DIR

    log "Using STP_DIR=$STP_DIR"
}

build_minisat() {
    local minisat_src="$DEPS_ROOT/src/minisat"
    local minisat_build="$DEPS_ROOT/build/minisat"
    local minisat_install="$DEPS_ROOT/install/minisat"

    clone_or_update_repo https://github.com/stp/minisat.git "$minisat_src"

    log "Configuring Minisat"
    cmake -S "$minisat_src" -B "$minisat_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$minisat_install" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN"

    log "Building Minisat"
    cmake --build "$minisat_build" --parallel "$JOBS"
    log "Installing Minisat"
    cmake --install "$minisat_build"

    printf '%s\n' "$minisat_install"
}

build_klee_uclibc() {
    local klee_uclibc_src="$DEPS_ROOT/src/klee-uclibc"

    clone_or_update_repo "$KLEE_UCLIBC_REPO_URL" "$klee_uclibc_src"

    if [[ ! -f "$klee_uclibc_src/config.mk" ]]; then
        log "Configuring klee-uclibc"
        (
            cd "$klee_uclibc_src"
            ./configure --make-llvm-lib \
                --with-cc="$CLANG_BIN" \
                --with-llvm-config="$LLVM_CONFIG_BIN"
        )
    fi

    log "Building klee-uclibc"
    make -C "$klee_uclibc_src" -j"$JOBS"

    KLEE_UCLIBC_PATH_RESOLVED="$klee_uclibc_src"
    export KLEE_UCLIBC_PATH_RESOLVED
}

configure_klee_project() {
    local project_name="$1"
    local project_src="$ROOT_DIR/$project_name"
    local project_build="$BUILD_ROOT/$project_name"
    local extra_args=()

    [[ -f "$project_src/CMakeLists.txt" ]] || die "Missing CMakeLists.txt in $project_src. Did submodule initialization fail?"

    if [[ -n "${KLEE_CMAKE_EXTRA_ARGS:-}" ]]; then
        # shellcheck disable=SC2206
        extra_args=( ${KLEE_CMAKE_EXTRA_ARGS} )
    fi

    log "Configuring $project_name"
    cmake -S "$project_src" -B "$project_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN" \
        -DLLVM_DIR="$LLVM_DIR" \
        -DLLVMCC="$CLANG_BIN" \
        -DLLVMCXX="$CLANGXX_BIN" \
        -DENABLE_SOLVER_STP=ON \
        -DSTP_DIR="$STP_DIR" \
        -DENABLE_POSIX_RUNTIME=ON \
        -DKLEE_UCLIBC_PATH="$KLEE_UCLIBC_PATH_RESOLVED" \
        -DENABLE_UNIT_TESTS=OFF \
        -DENABLE_SYSTEM_TESTS=OFF \
        -DENABLE_TCMALLOC="$ENABLE_TCMALLOC" \
        -DCMAKE_PREFIX_PATH="$STP_DIR;$CMAKE_PREFIX_PATH_VALUE" \
        "${extra_args[@]}"

    log "Building $project_name"
    cmake --build "$project_build" --parallel "$JOBS"
}

build_klee_projects() {
    local project_dir
    local project_name
    local built_any=0

    while IFS= read -r project_dir; do
        project_name="$(basename "$project_dir")"
        if contains_requested_project "$project_name"; then
            configure_klee_project "$project_name"
            built_any=1
        fi
    done < <(find "$ROOT_DIR" -mindepth 1 -maxdepth 1 -type d -name 'klee-*' | sort)

    [[ "$built_any" -eq 1 ]] || die "No matching KLEE projects found to build"
}

build_llvm_plugin_project() {
    local project_name="$1"
    local project_src="$ROOT_DIR/$project_name"
    local project_build="$BUILD_ROOT/$project_name"

    [[ -f "$project_src/CMakeLists.txt" ]] || die "Missing CMakeLists.txt in $project_src"

    log "Configuring $project_name"
    cmake -S "$project_src" -B "$project_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN" \
        -DLLVM_DIR="$LLVM_DIR" \
        -DCMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH_VALUE"

    log "Building $project_name"
    cmake --build "$project_build" --parallel "$JOBS"
}

main() {
    local build_env=0
    local build_deps=0
    local build_binsec_target=0
    local build_klee_targets=0
    local build_extra_targets=0

    parse_args "$@"

    case "$MODE" in
        all)
            build_env=1
            build_deps=1
            build_binsec_target=1
            build_klee_targets=1
            build_extra_targets=1
            ;;
        env)
            build_env=1
            ;;
        deps)
            build_env=1
            build_deps=1
            ;;
        binsec)
            build_env=1
            build_binsec_target=1
            ;;
        klee)
            build_env=1
            build_deps=1
            build_klee_targets=1
            ;;
        extras)
            build_env=1
            build_extra_targets=1
            ;;
        *)
            die "Unsupported mode: $MODE"
            ;;
    esac

    mkdir -p "$BUILD_ROOT" "$DEPS_ROOT"

    if [[ "$build_env" -eq 1 ]]; then
        ensure_conda_environment
        configure_toolchain
    fi

    if [[ "$build_deps" -eq 1 || "$build_klee_targets" -eq 1 ]]; then
        ensure_submodules
    fi

    if [[ "$build_deps" -eq 1 ]]; then
        build_stp
        build_klee_uclibc
    fi

    if [[ "$build_binsec_target" -eq 1 ]]; then
        build_binsec
    fi

    if [[ "$build_klee_targets" -eq 1 ]]; then
        if [[ -z "${STP_DIR:-}" ]]; then
            build_stp
        fi
        if [[ -z "${KLEE_UCLIBC_PATH_RESOLVED:-}" ]]; then
            build_klee_uclibc
        fi
        build_klee_projects
    fi

    if [[ "$build_extra_targets" -eq 1 ]]; then
        build_llvm_plugin_project branch-recorder
        build_llvm_plugin_project loop-limiter
    fi

    log "Build flow completed"
}

main "$@"