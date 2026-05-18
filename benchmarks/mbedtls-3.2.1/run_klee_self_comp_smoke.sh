#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
klee_bin="$repo_root/klee-self-comp/build/bin/klee"

case_name="${1:-fix_pub}"
shift || true

case "$case_name" in
    fix_pub)
        bitcode="$script_dir/klee_fix_pub.bc"
        ;;
    var_pub)
        bitcode="$script_dir/klee_var_pub.bc"
        ;;
    *)
        echo "Usage: $0 [fix_pub|var_pub] [extra klee args...]" >&2
        exit 1
        ;;
esac

if [[ ! -x "$klee_bin" ]]; then
    echo "Missing KLEE binary: $klee_bin" >&2
    exit 1
fi

if [[ ! -f "$bitcode" ]]; then
    echo "Missing benchmark bitcode: $bitcode" >&2
    exit 1
fi

run_stamp="$(date +%Y%m%d-%H%M%S)"
output_dir="$repo_root/results/klee_self_comp_smoke/mbedtls_${case_name}_${run_stamp}"
mkdir -p "$(dirname "$output_dir")"

echo "Running klee-self-comp smoke test"
echo "  bitcode: $bitcode"
echo "  output:  $output_dir"

ulimit -v 70000000

cd "$script_dir"

timeout \
    --foreground \
    --signal=INT \
    --kill-after=30s \
    300s \
    "$klee_bin" \
    --output-dir="$output_dir" \
    --libc=uclibc \
    --posix-runtime \
    --external-calls=all \
    --kdalloc \
    --kdalloc-constants-size=5 \
    --kdalloc-globals-size=5 \
    --kdalloc-heap-size=20 \
    --kdalloc-stack-size=10 \
    --dump-states-on-halt=false \
    --use-batching-search=false \
    --search=dfs \
    --max-solver-time=30s \
    --max-memory=10000 \
    --emit-all-errors=true \
    "$bitcode" \
    "$@"