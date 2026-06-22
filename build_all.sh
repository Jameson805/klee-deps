#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/environment-build.yml}"
ENV_NAME="${ENV_NAME:-klee-deps-build}"
BUILD_ROOT="${BUILD_ROOT:-$ROOT_DIR/build}"
DEPS_ROOT="${DEPS_ROOT:-$BUILD_ROOT/deps}"
OPAM_ROOT="$BUILD_ROOT/opam-root"
BINSEC_ROOT="$DEPS_ROOT/src/binsec"
BUILD_MANIFEST="$BUILD_ROOT/tool-paths.json"
JOBS="${JOBS:-$(nproc)}"
CMAKE_GENERATOR="${CMAKE_GENERATOR:-Ninja}"
CMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Release}"
STP_VERSION="${STP_VERSION:-2.3.3}"
STP_REPO_URL="${STP_REPO_URL:-https://github.com/stp/stp.git}"
KLEE_UCLIBC_REPO_URL="${KLEE_UCLIBC_REPO_URL:-https://github.com/klee/klee-uclibc.git}"
BINSEC_REPO_URL="${BINSEC_REPO_URL:-https://github.com/binsec/binsec.git}"
BINSEC_OCAML_COMPILER="${BINSEC_OCAML_COMPILER:-4.14.2}"
ENABLE_TCMALLOC="${ENABLE_TCMALLOC:-OFF}"
PIN_ARCHIVE_URL="${PIN_ARCHIVE_URL:-https://software.intel.com/sites/landingpage/pintool/downloads/pin-external-4.2-99776-g21d818fa2-gcc-linux.tar.gz}"
PIN_INSTALL_ROOT="${PIN_INSTALL_ROOT:-$DEPS_ROOT/pin}"
MINISAT_INSTALL_DIR=""

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
Usage: ./build_all.sh [all|env|deps|pin|binsec|klee|extras] [options]

Modes:
  all     Create or update the conda env, initialize submodules, build STP and
      klee-uclibc, install Intel Pin, then build all KLEE submodules plus
      loop-limiter. If `opam` is available, BINSEC is also built.
  env     Create or update the conda environment only.
  deps    Create or update the conda environment, initialize submodules, and
      build STP, klee-uclibc, and Intel Pin.
  pin     Create or update the conda environment and install Intel Pin only.
  binsec  Create or update the conda environment and build BINSEC only.
  klee    Create or update the conda environment, initialize submodules, build
          STP plus klee-uclibc, install Intel Pin, then build selected KLEE
          submodules.
  extras  Create or update the conda environment and build loop-limiter.

Options:
  --project <name>   Build only the named KLEE project. Repeatable.
  --help             Show this help text.

Environment overrides:
  ENV_NAME, ENV_FILE, BUILD_ROOT, DEPS_ROOT, JOBS, CMAKE_GENERATOR,
  CMAKE_BUILD_TYPE, STP_VERSION, STP_REPO_URL, KLEE_UCLIBC_REPO_URL,
    BINSEC_REPO_URL, BINSEC_OCAML_COMPILER, ENABLE_TCMALLOC,
    PIN_ARCHIVE_URL, PIN_INSTALL_ROOT, LLVM_DIR, LLVMCC, LLVMCXX,
    KLEE_CMAKE_EXTRA_ARGS, BUILD_MANIFEST.

Workspace-local paths:
    OPAM_ROOT is set to BUILD_ROOT/opam-root inside this script
    BINSEC_ROOT is set to DEPS_ROOT/src/binsec inside this script
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            all|env|deps|pin|binsec|klee|extras)
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
        if [[ "$candidate" == */* && -x "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi

        if [[ "$candidate" != */* ]] && command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

ensure_build_manifest() {
    # Keep tool discovery explicit and workspace-local instead of inferring it
    # from whichever build directories happen to exist in this checkout.
    mkdir -p "$(dirname "$BUILD_MANIFEST")"

    if [[ ! -f "$BUILD_MANIFEST" ]]; then
        cat > "$BUILD_MANIFEST" <<'EOF'
{
  "artifacts": {},
  "tools": {}
}
EOF
    fi
}

register_artifact() {
    local artifact_id="$1"
    local artifact_path="$2"
    local artifact_kind="$3"

    [[ -n "$artifact_id" ]] || die "register_artifact requires an artifact id"
    [[ -e "$artifact_path" ]] || die "Expected artifact not found: $artifact_path"

    ensure_build_manifest
    python - "$BUILD_MANIFEST" "$artifact_id" "$artifact_path" "$artifact_kind" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
artifact_id = sys.argv[2]
artifact_path = str(Path(sys.argv[3]).resolve())
artifact_kind = sys.argv[4]

with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

artifacts = data.setdefault("artifacts", {})
artifacts[artifact_id] = {"path": artifact_path, "kind": artifact_kind}

with manifest_path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

register_klee_tool_record() {
    local tool_id="$1"
    local binary_path="$2"
    local include_dir="$3"
    local runtime_lib_dir="$4"

    [[ -n "$tool_id" ]] || die "register_klee_tool_record requires a tool id"
    [[ -x "$binary_path" ]] || die "Expected KLEE binary not found: $binary_path"
    [[ -d "$include_dir" ]] || die "Expected KLEE include directory not found: $include_dir"
    [[ -d "$runtime_lib_dir" ]] || die "Expected KLEE runtime lib directory not found: $runtime_lib_dir"

    ensure_build_manifest
    python - "$BUILD_MANIFEST" "$tool_id" "$binary_path" "$include_dir" "$runtime_lib_dir" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
tool_id = sys.argv[2]
binary_path = str(Path(sys.argv[3]).resolve())
include_dir = str(Path(sys.argv[4]).resolve())
runtime_lib_dir = str(Path(sys.argv[5]).resolve())

with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

tools = data.setdefault("tools", {})
tools[tool_id] = {
    "kind": "klee-tool",
    "binary": binary_path,
    "include_dir": include_dir,
    "runtime_lib_dir": runtime_lib_dir,
}

with manifest_path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

register_executable_artifact() {
    local artifact_id="$1"
    local executable_path="$2"

    [[ -x "$executable_path" ]] || die "Expected executable not found: $executable_path"
    register_artifact "$artifact_id" "$executable_path" executable
}

prune_missing_artifacts() {
    # The manifest is reused across incremental builds, so drop entries whose
    # binaries or layouts disappeared before activation consumes stale paths.
    ensure_build_manifest
    python - "$BUILD_MANIFEST" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

artifacts = data.get("artifacts", {})
data["artifacts"] = {
    key: value
    for key, value in artifacts.items()
    if isinstance(value, dict) and Path(value.get("path", "")).exists()
}

tools = data.get("tools", {})
data["tools"] = {
    key: value
    for key, value in tools.items()
    if isinstance(value, dict)
    and Path(value.get("binary", "")).exists()
    and Path(value.get("include_dir", "")).is_dir()
    and Path(value.get("runtime_lib_dir", "")).is_dir()
}

with manifest_path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

unregister_artifact() {
    local artifact_id="$1"

    ensure_build_manifest
    python - "$BUILD_MANIFEST" "$artifact_id" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
artifact_id = sys.argv[2]

with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

artifacts = data.get("artifacts", {})
artifacts.pop(artifact_id, None)

with manifest_path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
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
        env -u OPAMSWITCH -u OPAMROOT -u OPAMNOENVNOTICE \
            opam init --root "$OPAM_ROOT" --disable-sandboxing --bare --yes
    fi
}

ensure_submodules() {
    require_command git
    log "Initializing git submodules"
    git -C "$ROOT_DIR" submodule sync --recursive
    git -C "$ROOT_DIR" submodule update --init --recursive
}

configure_toolchain() {
    require_command cmake
    require_command make

    local conda_include_dir="${CONDA_PREFIX:-}/include"
    local conda_lib_dir="${CONDA_PREFIX:-}/lib"
    local conda_gcc_root="${CONDA_PREFIX:-}/lib/gcc/x86_64-conda-linux-gnu"
    local conda_gcc_version_dir=""
    local conda_cxx_include_dir=""
    local pkg_config_entries=()

    LLVM_CONFIG_BIN="${LLVM_CONFIG_BIN:-$(resolve_tool "${CONDA_PREFIX:-}/bin/llvm-config" llvm-config-16 llvm-config || true)}"
    CLANG_BIN="${LLVMCC:-$(resolve_tool "${CONDA_PREFIX:-}/bin/clang-16" "${CONDA_PREFIX:-}/bin/clang" clang-16 clang || true)}"
    CLANGXX_BIN="${LLVMCXX:-$(resolve_tool "${CONDA_PREFIX:-}/bin/clang++-16" "${CONDA_PREFIX:-}/bin/clang++" clang++-16 clang++ || true)}"

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

    if [[ -n "${CONDA_PREFIX:-}" && -d "$conda_gcc_root" ]]; then
        conda_gcc_version_dir="$(find "$conda_gcc_root" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n 1)"
        conda_cxx_include_dir="$conda_gcc_version_dir/include/c++"

        if [[ -d "$conda_cxx_include_dir" ]]; then
            export CXXFLAGS="-Wno-invalid-constexpr -I$conda_cxx_include_dir -I$conda_cxx_include_dir/x86_64-conda-linux-gnu ${CXXFLAGS:-}"
        fi

        if [[ -d "$conda_gcc_version_dir" ]]; then
            export LDFLAGS="-L$conda_gcc_version_dir ${LDFLAGS:-}"
            export LIBRARY_PATH="$conda_gcc_version_dir${LIBRARY_PATH:+:$LIBRARY_PATH}"
        fi
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

ensure_klee_host_cxx_wrapper() {
    local wrapper_dir="$BUILD_ROOT/tool-wrappers"
    local wrapper_path="$wrapper_dir/klee-clangxx"

    mkdir -p "$wrapper_dir"

    # KLEE's host-side C++ build still appends -fno-exceptions, but newer
    # conda-provided libstdc++ headers used by LLVM 16 instantiate throw-based
    # helpers during ordinary host compilation. That breaks on some machines
    # with errors like bits/nested_exception.h: cannot use 'throw' with
    # exceptions disabled. Keep the workaround here in the integration layer so
    # we can adapt to the active toolchain without patching the KLEE trees.
    cat > "$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

real_cxx=$(printf '%q' "$CLANGXX_BIN")
args=()

for arg in "\$@"; do
    if [[ "\$arg" == "-fno-exceptions" ]]; then
        continue
    fi
    args+=("\$arg")
done

# Re-enable exceptions for KLEE's host compilation only. LLVMCXX still points
# at the real clang++ binary, so this wrapper does not change bitcode runtime
# builds that intentionally rely on KLEE's upstream flags.
for arg in "\$@"; do
    :
done

args+=("-fexceptions")

exec "\$real_cxx" "\${args[@]}"
EOF

    chmod +x "$wrapper_path"
    KLEE_HOST_CXX_WRAPPER="$wrapper_path"
    export KLEE_HOST_CXX_WRAPPER
}

reset_cmake_build_if_toolchain_changed() {
    local build_dir="$1"
    local cache_file="$build_dir/CMakeCache.txt"

    [[ -f "$cache_file" ]] || return 0

    if ! grep -qxF "CMAKE_C_COMPILER:FILEPATH=$CLANG_BIN" "$cache_file" || \
       ! grep -qxF "CMAKE_CXX_COMPILER:FILEPATH=$CLANGXX_BIN" "$cache_file"; then
        log "Removing stale CMake build directory $build_dir because the compiler changed"
        rm -rf "$build_dir"
        return 0
    fi

    if [[ " ${CXXFLAGS:-} " == *" -Wno-invalid-constexpr "* ]] && \
       ! grep -q -- "-Wno-invalid-constexpr" "$cache_file"; then
        log "Removing stale CMake build directory $build_dir because the C++ flags changed"
        rm -rf "$build_dir"
    fi
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

build_binsec() {
    local switch_bin_dir
    local binsec_cc="$CLANG_BIN ${CXXFLAGS:-}"
    local binsec_compiler_env=(
        "CC=$binsec_cc"
        "CXX=$CLANGXX_BIN"
    )
    local binsec_native_link_env=(
        "OCAMLPARAM=_,cclib=-lstdc++"
    )
    local binsec_unisim_env=(
        "CFLAGS=${CXXFLAGS:-} ${CFLAGS:-}"
    )
    local current_switch_cc=""

    ensure_opam_root
    clone_or_update_repo "$BINSEC_REPO_URL" "$BINSEC_ROOT"

    if [[ -d "$BINSEC_ROOT/_opam" ]]; then
        current_switch_cc="$(env -u OPAMSWITCH -u OPAMROOT -u OPAMNOENVNOTICE \
            opam exec --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" -- \
            ocamlc -config | awk -F': ' '/^c_compiler:/ {print $2; exit}')"

        # The local switch bakes its C toolchain into ocamlc -config, and dune
        # uses that command for C++ foreign stubs in unisim_archisec.
        if [[ -n "$current_switch_cc" && "$current_switch_cc" != "$binsec_cc" ]]; then
            log "Recreating BINSEC local opam switch because ocamlc uses $current_switch_cc"
            rm -rf "$BINSEC_ROOT/_opam"
        fi
    fi

    if [[ ! -d "$BINSEC_ROOT/_opam" ]]; then
        log "Creating BINSEC local opam switch in $BINSEC_ROOT"
        (
            cd "$BINSEC_ROOT"
            env -u OPAMSWITCH -u OPAMNOENVNOTICE \
                "${binsec_compiler_env[@]}" \
                OPAMROOT="$OPAM_ROOT" OCAML_COMPILER="$BINSEC_OCAML_COMPILER" make switch
        )
    fi

    log "Installing required BINSEC opam packages"
    env -u OPAMSWITCH -u OPAMROOT -u OPAMNOENVNOTICE \
        "${binsec_compiler_env[@]}" \
        opam install --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" \
        --yes dune dune-site menhir grain_dypgen ocamlgraph zarith toml z3

    log "Installing unisim_archisec with conda C++ headers available to CC"
    env -u OPAMSWITCH -u OPAMROOT -u OPAMNOENVNOTICE \
        "${binsec_compiler_env[@]}" \
        "${binsec_unisim_env[@]}" \
        opam install --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" \
        --yes unisim_archisec

    log "Building BINSEC"
    (
        cd "$BINSEC_ROOT"
        # Build BINSEC directly with dune instead of the repo Makefile. The
        # Makefile runs the @fmt alias before @install, which turns formatter
        # version skew inside BINSEC's docs tree into a spurious build failure.
        # unisim_archisec installs C++ stubs but does not export the native
        # C++ runtime link flag, so keep BINSEC's final OCaml native link explicit.
        env -u OPAMSWITCH -u OPAMROOT -u OPAMNOENVNOTICE \
            "${binsec_compiler_env[@]}" \
            "${binsec_native_link_env[@]}" \
            opam exec --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" -- dune build @install
    )
    log "Installing BINSEC into the local opam switch"
    (
        cd "$BINSEC_ROOT"
        env -u OPAMSWITCH -u OPAMROOT -u OPAMNOENVNOTICE \
            "${binsec_compiler_env[@]}" \
            "${binsec_native_link_env[@]}" \
            opam exec --root "$OPAM_ROOT" --switch "$BINSEC_ROOT" -- dune install
    )

    switch_bin_dir="$BINSEC_ROOT/_opam/bin"
    register_executable_artifact binsec "$switch_bin_dir/binsec"
    register_executable_artifact dune "$switch_bin_dir/dune"

    log "BINSEC is available via $switch_bin_dir/binsec"
    log "Dune is available via $switch_bin_dir/dune"
}

build_stp() {
    local stp_cxx_flags
    local stp_src="$DEPS_ROOT/src/stp"
    local stp_build="$DEPS_ROOT/build/stp"
    local stp_install="$DEPS_ROOT/install/stp-$STP_VERSION"

    build_minisat
    stp_cxx_flags="${CXXFLAGS:-} ${STP_CXX_FLAGS:--include stdint.h}"

    clone_or_update_repo "$STP_REPO_URL" "$stp_src" "tags/$STP_VERSION"

    reset_cmake_build_if_toolchain_changed "$stp_build"

    log "Configuring STP"
    cmake -S "$stp_src" -B "$stp_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$stp_install" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN" \
        -DCMAKE_CXX_FLAGS="$stp_cxx_flags" \
        -DENABLE_PYTHON_INTERFACE=OFF \
        -DNOCRYPTOMINISAT=ON \
        -DMINISAT_INCLUDE_DIRS="$MINISAT_INSTALL_DIR/include" \
        -DMINISAT_LIBDIR="$MINISAT_INSTALL_DIR/lib" \
        -DCMAKE_PREFIX_PATH="$MINISAT_INSTALL_DIR;$CMAKE_PREFIX_PATH_VALUE"

    log "Building STP"
    cmake --build "$stp_build" --parallel "$JOBS"
    log "Installing STP"
    cmake --install "$stp_build"

    STP_DIR="$(find "$stp_install" -path '*/STPConfig.cmake' -print -quit | xargs -r dirname)"
    [[ -n "${STP_DIR:-}" ]] || die "Failed to locate STPConfig.cmake under $stp_install"
    export STP_DIR

    log "Using STP_DIR=$STP_DIR"
}

build_pin() {
    local archive_path
    local archive_basename
    local extract_root
    local extracted_dir

    require_command curl
    require_command tar

    if [[ -x "$PIN_INSTALL_ROOT/pin" ]]; then
        log "Using existing Intel Pin kit under $PIN_INSTALL_ROOT"
    else
        archive_basename="$(basename "$PIN_ARCHIVE_URL")"
        archive_path="$DEPS_ROOT/downloads/$archive_basename"
        extract_root="$DEPS_ROOT/extract-pin"

        mkdir -p "$DEPS_ROOT/downloads"

        if [[ ! -f "$archive_path" ]]; then
            log "Downloading Intel Pin from $PIN_ARCHIVE_URL"
            curl --fail --location --output "$archive_path" "$PIN_ARCHIVE_URL"
        else
            log "Reusing downloaded Intel Pin archive $archive_path"
        fi

        rm -rf "$extract_root"
        mkdir -p "$extract_root"
        log "Extracting Intel Pin into $PIN_INSTALL_ROOT"
        tar -xzf "$archive_path" -C "$extract_root"

        extracted_dir="$(find "$extract_root" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
        [[ -n "$extracted_dir" ]] || die "Failed to locate extracted Intel Pin directory under $extract_root"
        [[ -x "$extracted_dir/pin" ]] || die "Extracted Intel Pin directory does not contain the pin launcher: $extracted_dir"

        rm -rf "$PIN_INSTALL_ROOT"
        mv "$extracted_dir" "$PIN_INSTALL_ROOT"
        rm -rf "$extract_root"
    fi

    register_artifact intel_pin_root "$PIN_INSTALL_ROOT" directory
    register_executable_artifact pin "$PIN_INSTALL_ROOT/pin"
    if [[ -x "$PIN_INSTALL_ROOT/pin32" ]]; then
        register_executable_artifact pin32 "$PIN_INSTALL_ROOT/pin32"
    fi

    export PIN_ROOT="$PIN_INSTALL_ROOT"
    log "Intel Pin is available via PIN_ROOT=$PIN_ROOT"
}

build_minisat() {
    local minisat_src="$DEPS_ROOT/src/minisat"
    local minisat_build="$DEPS_ROOT/build/minisat"
    local minisat_install="$DEPS_ROOT/install/minisat"
    local zlib_include="$CONDA_PREFIX/include"
    local zlib_library="$CONDA_PREFIX/lib/libz.so"

    clone_or_update_repo https://github.com/stp/minisat.git "$minisat_src"

    reset_cmake_build_if_toolchain_changed "$minisat_build"

    log "Configuring Minisat"
    cmake -S "$minisat_src" -B "$minisat_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_INSTALL_PREFIX="$minisat_install" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN" \
        -DCMAKE_C_FLAGS="${CFLAGS:-}" \
        -DCMAKE_CXX_FLAGS="${CXXFLAGS:-}" \
        -DCMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH_VALUE" \
        -DZLIB_ROOT="$CONDA_PREFIX" \
        -DZLIB_INCLUDE_DIR="$zlib_include" \
        -DZLIB_LIBRARY="$zlib_library"

    log "Building Minisat"
    cmake --build "$minisat_build" --parallel "$JOBS"
    log "Installing Minisat"
    cmake --install "$minisat_build"

    MINISAT_INSTALL_DIR="$minisat_install"
    export MINISAT_INSTALL_DIR
}

build_klee_uclibc() {
    local klee_uclibc_src="$DEPS_ROOT/src/klee-uclibc"
    local conda_cppflags="-I$CONDA_PREFIX/include"
    local conda_ldflags="-L$CONDA_PREFIX/lib -Wl,-rpath,$CONDA_PREFIX/lib"
    local conda_cpath="$CONDA_PREFIX/include"
    local conda_library_path="$CONDA_PREFIX/lib"
    local conda_curses_flags=""
    local conda_curses_libs=""
    local klee_uclibc_make_args=()

    # klee-uclibc builds host-side Kconfig tools separately, and that path does
    # not reliably honor the exported CPPFLAGS/CFLAGS used by the main build.
    if [[ -f "$CONDA_PREFIX/include/ncurses/ncurses.h" ]]; then
        conda_curses_flags='-I'
        conda_curses_flags+="$CONDA_PREFIX/include -DCURSES_LOC=\"<ncurses/ncurses.h>\" -DLOCALE"
    elif [[ -f "$CONDA_PREFIX/include/ncurses/curses.h" ]]; then
        conda_curses_flags='-I'
        conda_curses_flags+="$CONDA_PREFIX/include -DCURSES_LOC=\"<ncurses/curses.h>\" -DLOCALE"
    elif [[ -f "$CONDA_PREFIX/include/ncurses.h" ]]; then
        conda_curses_flags='-I'
        conda_curses_flags+="$CONDA_PREFIX/include -DCURSES_LOC=\"<ncurses.h>\" -DLOCALE"
    elif [[ -f "$CONDA_PREFIX/include/curses.h" ]]; then
        conda_curses_flags='-I'
        conda_curses_flags+="$CONDA_PREFIX/include -DCURSES_LOC=\"<curses.h>\" -DLOCALE"
    fi

    if [[ -f "$CONDA_PREFIX/lib/libncursesw.so" || -f "$CONDA_PREFIX/lib/libncursesw.a" ]]; then
        conda_curses_libs="-L$CONDA_PREFIX/lib -Wl,-rpath,$CONDA_PREFIX/lib -lncursesw"
    elif [[ -f "$CONDA_PREFIX/lib/libncurses.so" || -f "$CONDA_PREFIX/lib/libncurses.a" ]]; then
        conda_curses_libs="-L$CONDA_PREFIX/lib -Wl,-rpath,$CONDA_PREFIX/lib -lncurses"
    elif [[ -f "$CONDA_PREFIX/lib/libcurses.so" || -f "$CONDA_PREFIX/lib/libcurses.a" ]]; then
        conda_curses_libs="-L$CONDA_PREFIX/lib -Wl,-rpath,$CONDA_PREFIX/lib -lcurses"
    fi

    if [[ -n "$conda_curses_flags" ]]; then
        klee_uclibc_make_args+=("HOST_EXTRACFLAGS=$conda_curses_flags")
    fi

    if [[ -n "$conda_curses_libs" ]]; then
        klee_uclibc_make_args+=("HOST_LOADLIBES=$conda_curses_libs")
    fi

    clone_or_update_repo "$KLEE_UCLIBC_REPO_URL" "$klee_uclibc_src"

    if [[ ! -f "$klee_uclibc_src/config.mk" ]]; then
        log "Configuring klee-uclibc"
        (
            cd "$klee_uclibc_src"
            export CPPFLAGS="${CPPFLAGS:-} $conda_cppflags"
            export CFLAGS="${CFLAGS:-} $conda_cppflags"
            export LDFLAGS="${LDFLAGS:-} $conda_ldflags"
            export CPATH="${CPATH:+$CPATH:}$conda_cpath"
            export C_INCLUDE_PATH="${C_INCLUDE_PATH:+$C_INCLUDE_PATH:}$conda_cpath"
            export LIBRARY_PATH="${LIBRARY_PATH:+$LIBRARY_PATH:}$conda_library_path"
            export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$conda_library_path"
            ./configure --make-llvm-lib \
                --with-cc="$CLANG_BIN" \
                --with-llvm-config="$LLVM_CONFIG_BIN"
        )
    fi

    # The premade klee-uclibc config still needs its generated header refreshed
    # before the main build. Feed default answers once here so later `make`
    # does not block on interactive Kconfig prompts.
    set +o pipefail
    yes '' | make -C "$klee_uclibc_src" "${klee_uclibc_make_args[@]}" include/bits/uClibc_config.h
    local header_refresh_status=$?
    set -o pipefail
    if [[ "$header_refresh_status" -ne 0 && "$header_refresh_status" -ne 141 ]]; then
        die "Failed to refresh klee-uclibc generated headers"
    fi

    log "Building klee-uclibc"
    CPPFLAGS="${CPPFLAGS:-} $conda_cppflags" \
    CFLAGS="${CFLAGS:-} $conda_cppflags" \
    LDFLAGS="${LDFLAGS:-} $conda_ldflags" \
    CPATH="${CPATH:+$CPATH:}$conda_cpath" \
    C_INCLUDE_PATH="${C_INCLUDE_PATH:+$C_INCLUDE_PATH:}$conda_cpath" \
    LIBRARY_PATH="${LIBRARY_PATH:+$LIBRARY_PATH:}$conda_library_path" \
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$conda_library_path" \
    make -C "$klee_uclibc_src" "${klee_uclibc_make_args[@]}" -j"$JOBS"

    KLEE_UCLIBC_PATH_RESOLVED="$klee_uclibc_src"
    export KLEE_UCLIBC_PATH_RESOLVED
}

configure_klee_project() {
    local project_name="$1"
    local project_src="$ROOT_DIR/$project_name"
    local project_build="$BUILD_ROOT/$project_name"
    local extra_args=()
    local klee_cxx_flags

    [[ -f "$project_src/CMakeLists.txt" ]] || die "Missing CMakeLists.txt in $project_src. Did submodule initialization fail?"

    ensure_klee_host_cxx_wrapper

    if [[ -n "${KLEE_CMAKE_EXTRA_ARGS:-}" ]]; then
        # shellcheck disable=SC2206
        extra_args=( ${KLEE_CMAKE_EXTRA_ARGS} )
    fi

    reset_cmake_build_if_toolchain_changed "$project_build"

    klee_cxx_flags="${CXXFLAGS:-} ${KLEE_CXX_FLAGS:--include stdint.h}"

    log "Configuring $project_name"
    cmake -S "$project_src" -B "$project_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$KLEE_HOST_CXX_WRAPPER" \
        -DCMAKE_CXX_FLAGS="$klee_cxx_flags" \
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

    register_klee_artifacts "$project_name"
}

cleanup_obsolete_workspace_wrappers() {
    local wrapper_dir="$BUILD_ROOT/bin"

    rm -f \
        "$wrapper_dir/binsec" \
        "$wrapper_dir/dune" \
        "$wrapper_dir/klee-cf" \
        "$wrapper_dir/klee-controlflow" \
        "$wrapper_dir/klee-eager" \
        "$wrapper_dir/klee-self-comp" \
        "$wrapper_dir/ktest-tool" \
        "$wrapper_dir/pin" \
        "$wrapper_dir/pin32"
    rmdir "$wrapper_dir" 2>/dev/null || true
}

register_klee_artifacts() {
    local project_name="$1"
    local target_path="$BUILD_ROOT/$project_name/bin/klee"
    local ktest_tool_path="$BUILD_ROOT/$project_name/bin/ktest-tool"
    local artifact_name=""

    case "$project_name" in
        klee-cf)
            unregister_artifact klee-controlflow
            artifact_name="klee-cf"
            ;;
        klee-eager)
            artifact_name="klee-eager"
            ;;
        klee-self-comp)
            artifact_name="klee-self-comp"
            ;;
    esac

    if [[ -n "$artifact_name" ]]; then
        register_executable_artifact "$artifact_name" "$target_path"
        register_klee_tool_record \
            "$artifact_name" \
            "$target_path" \
            "$ROOT_DIR/$project_name/include" \
            "$BUILD_ROOT/$project_name/lib"
    fi

    if [[ -x "$ktest_tool_path" ]]; then
        register_executable_artifact ktest-tool "$ktest_tool_path"
    fi
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

    reset_cmake_build_if_toolchain_changed "$project_build"

    log "Configuring $project_name"
    cmake -S "$project_src" -B "$project_build" \
        -G "$CMAKE_GENERATOR" \
        -DCMAKE_BUILD_TYPE="$CMAKE_BUILD_TYPE" \
        -DCMAKE_C_COMPILER="$CLANG_BIN" \
        -DCMAKE_CXX_COMPILER="$CLANGXX_BIN" \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
        -DLLVM_DIR="$LLVM_DIR" \
        -DCMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH_VALUE"

    log "Building $project_name"
    cmake --build "$project_build" --parallel "$JOBS"

    case "$project_name" in
        loop-limiter)
            register_artifact loop_limiter_plugin "$project_build/libLoopLimiter.so" shared-library
            ;;
    esac
}

main() {
    local build_env=0
    local build_deps=0
    local build_pin_target=0
    local build_binsec_target=0
    local build_klee_targets=0
    local build_extra_targets=0

    parse_args "$@"

    case "$MODE" in
        all)
            build_env=1
            build_deps=1
            build_pin_target=1
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
            build_pin_target=1
            ;;
        pin)
            build_env=1
            build_pin_target=1
            ;;
        binsec)
            build_env=1
            build_binsec_target=1
            ;;
        klee)
            build_env=1
            build_deps=1
            build_pin_target=1
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
    ensure_build_manifest
    cleanup_obsolete_workspace_wrappers
    prune_missing_artifacts

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

    if [[ "$build_pin_target" -eq 1 ]]; then
        build_pin
    fi

    if [[ "$build_binsec_target" -eq 1 ]]; then
        if command -v opam >/dev/null 2>&1; then
            build_binsec
        elif [[ "$MODE" == "binsec" ]]; then
            die "BINSEC build requires opam, but opam is not available in PATH"
        else
            log "Skipping BINSEC build because opam is not available in PATH"
        fi
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
        build_llvm_plugin_project loop-limiter
    fi

    log "Build flow completed"
}

main "$@"
