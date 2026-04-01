#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bin_path=$(realpath ../klee-controlflow/build/bin)
script_path=$(realpath .)
export PATH="$bin_path:$script_path:$PATH"

# set virtual memory limit to 70GB to prevent excessive memory usage
ulimit -v 70000000

max_time="10m"
max_solver_time="30s"
kill_after="30s"
max_memory=10000
search_strategies="random-path,nurs:covnew"
concretize_on_solver_timeout="true"

klee_timeout() {
    local search_args=()
    IFS=',' read -ra ADDR <<< "$search_strategies"
    for i in "${ADDR[@]}"; do
        search_args+=( "--search=$i" )
    done

    timeout --foreground --signal=INT --kill-after="$kill_after" $max_time \
    klee --libc=uclibc \
        --posix-runtime \
        --external-calls=all \
        --kdalloc \
        --kdalloc-constants-size=5 \
        --kdalloc-globals-size=5 \
        --kdalloc-heap-size=20 \
        --kdalloc-stack-size=10 \
        --dump-states-on-halt=false \
        --use-batching-search=false \
        "${search_args[@]}" \
        --concretize-on-solver-timeout="$concretize_on_solver_timeout" \
        --max-solver-time="$max_solver_time" \
        --max-memory=$max_memory "$1" || true
}

mbedtls-3.2.1/build_test_mod.sh
klee_timeout mbedtls-3.2.1/test_mod.bc
