#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

klee_root=""
max_time=""
max_solver_time="10s"
kill_after="5m"
sym_size=4
max_memory=8000
max_depth=0
dfs=false

usage() {
    cat <<EOF
Usage: $0 --klee-root <path-to-klee-build> --max-time <duration> [options]

Required:
  --klee-root <path>     Path containing klee binary (e.g. ../klee-controlflow/build/bin)
  --max-time <duration>  Overall timeout for each KLEE run (e.g. 30m, 1h, 600s)

Optional:
  --sym-size <n>         Default: 4
  --max-solver-time <d>  Default: 10s
  --kill-after <d>       Default: 5m
  --max-memory <n>       Default: 8000 (MB KLEE cap)
  --max-depth <n>        Default: 0 (0 means unlimited search depth)
  --dfs                  Default: false (use DFS search when present)
  --results-dir <name>   Default: self_comp_results
  --help                 Show this help
EOF
    exit 1
}

results_dir="self_comp_results"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --klee-root) klee_root="$2"; shift 2;;
        --max-time) max_time="$2"; shift 2;;
        --sym-size) sym_size="$2"; shift 2;;
        --max-solver-time) max_solver_time="$2"; shift 2;;
        --kill-after) kill_after="$2"; shift 2;;
        --max-memory) max_memory="$2"; shift 2;;
        --max-depth) max_depth="$2"; shift 2;;
        --dfs) dfs=true; shift;;
        --results-dir) results_dir="$2"; shift 2;;
        --help|-h) usage;;
        --) shift; break;;
        -*)
            echo "Unknown option: $1"
            usage;;
        *)
            echo "Unexpected positional argument: $1"
            usage;;
    esac
done

# Validate required
if [[ -z "$klee_root" || -z "$max_time" ]]; then
    echo "Error: --klee-root and --max-time are required."
    usage
fi

# Validate numeric
if ! [[ "$sym_size" =~ ^[0-9]+$ ]]; then
    echo "Error: sym_size must be a non-negative integer (got '$sym_size')"; exit 1
fi
if ! [[ "$max_memory" =~ ^[0-9]+$ ]]; then
    echo "Error: max_memory must be a non-negative integer (got '$max_memory')"; exit 1
fi
if ! [[ "$max_depth" =~ ^[0-9]+$ ]]; then
    echo "Error: max_depth must be a non-negative integer (got '$max_depth')"; exit 1
fi

rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

echo "##########"
echo "Args:"
echo "klee_root=$klee_root"
echo "max_time=$max_time"
echo "sym_size=$sym_size"
echo "max_solver_time=$max_solver_time"
echo "kill_after=$kill_after"
echo "max_memory=$max_memory"
echo "max_depth=$max_depth"
echo "dfs=$dfs"
echo "results_dir=$results_dir"
echo "##########"

klee_timeout() {
    local search_flag=()
    if [[ "$dfs" == "true" ]]; then
        search_flag+=( --search=dfs )
    fi

    timeout --foreground --signal=INT --kill-after="$kill_after" "$max_time" \
    "$klee_root/klee" --libc=uclibc \
        --posix-runtime \
        --dump-states-on-halt=false \
        --use-batching-search=true \
        --max-solver-time="$max_solver_time" \
        --max-depth="$max_depth" \
        "${search_flag[@]}" \
        --max-memory=$max_memory "$1" || true
}

run_case() {
    local title="$1"      # descriptive title
    local bc="$2"         # bitcode path
    local result_name="$3"

    local bc_dir=$(dirname "$bc")

    echo "========="
    echo "$title"
    echo "========="

    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir"/klee-out-*
    klee_timeout "$bc"
    mv "$bc_dir/klee-out-0" "$results_dir/$result_name"
    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir"/klee-out-*
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"
    mbedtls-3.2.1/build.sh --self-comp --sym-size "$sym_size"
    run_case "Mbed TLS 3.2.1 (Fix Pub Self-Comp)" "mbedtls-3.2.1/self_comp_fix_pub.bc" "mbedtls_self_comp_fix_pub"
    run_case "Mbed TLS 3.2.1 (Var Pub Self-Comp)" "mbedtls-3.2.1/self_comp_var_pub.bc" "mbedtls_self_comp_var_pub"
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"
    libgcrypt-and-libgpg-error/build.sh --self-comp --sym-size "$sym_size"
    run_case "Libgcrypt 1.10.1 (Fix Pub Self-Comp)" "libgcrypt-and-libgpg-error/self_comp_fix_pub.bc" "libgcrypt_self_comp_fix_pub"
    run_case "Libgcrypt 1.10.1 (Var Pub Self-Comp)" "libgcrypt-and-libgpg-error/self_comp_var_pub.bc" "libgcrypt_self_comp_var_pub"
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"
    openssl-1.1.1q/build.sh --self-comp --sym-size "$sym_size"
    for algo in recp mont mont_consttime mont_word; do
        run_case "OpenSSL 1.1.1q ${algo} (Fix Pub Self-Comp)" "openssl-1.1.1q/self_comp_fix_pub_${algo}.bc" "openssl_${algo}_self_comp_fix_pub"
        run_case "OpenSSL 1.1.1q ${algo} (Var Pub Self-Comp)" "openssl-1.1.1q/self_comp_var_pub_${algo}.bc" "openssl_${algo}_self_comp_var_pub"
    done
}

run_mbedtls
run_libgcrypt
run_openssl
