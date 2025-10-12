#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bin_path=$(realpath ../klee-controlflow/build/bin)
script_path=$(realpath ../klee-controlflow/scripts)
export PATH="$bin_path:$script_path:$PATH"

# defaults
max_time=""
loop_max_iterations=20
max_solver_time="5s"
kill_after="10s"

usage() {
    cat <<EOF
Usage: $0 [--kill-after <duration>] [--max-solver-time <duration>] [--loop-max-iterations <n>] <max_time>

  <max_time>               - required, e.g. 1h, 30m, 600s
  --loop-max-iterations n  - optional, default: 20
  --max-solver-time <dur>  - optional, default: 5s
  --kill-after <duration>  - optional, default: 10s
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

echo "##########"
echo "Args:"
echo "max_time=$max_time"
echo "loop_max_iterations=$loop_max_iterations"
echo "max_solver_time=$max_solver_time"
echo "kill_after=$kill_after"
echo "##########"

klee_timeout() {
    timeout --kill-after="$kill_after" "$max_time" \
    klee --max-solver-time="$max_solver_time" --libc=uclibc --posix-runtime "$1" \
    || true
}

limit_loop() {
    if [ -z "$3" ]; then
        opt \
            -load ../loop-limiter/build/libLoopLimiter.so \
            -load-pass-plugin=../loop-limiter/build/libLoopLimiter.so \
            -passes=loop-limiter \
            -max-iterations="$loop_max_iterations" \
            "$1" -o "$2"
    else
        opt \
            -load ../loop-limiter/build/libLoopLimiter.so \
            -load-pass-plugin=../loop-limiter/build/libLoopLimiter.so \
            -passes=loop-limiter \
            -max-iterations="$loop_max_iterations" \
            -functions="$3" \
            "$1" -o "$2"
    fi
}


rm -rf results
mkdir results
exec > >(tee -a results/output.log) 2>&1

echo "##########"
echo "Begin experiments for Mbed TLS 3.2.1"
echo "##########"

mbedtls-3.2.1/build.sh
limit_loop mbedtls-3.2.1/klee_fix_pub.bc mbedtls-3.2.1/klee_fix_pub_lim_loop.bc mbedtls_mpi_exp_mod
limit_loop mbedtls-3.2.1/klee_var_pub.bc mbedtls-3.2.1/klee_var_pub_lim_loop.bc mbedtls_mpi_exp_mod
rm -f mbedtls-3.2.1/klee-last
rm -rf mbedtls-3.2.1/klee-out-*

echo "========="
echo "Mbed TLS 3.2.1 (Fix Pub)"
echo "========="
klee_timeout mbedtls-3.2.1/klee_fix_pub.bc
mv mbedtls-3.2.1/klee-out-0 results/mbedtls_fix_pub
rm -f mbedtls-3.2.1/klee-last
rm -rf mbedtls-3.2.1/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/mbedtls3.2.1/2.json results/mbedtls_fix_pub results/mbedtls_fix_pub_combined.json --code-path mbedtls-3.2.1/library --lines 1968:2202
reproduce_positives.py results/mbedtls_fix_pub_combined.json results/mbedtls_fix_pub mbedtls-3.2.1/klee_fix_pub_replay --secret E --output results/mbedtls_fix_pub_combined.json
make_report.py results/mbedtls_fix_pub_combined.json results/mbedtls_fix_pub_report.html
make_plot.py results/mbedtls_fix_pub_combined.json "Mbed TLS 3.2.1 (Fix Pub)" results/mbedtls_fix_pub_plot.png

echo "========="
echo "Mbed TLS 3.2.1 (Fix Pub Lim Loop)"
echo "========="
klee_timeout mbedtls-3.2.1/klee_fix_pub_lim_loop.bc
mv mbedtls-3.2.1/klee-out-0 results/mbedtls_fix_pub_lim_loop
rm -f mbedtls-3.2.1/klee-last
rm -rf mbedtls-3.2.1/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/mbedtls3.2.1/2.json results/mbedtls_fix_pub_lim_loop results/mbedtls_fix_pub_lim_loop_combined.json --code-path mbedtls-3.2.1/library --lines 1968:2202
reproduce_positives.py results/mbedtls_fix_pub_lim_loop_combined.json results/mbedtls_fix_pub_lim_loop mbedtls-3.2.1/klee_fix_pub_replay --secret E --output results/mbedtls_fix_pub_lim_loop_combined.json
make_report.py results/mbedtls_fix_pub_lim_loop_combined.json results/mbedtls_fix_pub_lim_loop_report.html
make_plot.py results/mbedtls_fix_pub_lim_loop_combined.json "Mbed TLS 3.2.1 (Fix Pub Lim Loop)" results/mbedtls_fix_pub_lim_loop_plot.png

echo "========="
echo "Mbed TLS 3.2.1 (Var Pub)"
echo "========="
klee_timeout mbedtls-3.2.1/klee_var_pub.bc
mv mbedtls-3.2.1/klee-out-0 results/mbedtls_var_pub
rm -f mbedtls-3.2.1/klee-last
rm -rf mbedtls-3.2.1/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/mbedtls3.2.1/2.json results/mbedtls_var_pub results/mbedtls_var_pub_combined.json --code-path mbedtls-3.2.1/library --lines 1968:2202
reproduce_positives.py results/mbedtls_var_pub_combined.json results/mbedtls_var_pub mbedtls-3.2.1/klee_var_pub_replay --secret E --public A,N --output results/mbedtls_var_pub_combined.json
make_report.py results/mbedtls_var_pub_combined.json results/mbedtls_var_pub_report.html
make_plot.py results/mbedtls_var_pub_combined.json "Mbed TLS 3.2.1 (Var Pub)" results/mbedtls_var_pub_plot.png

echo "========="
echo "Mbed TLS 3.2.1 (Var Pub Lim Loop)"
echo "========="
klee_timeout mbedtls-3.2.1/klee_var_pub_lim_loop.bc
mv mbedtls-3.2.1/klee-out-0 results/mbedtls_var_pub_lim_loop
rm -f mbedtls-3.2.1/klee-last
rm -rf mbedtls-3.2.1/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/mbedtls3.2.1/2.json results/mbedtls_var_pub_lim_loop results/mbedtls_var_pub_lim_loop_combined.json --code-path mbedtls-3.2.1/library --lines 1968:2202
reproduce_positives.py results/mbedtls_var_pub_lim_loop_combined.json results/mbedtls_var_pub_lim_loop mbedtls-3.2.1/klee_var_pub_replay --secret E --public A,N --output results/mbedtls_var_pub_lim_loop_combined.json
make_report.py results/mbedtls_var_pub_lim_loop_combined.json results/mbedtls_var_pub_lim_loop_report.html
make_plot.py results/mbedtls_var_pub_lim_loop_combined.json "Mbed TLS 3.2.1 (Var Pub Lim Loop)" results/mbedtls_var_pub_lim_loop_plot.png

echo "##########"
echo "Begin experiments for Libgcrypt 1.10.1"
echo "##########"

libgcrypt-and-libgpg-error/build.sh
limit_loop libgcrypt-and-libgpg-error/klee_fix_pub.bc  libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc _gcry_mpi_powm
limit_loop libgcrypt-and-libgpg-error/klee_var_pub.bc  libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc _gcry_mpi_powm
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*

echo "========="
echo "Libgcrypt 1.10.1 (Fix Pub)"
echo "========="
klee_timeout libgcrypt-and-libgpg-error/klee_fix_pub.bc
mv libgcrypt-and-libgpg-error/klee-out-0 results/libgcrypt_fix_pub
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/libgcrypt1.10.1/2.json results/libgcrypt_fix_pub results/libgcrypt_fix_pub_combined.json --code-path libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi
reproduce_positives.py results/libgcrypt_fix_pub_combined.json results/libgcrypt_fix_pub libgcrypt-and-libgpg-error/klee_fix_pub_replay --secret exp --output results/libgcrypt_fix_pub_combined.json
make_report.py results/libgcrypt_fix_pub_combined.json results/libgcrypt_fix_pub_report.html
make_plot.py results/libgcrypt_fix_pub_combined.json "Libgcrypt 1.10.1 (Fix Pub)" results/libgcrypt_fix_pub_plot.png

echo "========="
echo "Libgcrypt 1.10.1 (Fix Pub Lim Loop)"
echo "========="
klee_timeout libgcrypt-and-libgpg-error/klee_fix_pub_lim_loop.bc
mv libgcrypt-and-libgpg-error/klee-out-0 results/libgcrypt_fix_pub_lim_loop
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/libgcrypt1.10.1/2.json results/libgcrypt_fix_pub_lim_loop results/libgcrypt_fix_pub_lim_loop_combined.json --code-path libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi
reproduce_positives.py results/libgcrypt_fix_pub_lim_loop_combined.json results/libgcrypt_fix_pub_lim_loop libgcrypt-and-libgpg-error/klee_fix_pub_replay --secret exp --output results/libgcrypt_fix_pub_lim_loop_combined.json
make_report.py results/libgcrypt_fix_pub_lim_loop_combined.json results/libgcrypt_fix_pub_lim_loop_report.html
make_plot.py results/libgcrypt_fix_pub_lim_loop_combined.json "Libgcrypt 1.10.1 (Fix Pub Lim Loop)" results/libgcrypt_fix_pub_lim_loop_plot.png

echo "========="
echo "Libgcrypt 1.10.1 (Var Pub)"
echo "========="
klee_timeout libgcrypt-and-libgpg-error/klee_var_pub.bc
mv libgcrypt-and-libgpg-error/klee-out-0 results/libgcrypt_var_pub
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/libgcrypt1.10.1/2.json results/libgcrypt_var_pub results/libgcrypt_var_pub_combined.json --code-path libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi
reproduce_positives.py results/libgcrypt_var_pub_combined.json results/libgcrypt_var_pub libgcrypt-and-libgpg-error/klee_var_pub_replay --secret exp --public base,mod --output results/libgcrypt_var_pub_combined.json
make_report.py results/libgcrypt_var_pub_combined.json results/libgcrypt_var_pub_report.html
make_plot.py results/libgcrypt_var_pub_combined.json "Libgcrypt 1.10.1 (Var Pub)" results/libgcrypt_var_pub_plot.png

echo "========="
echo "Libgcrypt 1.10.1 (Var Pub Lim Loop)"
echo "========="
klee_timeout libgcrypt-and-libgpg-error/klee_var_pub_lim_loop.bc
mv libgcrypt-and-libgpg-error/klee-out-0 results/libgcrypt_var_pub_lim_loop
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/libgcrypt1.10.1/2.json results/libgcrypt_var_pub_lim_loop results/libgcrypt_var_pub_lim_loop_combined.json --code-path libgcrypt-and-libgpg-error/libgcrypt-1.10.1/mpi
reproduce_positives.py results/libgcrypt_var_pub_lim_loop_combined.json results/libgcrypt_var_pub_lim_loop libgcrypt-and-libgpg-error/klee_var_pub_replay --secret exp --public base,mod --output results/libgcrypt_var_pub_lim_loop_combined.json
make_report.py results/libgcrypt_var_pub_lim_loop_combined.json results/libgcrypt_var_pub_lim_loop_report.html
make_plot.py results/libgcrypt_var_pub_combined.json "Libgcrypt 1.10.1 (Var Pub Lim Loop)" results/libgcrypt_var_pub_plot.png
