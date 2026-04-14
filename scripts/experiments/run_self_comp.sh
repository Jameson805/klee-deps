#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"

converter_module="tools.converters.self_comp_log_to_json"
if ! command -v python >/dev/null 2>&1; then
    echo "Error: python not found in PATH" >&2
    exit 1
fi

# set virtual memory limit to 70GB to prevent excessive memory usage
ulimit -v 70000000

klee_root=""
max_time=""
max_solver_time="30s"
kill_after="1800s"
sym_size=4
max_memory=10000
search_strategies="random-path,nurs:covnew"
do_reproduce=1
reproduce_timeout=180
benchmarks_csv=""
default_benchmarks=(mbedtls libgcrypt openssl)
selected_benchmarks=("${default_benchmarks[@]}")

usage() {
    cat <<EOF
Usage: $0 --klee-root <path-to-klee-build> --max-time <duration> [options]

Required:
  --klee-root <path>     Path containing klee binary (e.g. <repo>/klee-controlflow/build/bin)
  --max-time <duration>  Overall timeout for each KLEE run (e.g. 30m, 1h, 600s)

Optional:
  --sym-size <n>         Default: 4
  --max-solver-time <d>  Default: 30s
  --kill-after <duration> Default: 1800s
  --max-memory <n>       Default: 10000 (MB KLEE cap)
  --search <strategies>  Default: random-path,nurs:covnew (comma-separated)
  --results-dir <name>   Default: self_comp_results
  --no-reproduce         Disable replay-based validation (enabled by default)
  --reproduce-timeout <s> Timeout per replay attempt in seconds (default: 180)
  --benchmarks <list>    Comma-separated benchmark groups to run
    valid: mbedtls,libgcrypt,openssl
  default: all valid groups
  --help                 Show this help
EOF
    exit 1
}

results_dir="$repo_root/results/self_comp_results"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --klee-root) klee_root="$2"; shift 2;;
        --max-time) max_time="$2"; shift 2;;
        --sym-size) sym_size="$2"; shift 2;;
        --max-solver-time) max_solver_time="$2"; shift 2;;
        --kill-after) kill_after="$2"; shift 2;;
        --max-memory) max_memory="$2"; shift 2;;
        --search) search_strategies="$2"; shift 2;;
        --results-dir) results_dir="$2"; shift 2;;
        --no-reproduce) do_reproduce=0; shift 1;;
        --reproduce-timeout) reproduce_timeout="$2"; shift 2;;
        --benchmarks) benchmarks_csv="$2"; shift 2;;
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
if ! [[ "$reproduce_timeout" =~ ^[0-9]+$ ]]; then
    echo "Error: reproduce_timeout must be a non-negative integer (got '$reproduce_timeout')"; exit 1
fi

if [[ -n "$benchmarks_csv" ]]; then
    IFS=',' read -ra requested_benchmarks <<< "$benchmarks_csv"
    selected_benchmarks=()
    for raw in "${requested_benchmarks[@]}"; do
        bench="${raw//[[:space:]]/}"
        [[ -z "$bench" ]] && continue
        case "$bench" in
            mbedtls|libgcrypt|openssl)
                selected_benchmarks+=("$bench")
                ;;
            *)
                echo "Error: unknown benchmark '$bench' for --benchmarks" >&2
                exit 1
                ;;
        esac
    done
    if [[ "${#selected_benchmarks[@]}" -eq 0 ]]; then
        echo "Error: --benchmarks provided but no valid benchmark names were parsed" >&2
        exit 1
    fi
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
echo "search_strategies=$search_strategies"
echo "results_dir=$results_dir"
echo "do_reproduce=$do_reproduce"
echo "reproduce_timeout=$reproduce_timeout"
echo "benchmarks=$(IFS=','; echo "${selected_benchmarks[*]}")"
echo "##########"

klee_timeout() {
    local search_args=()
    IFS=',' read -ra ADDR <<< "$search_strategies"
    for i in "${ADDR[@]}"; do
        search_args+=( "--search=$i" )
    done

    timeout --foreground --signal=INT --kill-after="$kill_after" "$max_time" \
        stdbuf -oL -eL "$klee_root/klee" --libc=uclibc \
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
            --max-solver-time="$max_solver_time" \
            --max-memory=$max_memory \
            --emit-all-errors=true "$1" 2>&1 \
    | python -u -c 'import sys,time
for raw in sys.stdin.buffer:
    line = raw.decode("utf-8", errors="replace")
    sys.stdout.write(f"[{time.time():.3f}] {line}")
    sys.stdout.flush()' \
    || true
}

library_for_path() {
    local path="$1"
    case "$path" in
        *mbedtls-3.2.1*)
            echo "mbedtls"
            ;;
        *libgcrypt-and-libgpg-error*)
            echo "libgcrypt"
            ;;
        *openssl-1.1.1q*)
            echo "openssl"
            ;;
        *)
            echo ""
            ;;
    esac
}

run_case() {
    local title="$1"      # descriptive title
    local bc="$2"         # bitcode path
    local result_name="$3"
    local json_name="$4"
    local replay_exe="$5"

    local bc_dir=$(dirname "$bc")
    local case_log="$results_dir/${result_name}.log"
    local case_json="$results_dir/${json_name}"
    local library
    library="$(library_for_path "$bc")"
    if [[ -z "$library" ]]; then
        echo "Error: cannot infer library from path '$bc'" >&2
        exit 2
    fi

    echo "========="
    echo "$title"
    echo "========="

    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir"/klee-out-*
    klee_timeout "$bc" | tee "$case_log"
    if [[ -d "$bc_dir/klee-out-0" ]]; then
        mv "$bc_dir/klee-out-0" "$results_dir/$result_name"
    else
        echo "Warning: missing output directory '$bc_dir/klee-out-0'"
    fi
    local cmd=(
        python -m "$converter_module"
        --log "$case_log"
        --out "$case_json"
        --code-root "$bc_dir"
        --sym-size "$sym_size"
        --library "$library"
    )

    if [[ "$do_reproduce" -eq 1 ]]; then
        local replay_path="$bc_dir/$replay_exe"
        if [[ ! -x "$replay_path" ]]; then
            echo "Error: replay executable not found or not executable: $replay_path"
            exit 2
        fi
        cmd+=(
            --reproduce
            --replay-executable "$replay_path"
            --reproduce-timeout "$reproduce_timeout"
        )
    fi

    "${cmd[@]}"
    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir"/klee-out-*
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"
    benchmarks/mbedtls-3.2.1/build.sh --self-comp --preset "size_${sym_size}"
    run_case "Mbed TLS 3.2.1 (Fix Pub Self-Comp)" "benchmarks/mbedtls-3.2.1/self_comp_fix_pub.bc" "mbedtls_self_comp_fix_pub" "mbedtls_fix_pub.json" "klee_fix_pub_replay"
    run_case "Mbed TLS 3.2.1 (Var Pub Self-Comp)" "benchmarks/mbedtls-3.2.1/self_comp_var_pub.bc" "mbedtls_self_comp_var_pub" "mbedtls_var_pub.json" "klee_var_pub_replay"
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"
    benchmarks/libgcrypt-and-libgpg-error/build.sh --self-comp --preset "size_${sym_size}"
    run_case "Libgcrypt 1.10.1 (Fix Pub Self-Comp)" "benchmarks/libgcrypt-and-libgpg-error/self_comp_fix_pub.bc" "libgcrypt_self_comp_fix_pub" "libgcrypt_fix_pub.json" "klee_fix_pub_replay"
    run_case "Libgcrypt 1.10.1 (Var Pub Self-Comp)" "benchmarks/libgcrypt-and-libgpg-error/self_comp_var_pub.bc" "libgcrypt_self_comp_var_pub" "libgcrypt_var_pub.json" "klee_var_pub_replay"
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"
    benchmarks/openssl-1.1.1q/build.sh --self-comp --preset "size_${sym_size}"
    for algo in recp mont mont_consttime mont_word; do
        run_case "OpenSSL 1.1.1q ${algo} (Fix Pub Self-Comp)" "benchmarks/openssl-1.1.1q/self_comp_fix_pub_${algo}.bc" "openssl_${algo}_self_comp_fix_pub" "openssl_${algo}_fix_pub.json" "klee_fix_pub_replay_${algo}"
        run_case "OpenSSL 1.1.1q ${algo} (Var Pub Self-Comp)" "benchmarks/openssl-1.1.1q/self_comp_var_pub_${algo}.bc" "openssl_${algo}_self_comp_var_pub" "openssl_${algo}_var_pub.json" "klee_var_pub_replay_${algo}"
    done
}

for benchmark in "${selected_benchmarks[@]}"; do
    case "$benchmark" in
        mbedtls)
            run_mbedtls
            ;;
        libgcrypt)
            run_libgcrypt
            ;;
        openssl)
            run_openssl
            ;;
    esac
done
