#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"
if ! command -v python >/dev/null 2>&1; then
    echo "Error: python not found in PATH" >&2
    exit 1
fi
bin_path="$repo_root/klee-eager/build/bin"
export PATH="$bin_path:$PATH"

# set virtual memory limit to 70GB to prevent excessive memory usage
ulimit -v 70000000

# defaults
max_time=""
loop_max_iterations=10
max_solver_time="30s"
kill_after="1800s"
sym_size=4
max_memory=10000
mod_exp_only="false"
search_strategies="random-path,nurs:covnew"
product_program_fallback="false"
solver_backend="stp"
optimize_array="false"
pin_root=""
benchmarks_csv=""
default_benchmarks=(mbedtls libgcrypt openssl bearssl)
selected_benchmarks=("${default_benchmarks[@]}")

usage() {
    cat <<EOF
Usage: $0 [--sym-size <n>] [--loop-max-iterations <n>] [--max-solver-time <duration>] [--kill-after <duration>] [--max-memory <n>] [--mod-exp-only] [--search <strategies>] [--solver-backend <stp|metasmt|dummy|z3>] [--optimize-array <false|all|index|value>] [--benchmarks <list>] <max_time>

  <max_time>               - required, e.g. 1h, 30m, 600s
  --sym-size <n>           - optional, default: 4 (size in bytes for bignum symbols)
  --loop-max-iterations n  - optional, default: 10
  --max-solver-time <dur>  - optional, default: 30s
  --kill-after <duration>  - optional, default: 1800s
  --max-memory <n>         - optional, default: 10000 (MB KLEE state cap)
  --mod-exp-only           - optional, default: false
  --search <strategies>    - optional, default: random-path,nurs:covnew (comma-separated)
  --product-program-fallback - optional, default: false (enables Executor::bindLocal fallback repair)
  --solver-backend <name>  - optional, default: stp (stp|metasmt|dummy|z3)
  --optimize-array <value> - optional, default: false (false|all|index|value)
    --pin-root <path>       - optional, path to external Intel Pin kit (defaults to PIN_ROOT)
  --benchmarks <list>      - optional, comma-separated benchmark groups to run
        valid: mbedtls,libgcrypt,openssl,bearssl
  default: all valid groups
EOF
    exit 1
}

# parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --kill-after)
            kill_after="$2"; shift 2;;
        --max-solver-time)
            max_solver_time="$2"; shift 2;;
        --loop-max-iterations)
            loop_max_iterations="$2"; shift 2;;
        --sym-size)
            sym_size="$2"; shift 2;;
        --max-memory)
            max_memory="$2"; shift 2;;
        --mod-exp-only)
            mod_exp_only="true"; shift;;
        --search)
            search_strategies="$2"; shift 2;;
        --product-program-fallback)
            product_program_fallback="true"; shift;;
        --solver-backend)
            solver_backend="$2"; shift 2;;
        --optimize-array)
            optimize_array="$2"; shift 2;;
        --pin-root)
            pin_root="$2"; shift 2;;
        --benchmarks)
            benchmarks_csv="$2"; shift 2;;
        --)
            shift; break;;
        -*)
            echo "Unknown option: $1"; usage;;
        *)
            if [[ -z "$max_time" ]]; then
                max_time="$1"; shift
            else
                echo "Unexpected argument: $1"; usage
            fi;;
    esac
done

if [[ -z "$max_time" ]]; then
    echo "Error: <max_time> is required."
    usage
fi

# Validate numeric loop_max_iterations
if ! [[ "$loop_max_iterations" =~ ^[0-9]+$ ]]; then
    echo "Error: loop_max_iterations must be a non-negative integer (got '$loop_max_iterations')"
    exit 1
fi
if ! [[ "$sym_size" =~ ^[0-9]+$ ]]; then
    echo "Error: sym_size must be a non-negative integer (got '$sym_size')"
    exit 1
fi
if ! [[ "$max_memory" =~ ^[0-9]+$ ]]; then
    echo "Error: max_memory must be a non-negative integer (got '$max_memory')"
    exit 1
fi
if [[ "$product_program_fallback" != "true" && "$product_program_fallback" != "false" ]]; then
    echo "Error: product_program_fallback must be 'true' or 'false' (got '$product_program_fallback')"
    exit 1
fi

if [[ -n "$benchmarks_csv" ]]; then
    IFS=',' read -ra requested_benchmarks <<< "$benchmarks_csv"
    selected_benchmarks=()
    for raw in "${requested_benchmarks[@]}"; do
        bench="${raw//[[:space:]]/}"
        [[ -z "$bench" ]] && continue
        case "$bench" in
            mbedtls|libgcrypt|openssl|bearssl)
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

case "$solver_backend" in
    stp|metasmt|dummy|z3) ;;
    *)
        echo "Error: solver_backend must be one of: stp, metasmt, dummy, z3 (got '$solver_backend')"
        exit 1
        ;;
esac

case "$optimize_array" in
    false|all|index|value) ;;
    *)
        echo "Error: optimize_array must be one of: false, all, index, value (got '$optimize_array')"
        exit 1
        ;;
esac

results_dir="$repo_root/results/klee_eager_results"
rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

echo "##########"
echo "Args:"
echo "max_time=$max_time"
echo "sym_size=$sym_size"
echo "loop_max_iterations=$loop_max_iterations"
echo "max_solver_time=$max_solver_time"
echo "kill_after=$kill_after"
echo "max_memory=$max_memory"
echo "mod_exp_only=$mod_exp_only"
echo "search_strategies=$search_strategies"
echo "product_program_fallback=$product_program_fallback"
echo "solver_backend=$solver_backend"
echo "optimize_array=$optimize_array"
echo "pin_root=${pin_root:-<env PIN_ROOT>}"
echo "benchmarks=$(IFS=','; echo "${selected_benchmarks[*]}")"
echo "##########"

klee_timeout() {
    local search_args=()
    local optimize_args=()
    IFS=',' read -ra ADDR <<< "$search_strategies"
    for i in "${ADDR[@]}"; do
        search_args+=( "--search=$i" )
    done

    if [[ "$optimize_array" != "false" ]]; then
        optimize_args+=( "--optimize-array=$optimize_array" )
    fi

    timeout --foreground --signal=INT --kill-after="$kill_after" $max_time \
    klee --libc=uclibc \
        --posix-runtime \
        --external-calls=all \
        --solver-backend="$solver_backend" \
        --product-program-fallback="$product_program_fallback" \
        --kdalloc \
        --kdalloc-constants-size=5 \
        --kdalloc-globals-size=5 \
        --kdalloc-heap-size=20 \
        --kdalloc-stack-size=10 \
        --dump-states-on-halt=false \
        --use-batching-search=false \
        "${search_args[@]}" \
        "${optimize_args[@]}" \
        --max-solver-time="$max_solver_time" \
        --max-memory=$max_memory "$1" || true
}

limit_loop() {
    opt \
        -load "$repo_root/loop-limiter/build/libLoopLimiter.so" \
        -load-pass-plugin="$repo_root/loop-limiter/build/libLoopLimiter.so" \
        -passes=loop-limiter \
        -max-iterations="$loop_max_iterations" \
        $@
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
        *bearssl*)
            echo "bearssl"
            ;;
        *)
            echo ""
            ;;
    esac
}

run_case() {
    local title="$1"          # e.g. "Mbed TLS 3.2.1 (Fix Pub)"
    local bc="$2"             # e.g. benchmarks/mbedtls-3.2.1/klee_fix_pub.bc
    local result_name="$3"    # e.g. mbedtls_fix_pub
    local replay_script="$4"  # e.g. benchmarks/mbedtls-3.2.1/klee_fix_pub_replay
    local replay_opts="$5"    # e.g. "--secret E" or "--secret exp --public base,mod"
    local ct_json="$6"        # e.g. ctchecker_results/mbedtls3.2.1/3.json
    local code_path="$7"      # e.g. benchmarks/mbedtls-3.2.1/library
    local memory_flag="$8"    # must be "true" or "false"
    shift 8                   # Remaining args (if any) are extra compare args, e.g., --lines ...

    if [[ "$memory_flag" != "true" && "$memory_flag" != "false" ]]; then
        echo "Error: memory_flag must be 'true' or 'false' (got '$memory_flag')" >&2
        exit 1
    fi

    local bc_dir
    bc_dir=$(dirname "$bc")
    local library
    local replay_args=()
    library="$(library_for_path "$bc")"
    if [[ -z "$library" ]]; then
        echo "Error: cannot infer library from path '$bc'" >&2
        exit 2
    fi
    if [[ -n "$replay_opts" ]]; then
        # shellcheck disable=SC2206
        replay_args=( $replay_opts )
    fi

    echo "========="
    echo "$title"
    echo "========="
    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir/klee-out-"*
    klee_timeout "$bc"
    mv "$bc_dir/klee-out-0" "$results_dir/$result_name"
    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir/klee-out-"*

    local branch_compare_cmd=(python -m tools.converters.compare_with_ctchecker branch "$ct_json" "$results_dir/$result_name" "$results_dir/${result_name}_branch.json" --code-path "$code_path" --library "$library")
    branch_compare_cmd+=("$@")
    branch_compare_cmd+=("${replay_args[@]}")
    "${branch_compare_cmd[@]}"

    local branch_reproduce_cmd=(python -m tools.postprocess.reproduce_positives --json "$results_dir/${result_name}_branch.json" --klee-output "$results_dir/$result_name" --executable "$replay_script" --library "$library" --output "$results_dir/${result_name}_branch.json")
    if [[ -n "$pin_root" ]]; then
        branch_reproduce_cmd+=(--pin-root "$pin_root")
    fi
    branch_reproduce_cmd+=("${replay_args[@]}")
    "${branch_reproduce_cmd[@]}"
    # make_report.py "$results_dir/${result_name}_branch.json" "$results_dir/${result_name}_branch_report.html"

    if [[ "$memory_flag" == "true" ]]; then
        local memory_compare_cmd=(python -m tools.converters.compare_with_ctchecker memory "$ct_json" "$results_dir/$result_name" "$results_dir/${result_name}_memory.json" --code-path "$code_path" --library "$library")
        memory_compare_cmd+=("$@")
        memory_compare_cmd+=("${replay_args[@]}")
        "${memory_compare_cmd[@]}"

        local memory_reproduce_cmd=(python -m tools.postprocess.reproduce_positives --json "$results_dir/${result_name}_memory.json" --klee-output "$results_dir/$result_name" --executable "$replay_script" --library "$library" --output "$results_dir/${result_name}_memory.json")
        if [[ -n "$pin_root" ]]; then
            memory_reproduce_cmd+=(--pin-root "$pin_root")
        fi
        memory_reproduce_cmd+=("${replay_args[@]}")
        "${memory_reproduce_cmd[@]}"
        # make_report.py "$results_dir/${result_name}_memory.json" "$results_dir/${result_name}_memory_report.html"
    fi
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"

    benchmarks/mbedtls-3.2.1/build.sh --klee-cf --preset size_${sym_size}
    limit_loop \
        -blacklist=bitlen_i64_nosign,mbedtls_mpi_bitlen,mbedtls_clz \
        -o benchmarks/mbedtls-3.2.1/klee_fix_pub_lim_loop.bc \
        benchmarks/mbedtls-3.2.1/klee_fix_pub.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign \
        -break \
        -o benchmarks/mbedtls-3.2.1/klee_fix_pub_lim_loop_break.bc \
        benchmarks/mbedtls-3.2.1/klee_fix_pub.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign,mbedtls_mpi_bitlen,mbedtls_clz \
        -o benchmarks/mbedtls-3.2.1/klee_var_pub_lim_loop.bc \
        benchmarks/mbedtls-3.2.1/klee_var_pub.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign \
        -break \
        -o benchmarks/mbedtls-3.2.1/klee_var_pub_lim_loop_break.bc \
        benchmarks/mbedtls-3.2.1/klee_var_pub.bc

    EXTRA_ARGS=( --ctchecker-prefix "library" )
    if [ "$mod_exp_only" = "true" ]; then
        EXTRA_ARGS+=( --filename bignum.c --lines 1968:2202 )
    fi

    run_case "Mbed TLS 3.2.1 (Fix Pub)" "benchmarks/mbedtls-3.2.1/klee_fix_pub.bc" "mbedtls_fix_pub" "benchmarks/mbedtls-3.2.1/klee_fix_pub_replay" "--secret exp" "ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    # run_case "Mbed TLS 3.2.1 (Fix Pub Lim Loop)" "benchmarks/mbedtls-3.2.1/klee_fix_pub_lim_loop.bc" "mbedtls_fix_pub_lim_loop" "benchmarks/mbedtls-3.2.1/klee_fix_pub_replay" "--secret exp" "ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    # run_case "Mbed TLS 3.2.1 (Fix Pub Lim Loop Break)" "benchmarks/mbedtls-3.2.1/klee_fix_pub_lim_loop_break.bc" "mbedtls_fix_pub_lim_loop_break" "benchmarks/mbedtls-3.2.1/klee_fix_pub_replay" "--secret exp" "ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    run_case "Mbed TLS 3.2.1 (Var Pub)" "benchmarks/mbedtls-3.2.1/klee_var_pub.bc" "mbedtls_var_pub" "benchmarks/mbedtls-3.2.1/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    # run_case "Mbed TLS 3.2.1 (Var Pub Lim Loop)" "benchmarks/mbedtls-3.2.1/klee_var_pub_lim_loop.bc" "mbedtls_var_pub_lim_loop" "benchmarks/mbedtls-3.2.1/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    run_case "Mbed TLS 3.2.1 (Var Pub Lim Loop Break)" "benchmarks/mbedtls-3.2.1/klee_var_pub_lim_loop_break.bc" "mbedtls_var_pub_lim_loop_break" "benchmarks/mbedtls-3.2.1/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
}

run_mbedtls_sliced() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1 (Sliced)"
    echo "##########"

    benchmarks/mbedtls-3.2.1/build.sh --klee-cf --preset size_${sym_size}
    limit_loop \
        -blacklist=bitlen_i64_nosign,mbedtls_mpi_bitlen,mbedtls_clz \
        -o benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_lim_loop.bc \
        benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign \
        -break \
        -o benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_lim_loop_break.bc \
        benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign,mbedtls_mpi_bitlen,mbedtls_clz \
        -o benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_lim_loop.bc \
        benchmarks/mbedtls-3.2.1/klee_var_pub_sliced.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign \
        -break \
        -o benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_lim_loop_break.bc \
        benchmarks/mbedtls-3.2.1/klee_var_pub_sliced.bc

    EXTRA_ARGS=()

    run_case "Mbed TLS 3.2.1 (Fix Pub Sliced)" "benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced.bc" "mbedtls_fix_pub_sliced" "benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_replay" "--secret exp" "ctchecker_results/mbedtls3.2.1-sliced/2.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    # run_case "Mbed TLS 3.2.1 (Fix Pub Sliced Lim Loop)" "benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_lim_loop.bc" "mbedtls_fix_pub_sliced_lim_loop" "benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_replay" "--secret exp" "ctchecker_results/mbedtls3.2.1-sliced/2.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    # run_case "Mbed TLS 3.2.1 (Fix Pub Sliced Lim Loop Break)" "benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_lim_loop_break.bc" "mbedtls_fix_pub_sliced_lim_loop_break" "benchmarks/mbedtls-3.2.1/klee_fix_pub_sliced_replay" "--secret exp" "ctchecker_results/mbedtls3.2.1-sliced/2.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    run_case "Mbed TLS 3.2.1 (Var Pub Sliced)" "benchmarks/mbedtls-3.2.1/klee_var_pub_sliced.bc" "mbedtls_var_pub_sliced" "benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_replay" "--secret exp --public base,mod" "ctchecker_results/mbedtls3.2.1-sliced/2.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    # run_case "Mbed TLS 3.2.1 (Var Pub Sliced Lim Loop)" "benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_lim_loop.bc" "mbedtls_var_pub_sliced_lim_loop" "benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_replay" "--secret exp --public base,mod" "ctchecker_results/mbedtls3.2.1-sliced/2.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
    run_case "Mbed TLS 3.2.1 (Var Pub Sliced Lim Loop Break)" "benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_lim_loop_break.bc" "mbedtls_var_pub_sliced_lim_loop_break" "benchmarks/mbedtls-3.2.1/klee_var_pub_sliced_replay" "--secret exp --public base,mod" "ctchecker_results/mbedtls3.2.1-sliced/2.json" "mbedtls-3.2.1" false "${EXTRA_ARGS[@]}"
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"

    benchmarks/libgcrypt-and-libgpg-error/build.sh --klee-cf --preset size_${sym_size}
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen,__builtin_clzl,__builtin_clz,__builtin_ctzl,__builtin_ctz,_gcry_mpih_lshift \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen,__builtin_clzl,__builtin_clz,__builtin_ctzl,__builtin_ctz,_gcry_mpih_lshift \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_var_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen \
        -break \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop_break.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen \
        -break \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop_break.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_var_pub.bc

    EXTRA_ARGS=()
    if [ "$mod_exp_only" = "true" ]; then
        EXTRA_ARGS+=( --filename mpi-pow.c --lines 404:771 )
    fi

    run_case "Libgcrypt 1.10.1 (Fix Pub)" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub.bc" "libgcrypt_fix_pub" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "ctchecker_results/libgcrypt1.10.1/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false "${EXTRA_ARGS[@]}"
    # run_case "Libgcrypt 1.10.1 (Fix Pub Lim Loop)" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc" "libgcrypt_fix_pub_lim_loop" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "ctchecker_results/libgcrypt1.10.1/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false "${EXTRA_ARGS[@]}"
    # run_case "Libgcrypt 1.10.1 (Fix Pub Lim Loop Break)" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop_break.bc" "libgcrypt_fix_pub_lim_loop_break" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "ctchecker_results/libgcrypt1.10.1/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false "${EXTRA_ARGS[@]}"
    run_case "Libgcrypt 1.10.1 (Var Pub)" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub.bc" "libgcrypt_var_pub" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/libgcrypt1.10.1/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false "${EXTRA_ARGS[@]}"
    # run_case "Libgcrypt 1.10.1 (Var Pub Lim Loop)" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc" "libgcrypt_var_pub_lim_loop" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/libgcrypt1.10.1/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false "${EXTRA_ARGS[@]}"
    run_case "Libgcrypt 1.10.1 (Var Pub Lim Loop Break)" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop_break.bc" "libgcrypt_var_pub_lim_loop_break" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/libgcrypt1.10.1/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false "${EXTRA_ARGS[@]}"
}


run_libgcrypt_sliced() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1 (Sliced)"
    echo "##########"

    benchmarks/libgcrypt-and-libgpg-error/build.sh --klee-cf --preset size_${sym_size} --sliced
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen,__builtin_clzl,__builtin_clz,__builtin_ctzl,__builtin_ctz,_gcry_mpih_lshift \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen,__builtin_clzl,__builtin_clz,__builtin_ctzl,__builtin_ctz,_gcry_mpih_lshift \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_var_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen \
        -break \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop_break.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen \
        -break \
        -o benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop_break.bc \
        benchmarks/libgcrypt-and-libgpg-error/klee_var_pub.bc

    EXTRA_ARGS=()
    if [ "$mod_exp_only" = "true" ]; then
        EXTRA_ARGS+=( --filename mpi-pow.c --lines 404:771 )
    fi

    run_case "Libgcrypt 1.10.1 (Fix Pub Sliced)" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub.bc" "libgcrypt_fix_pub_sliced" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "ctchecker_results/libgcrypt1.10.1-sliced/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1-sliced/mpi" false "${EXTRA_ARGS[@]}"
    # run_case "Libgcrypt 1.10.1 (Fix Pub Sliced Lim Loop)" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc" "libgcrypt_fix_pub_sliced_lim_loop" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "ctchecker_results/libgcrypt1.10.1-sliced/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1-sliced/mpi" false "${EXTRA_ARGS[@]}"
    # run_case "Libgcrypt 1.10.1 (Fix Pub Sliced Lim Loop Break)" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop_break.bc" "libgcrypt_fix_pub_sliced_lim_loop_break" "benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "ctchecker_results/libgcrypt1.10.1-sliced/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1-sliced/mpi" false "${EXTRA_ARGS[@]}"
    run_case "Libgcrypt 1.10.1 (Var Pub Sliced)" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub.bc" "libgcrypt_var_pub_sliced" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/libgcrypt1.10.1-sliced/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1-sliced/mpi" false "${EXTRA_ARGS[@]}"
    # run_case "Libgcrypt 1.10.1 (Var Pub Sliced Lim Loop)" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc" "libgcrypt_var_pub_sliced_lim_loop" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/libgcrypt1.10.1-sliced/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1-sliced/mpi" false "${EXTRA_ARGS[@]}"
    run_case "Libgcrypt 1.10.1 (Var Pub Sliced Lim Loop Break)" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_lim_loop_break.bc" "libgcrypt_var_pub_sliced_lim_loop_break" "benchmarks/libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "ctchecker_results/libgcrypt1.10.1-sliced/3.json" "benchmarks/libgcrypt-and-libgpg-error/libgcrypt-1.10.1-sliced/mpi" false "${EXTRA_ARGS[@]}"
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"

    benchmarks/openssl-1.1.1q/build.sh --klee-cf --preset size_${sym_size}

    for algo in recp mont mont_consttime mont_word; do
        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen,bn_add_words,bn_sub_words,bn_mul_add_words,bn_mul_words,bn_sqr_words,bn_div_words,bn_mul_mont,BN_num_bits,MOD_EXP_CTIME_COPY_TO_PREBUF,MOD_EXP_CTIME_COPY_FROM_PREBUF \
            -o "benchmarks/openssl-1.1.1q/klee_fix_pub_lim_loop_${algo}.bc" \
            "benchmarks/openssl-1.1.1q/klee_fix_pub_${algo}.bc"

        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen,bn_add_words,bn_sub_words,bn_mul_add_words,bn_mul_words,bn_sqr_words,bn_div_words,bn_mul_mont,BN_num_bits,MOD_EXP_CTIME_COPY_TO_PREBUF,MOD_EXP_CTIME_COPY_FROM_PREBUF \
            -o "benchmarks/openssl-1.1.1q/klee_var_pub_lim_loop_${algo}.bc" \
            "benchmarks/openssl-1.1.1q/klee_var_pub_${algo}.bc"

        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen \
            -break \
            -o "benchmarks/openssl-1.1.1q/klee_fix_pub_lim_loop_break_${algo}.bc" \
            "benchmarks/openssl-1.1.1q/klee_fix_pub_${algo}.bc"

        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen \
            -break \
            -o "benchmarks/openssl-1.1.1q/klee_var_pub_lim_loop_break_${algo}.bc" \
            "benchmarks/openssl-1.1.1q/klee_var_pub_${algo}.bc"
    done

    run_openssl_algo() {
        local algo="$1"
        local memory_flag="$2"    # "true" or "false"
        local lines_range="$3"    # e.g. "161:295"

        if [[ "$memory_flag" != "true" && "$memory_flag" != "false" ]]; then
            echo "Error: memory_flag must be 'true' or 'false' (got '$memory_flag')" >&2
            exit 1
        fi

        echo "##########"
        echo "Running OpenSSL 1.1.1q ${algo} tests"
        echo "##########"

        run_case "OpenSSL 1.1.1q ${algo} (Fix Pub)" "benchmarks/openssl-1.1.1q/klee_fix_pub_${algo}.bc" "openssl_${algo}_fix_pub" "benchmarks/openssl-1.1.1q/klee_fix_pub_replay_${algo}" "--secret exp" "ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q" "$memory_flag" --ctchecker-prefix "crypto/bn"
        # run_case "OpenSSL 1.1.1q ${algo} (Fix Pub Lim Loop)" "benchmarks/openssl-1.1.1q/klee_fix_pub_lim_loop_${algo}.bc" "openssl_${algo}_fix_pub_lim_loop" "benchmarks/openssl-1.1.1q/klee_fix_pub_replay_${algo}" "--secret exp" "ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q" "$memory_flag" --ctchecker-prefix "crypto/bn"
        # run_case "OpenSSL 1.1.1q ${algo} (Fix Pub Lim Loop Break)" "benchmarks/openssl-1.1.1q/klee_fix_pub_lim_loop_break_${algo}.bc" "openssl_${algo}_fix_pub_lim_loop_break" "benchmarks/openssl-1.1.1q/klee_fix_pub_replay_${algo}" "--secret exp" "ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q" "$memory_flag" --ctchecker-prefix "crypto/bn"
        run_case "OpenSSL 1.1.1q ${algo} (Var Pub)" "benchmarks/openssl-1.1.1q/klee_var_pub_${algo}.bc" "openssl_${algo}_var_pub" "benchmarks/openssl-1.1.1q/klee_var_pub_replay_${algo}" "--secret exp --public base,mod" "ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q" "$memory_flag" --ctchecker-prefix "crypto/bn"
        # run_case "OpenSSL 1.1.1q ${algo} (Var Pub Lim Loop)" "benchmarks/openssl-1.1.1q/klee_var_pub_lim_loop_${algo}.bc" "openssl_${algo}_var_pub_lim_loop" "benchmarks/openssl-1.1.1q/klee_var_pub_replay_${algo}" "--secret exp --public base,mod" "ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q" "$memory_flag" --ctchecker-prefix "crypto/bn"
        run_case "OpenSSL 1.1.1q ${algo} (Var Pub Lim Loop Break)" "benchmarks/openssl-1.1.1q/klee_var_pub_lim_loop_break_${algo}.bc" "openssl_${algo}_var_pub_lim_loop_break" "benchmarks/openssl-1.1.1q/klee_var_pub_replay_${algo}" "--secret exp --public base,mod" "ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q" "$memory_flag" --ctchecker-prefix "crypto/bn"
    }

    run_openssl_algo recp false 161:295
    run_openssl_algo mont false 297:471
    run_openssl_algo mont_consttime false 593:1136
    run_openssl_algo mont_word false 1138:1283
}

run_bearssl() {
    echo "##########"
    echo "Begin experiments for BearSSL 0.6"
    echo "##########"

    benchmarks/bearssl/build.sh --klee-eager --preset default
    run_case "BearSSL 0.6 aes_big" "benchmarks/bearssl/klee_fix_pub_binsec_aes_big.bc" "bearssl_aes_big" "benchmarks/bearssl/klee_fix_pub_replay_binsec_aes_big" "--secret skey,data" "ctchecker_results/BearSSL0.6/empty.json" "benchmarks/bearssl" true
    run_case "BearSSL 0.6 des_tab" "benchmarks/bearssl/klee_fix_pub_appliedcryp_des.bc" "bearssl_des_tab" "benchmarks/bearssl/klee_fix_pub_replay_appliedcryp_des" "--secret skey,data" "ctchecker_results/BearSSL0.6/empty.json" "benchmarks/bearssl" true
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
        bearssl)
            run_bearssl
            ;;
    esac
done
