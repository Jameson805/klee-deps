#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bin_path=$(realpath ../klee-controlflow/build/bin)
script_path=$(realpath ../klee-controlflow/scripts)
export PATH="$bin_path:$script_path:$PATH"

# defaults
max_time=""
loop_max_iterations=10
max_solver_time="10s"
kill_after="5m"
sym_size=4
max_memory=8000

usage() {
    cat <<EOF
Usage: $0 [--sym-size <n>] [--loop-max-iterations <n>] [--max-solver-time <duration>] [--kill-after <duration>] [--max-memory <n>] <max_time>

  <max_time>               - required, e.g. 1h, 30m, 600s
  --sym-size <n>           - optional, default: 4 (size in bytes for bignum symbols)
  --loop-max-iterations n  - optional, default: 10
  --max-solver-time <dur>  - optional, default: 10s
  --kill-after <duration>  - optional, default: 10s
  --max-memory <n>         - optional, default: 8000 (MB KLEE state cap)
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

results_dir="klee_cf_results"
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
echo "##########"

klee_timeout() {
    timeout --foreground --signal=INT --kill-after=30s $max_time \
    klee --libc=uclibc \
        --posix-runtime \
        --dump-states-on-halt=false \
        --use-batching-search=true \
        --max-solver-time="$max_solver_time" \
        --max-memory=$max_memory "$1" || true
}

limit_loop() {
    opt \
        -load ../loop-limiter/build/libLoopLimiter.so \
        -load-pass-plugin=../loop-limiter/build/libLoopLimiter.so \
        -passes=loop-limiter \
        -max-iterations="$loop_max_iterations" \
        $@
}

run_case() {
    local title="$1"          # e.g. "Mbed TLS 3.2.1 (Fix Pub)"
    local bc="$2"             # e.g. mbedtls-3.2.1/klee_fix_pub.bc
    local result_name="$3"    # e.g. mbedtls_fix_pub
    local replay_script="$4"  # e.g. mbedtls-3.2.1/klee_fix_pub_replay
    local replay_opts="$5"    # e.g. "--secret E" or "--secret exp --public base,mod"
    local ct_json="$6"        # e.g. ../ctchecker_results/mbedtls3.2.1/3.json
    local code_path="$7"      # e.g. mbedtls-3.2.1/library
    local memory_flag="$8"    # must be "true" or "false"
    shift 8                   # Remaining args (if any) are extra compare args, e.g., --lines ...

    if [[ "$memory_flag" != "true" && "$memory_flag" != "false" ]]; then
        echo "Error: memory_flag must be 'true' or 'false' (got '$memory_flag')" >&2
        exit 1
    fi

    local bc_dir
    bc_dir=$(dirname "$bc")

    echo "========="
    echo "$title"
    echo "========="
    klee_timeout "$bc"
    mv "$bc_dir/klee-out-0" "$results_dir/$result_name"
    rm -f "$bc_dir/klee-last"
    rm -rf "$bc_dir/klee-out-*"

    compare_with_ctchecker.py branch "$ct_json" "$results_dir/$result_name" "$results_dir/${result_name}_branch.json" --code-path "$code_path" "$@"
    reproduce_positives.py "$results_dir/${result_name}_branch.json" "$results_dir/$result_name" "$replay_script" $replay_opts --output "$results_dir/${result_name}_branch.json"
    make_report.py "$results_dir/${result_name}_branch.json" "$results_dir/${result_name}_branch_report.html"
    make_plot.py "$results_dir/${result_name}_branch.json" "$title (Branch)" "$results_dir/${result_name}_branch_plot.png"

    if [[ "$memory_flag" == "true" ]]; then
        compare_with_ctchecker.py memory "$ct_json" "$results_dir/$result_name" "$results_dir/${result_name}_memory.json" --code-path "$code_path" "$@"
        make_report.py "$results_dir/${result_name}_memory.json" "$results_dir/${result_name}_memory_report.html"
        make_plot.py "$results_dir/${result_name}_memory.json" "$title" "$results_dir/${result_name}_memory_plot.png"
    fi
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"

    mbedtls-3.2.1/build.sh ${sym_size}
    limit_loop \
        -blacklist=bitlen_i64_nosign,mbedtls_mpi_bitlen,mbedtls_clz \
        -o mbedtls-3.2.1/klee_fix_pub_lim_loop.bc \
        mbedtls-3.2.1/klee_fix_pub.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign \
        -break \
        -o mbedtls-3.2.1/klee_fix_pub_lim_loop_break.bc \
        mbedtls-3.2.1/klee_fix_pub.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign,mbedtls_mpi_bitlen,mbedtls_clz \
        -o mbedtls-3.2.1/klee_var_pub_lim_loop.bc \
        mbedtls-3.2.1/klee_var_pub.bc
    limit_loop \
        -blacklist=bitlen_i64_nosign \
        -break \
        -o mbedtls-3.2.1/klee_var_pub_lim_loop_break.bc \
        mbedtls-3.2.1/klee_var_pub.bc
    rm -f mbedtls-3.2.1/klee-last
    rm -rf mbedtls-3.2.1/klee-out-*

    run_case "Mbed TLS 3.2.1 (Fix Pub)" "mbedtls-3.2.1/klee_fix_pub.bc" "mbedtls_fix_pub" "mbedtls-3.2.1/klee_fix_pub_replay" "--secret exp" "../ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1/library" false --filename bignum.c --lines 1968:2202
    # run_case "Mbed TLS 3.2.1 (Fix Pub Lim Loop)" "mbedtls-3.2.1/klee_fix_pub_lim_loop.bc" "mbedtls_fix_pub_lim_loop" "mbedtls-3.2.1/klee_fix_pub_replay" "--secret exp" "../ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1/library" false --filename bignum.c --lines 1968:2202
    # run_case "Mbed TLS 3.2.1 (Fix Pub Lim Loop Break)" "mbedtls-3.2.1/klee_fix_pub_lim_loop_break.bc" "mbedtls_fix_pub_lim_loop_break" "mbedtls-3.2.1/klee_fix_pub_replay" "--secret exp" "../ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1/library" false --filename bignum.c --lines 1968:2202
    run_case "Mbed TLS 3.2.1 (Var Pub)" "mbedtls-3.2.1/klee_var_pub.bc" "mbedtls_var_pub" "mbedtls-3.2.1/klee_var_pub_replay" "--secret exp --public base,mod" "../ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1/library" false --filename bignum.c --lines 1968:2202
    # run_case "Mbed TLS 3.2.1 (Var Pub Lim Loop)" "mbedtls-3.2.1/klee_var_pub_lim_loop.bc" "mbedtls_var_pub_lim_loop" "mbedtls-3.2.1/klee_var_pub_replay" "--secret exp --public base,mod" "../ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1/library" false --filename bignum.c --lines 1968:2202
    run_case "Mbed TLS 3.2.1 (Var Pub Lim Loop Break)" "mbedtls-3.2.1/klee_var_pub_lim_loop_break.bc" "mbedtls_var_pub_lim_loop_break" "mbedtls-3.2.1/klee_var_pub_replay" "--secret exp --public base,mod" "../ctchecker_results/mbedtls3.2.1/3.json" "mbedtls-3.2.1/library" false --filename bignum.c --lines 1968:2202
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"

    libgcrypt-and-libgpg-error/build.sh ${sym_size}
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen,__builtin_clzl,__builtin_clz,__builtin_ctzl,__builtin_ctz,_gcry_mpih_lshift \
        -o libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc \
        libgcrypt-and-libgpg-error/klee_fix_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen,__builtin_clzl,__builtin_clz,__builtin_ctzl,__builtin_ctz,_gcry_mpih_lshift \
        -o libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc \
        libgcrypt-and-libgpg-error/klee_var_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen \
        -break \
        -o libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop_break.bc \
        libgcrypt-and-libgpg-error/klee_fix_pub.bc
    limit_loop \
        -blacklist=buf_nonzero,buf_bitlen \
        -break \
        -o libgcrypt-and-libgpg-error/klee_var_pub_lim_loop_break.bc \
        libgcrypt-and-libgpg-error/klee_var_pub.bc
    rm -f libgcrypt-and-libgpg-error/klee-last
    rm -rf libgcrypt-and-libgpg-error/klee-out-*

    run_case "Libgcrypt 1.10.1 (Fix Pub)" "libgcrypt-and-libgpg-error/klee_fix_pub.bc" "libgcrypt_fix_pub" "libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "../ctchecker_results/libgcrypt1.10.1/3.json" "libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false --filename mpi-pow.c --lines 404:771
    # run_case "Libgcrypt 1.10.1 (Fix Pub Lim Loop)" "libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc" "libgcrypt_fix_pub_lim_loop" "libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "../ctchecker_results/libgcrypt1.10.1/3.json" "libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false --filename mpi-pow.c --lines 404:771
    # run_case "Libgcrypt 1.10.1 (Fix Pub Lim Loop Break)" "libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop_break.bc" "libgcrypt_fix_pub_lim_loop_break" "libgcrypt-and-libgpg-error/klee_fix_pub_replay" "--secret exp" "../ctchecker_results/libgcrypt1.10.1/3.json" "libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false --filename mpi-pow.c --lines 404:771
    run_case "Libgcrypt 1.10.1 (Var Pub)" "libgcrypt-and-libgpg-error/klee_var_pub.bc" "libgcrypt_var_pub" "libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "../ctchecker_results/libgcrypt1.10.1/3.json" "libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false --filename mpi-pow.c --lines 404:771
    # run_case "Libgcrypt 1.10.1 (Var Pub Lim Loop)" "libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc" "libgcrypt_var_pub_lim_loop" "libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "../ctchecker_results/libgcrypt1.10.1/3.json" "libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false --filename mpi-pow.c --lines 404:771
    run_case "Libgcrypt 1.10.1 (Var Pub Lim Loop Break)" "libgcrypt-and-libgpg-error/klee_var_pub_lim_loop_break.bc" "libgcrypt_var_pub_lim_loop_break" "libgcrypt-and-libgpg-error/klee_var_pub_replay" "--secret exp --public base,mod" "../ctchecker_results/libgcrypt1.10.1/3.json" "libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi" false --filename mpi-pow.c --lines 404:771
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"

    openssl-1.1.1q/build.sh ${sym_size}

    for algo in recp mont mont_consttime mont_word; do
        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen,bn_add_words,bn_sub_words,bn_mul_add_words,bn_mul_words,bn_sqr_words,bn_div_words,bn_mul_mont,BN_num_bits,MOD_EXP_CTIME_COPY_TO_PREBUF,MOD_EXP_CTIME_COPY_FROM_PREBUF \
            -o "openssl-1.1.1q/klee_fix_pub_lim_loop_${algo}.bc" \
            "openssl-1.1.1q/klee_fix_pub_${algo}.bc"

        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen,bn_add_words,bn_sub_words,bn_mul_add_words,bn_mul_words,bn_sqr_words,bn_div_words,bn_mul_mont,BN_num_bits,MOD_EXP_CTIME_COPY_TO_PREBUF,MOD_EXP_CTIME_COPY_FROM_PREBUF \
            -o "openssl-1.1.1q/klee_var_pub_lim_loop_${algo}.bc" \
            "openssl-1.1.1q/klee_var_pub_${algo}.bc"

        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen \
            -break \
            -o "openssl-1.1.1q/klee_fix_pub_lim_loop_break_${algo}.bc" \
            "openssl-1.1.1q/klee_fix_pub_${algo}.bc"

        limit_loop \
            -blacklist=buf_nonzero,buf_bitlen \
            -break \
            -o "openssl-1.1.1q/klee_var_pub_lim_loop_break_${algo}.bc" \
            "openssl-1.1.1q/klee_var_pub_${algo}.bc"
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

        rm -f "openssl-1.1.1q/klee-last"
        rm -rf "openssl-1.1.1q/klee-out-*"

        run_case "OpenSSL 1.1.1q ${algo} (Fix Pub)" "openssl-1.1.1q/klee_fix_pub_${algo}.bc" "openssl_${algo}_fix_pub" "openssl-1.1.1q/klee_fix_pub_replay_${algo}" "--secret exp" "../ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q/crypto/bn" "$memory_flag" --filename bn_exp.c --lines "$lines_range" --src-prefix crypto/bn
        # run_case "OpenSSL 1.1.1q ${algo} (Fix Pub Lim Loop)" "openssl-1.1.1q/klee_fix_pub_lim_loop_${algo}.bc" "openssl_${algo}_fix_pub_lim_loop" "openssl-1.1.1q/klee_fix_pub_replay_${algo}" "--secret exp" "../ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q/crypto/bn" "$memory_flag" --filename bn_exp.c --lines "$lines_range" --src-prefix crypto/bn
        # run_case "OpenSSL 1.1.1q ${algo} (Fix Pub Lim Loop Break)" "openssl-1.1.1q/klee_fix_pub_lim_loop_break_${algo}.bc" "openssl_${algo}_fix_pub_lim_loop_break" "openssl-1.1.1q/klee_fix_pub_replay_${algo}" "--secret exp" "../ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q/crypto/bn" "$memory_flag" --filename bn_exp.c --lines "$lines_range" --src-prefix crypto/bn
        run_case "OpenSSL 1.1.1q ${algo} (Var Pub)" "openssl-1.1.1q/klee_var_pub_${algo}.bc" "openssl_${algo}_var_pub" "openssl-1.1.1q/klee_var_pub_replay_${algo}" "--secret exp --public base,mod" "../ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q/crypto/bn" "$memory_flag" --filename bn_exp.c --lines "$lines_range" --src-prefix crypto/bn
        # run_case "OpenSSL 1.1.1q ${algo} (Var Pub Lim Loop)" "openssl-1.1.1q/klee_var_pub_lim_loop_${algo}.bc" "openssl_${algo}_var_pub_lim_loop" "openssl-1.1.1q/klee_var_pub_replay_${algo}" "--secret exp --public base,mod" "../ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q/crypto/bn" "$memory_flag" --filename bn_exp.c --lines "$lines_range" --src-prefix crypto/bn
        run_case "OpenSSL 1.1.1q ${algo} (Var Pub Lim Loop Break)" "openssl-1.1.1q/klee_var_pub_lim_loop_break_${algo}.bc" "openssl_${algo}_var_pub_lim_loop_break" "openssl-1.1.1q/klee_var_pub_replay_${algo}" "--secret exp --public base,mod" "../ctchecker_results/openSSL_1_1_1q/${algo}-3.json" "openssl-1.1.1q/crypto/bn" "$memory_flag" --filename bn_exp.c --lines "$lines_range" --src-prefix crypto/bn
    }

    run_openssl_algo recp false 161:295
    run_openssl_algo mont false 297:471
    run_openssl_algo mont_consttime false 593:1136
    run_openssl_algo mont_word false 1138:1283
}

run_mbedtls
run_libgcrypt
run_openssl
