#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

source "$repo_root/scripts/shared/klee_tool_env.sh"
load_klee_tool_layout "$repo_root"

export LLVM_COMPILER=clang

flags=( -g -O0 -I"$repo_root/include" -Iinclude )
noind_exe_flags=( -fno-pie -fno-plt -Wl,-no-pie )
klee_flags=(\
    -I"$KLEE_TOOL_INCLUDE_DIR" \
    -L"$KLEE_TOOL_RUNTIME_LIB_DIR" -Wl,-rpath="$KLEE_TOOL_RUNTIME_LIB_DIR" \
    -lkleeRuntest \
)
libs=( build/library/libmbedtls.a build/library/libmbedx509.a build/library/libmbedcrypto.a )

wllvm "${flags[@]}" "${klee_flags[@]}" "${noind_exe_flags[@]}" test_mod.c "${libs[@]}" -o test_mod
extract-bc test_mod
