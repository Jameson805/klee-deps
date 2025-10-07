#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bin_path=$(realpath ../klee-controlflow/build/bin)
script_path=$(realpath ../klee-controlflow/scripts)
export PATH="$bin_path:$script_path:$PATH"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <max_time>"
    exit 1
fi
max_time="$1"
kill_after="10s"
max_solver_time="5s"

klee_timeout() {
    timeout --kill-after="$kill_after" "$max_time" \
    klee --max-solver-time="$max_solver_time" --libc=uclibc --posix-runtime "$@" \
    || true
}

rm -rf results
mkdir results
exec > >(tee -a results/output.log) 2>&1

echo "##########"
echo "Begin experiments for Mbed TLS 3.2.1"
echo "##########"

mbedtls-3.2.1/build.sh
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

echo "##########"
echo "Begin experiments for Libgcrypt 1.10.1"
echo "##########"

libgcrypt-and-libgpg-error/build.sh
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*

echo "========="
echo "Libgcrypt 1.10.1 (Fix Pub)"
echo "========="
klee_timeout libgcrypt-and-libgpg-error/klee_fix_pub.bc
mv libgcrypt-and-libgpg-error/klee-out-0 results/libgcrypt_fix_pub
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/libgcrypt1.10.1/2.json results/libgcrypt_fix_pub results/libgcrypt_fix_pub_combined.json --code-path libgcrypt-and-libgpg-error/libgcrypt-1.10.1/src
reproduce_positives.py results/libgcrypt_fix_pub_combined.json results/libgcrypt_fix_pub libgcrypt-and-libgpg-error/klee_fix_pub_replay --secret exp --output results/libgcrypt_fix_pub_combined.json
make_report.py results/libgcrypt_fix_pub_combined.json results/libgcrypt_fix_pub_report.html
make_plot.py results/libgcrypt_fix_pub_combined.json "Libgcrypt 1.10.1 (Fix Pub)" results/libgcrypt_fix_pub_plot.png

echo "========="
echo "Libgcrypt 1.10.1 (Var Pub)"
echo "========="
klee_timeout libgcrypt-and-libgpg-error/klee_var_pub.bc
mv libgcrypt-and-libgpg-error/klee-out-0 results/libgcrypt_var_pub
rm -f libgcrypt-and-libgpg-error/klee-last
rm -rf libgcrypt-and-libgpg-error/klee-out-*
compare_with_ctchecker.py ../ctchecker_results/libgcrypt1.10.1/2.json results/libgcrypt_var_pub results/libgcrypt_var_pub_combined.json --code-path libgcrypt-and-libgpg-error/libgcrypt-1.10.1/src
reproduce_positives.py results/libgcrypt_var_pub_combined.json results/libgcrypt_var_pub libgcrypt-and-libgpg-error/klee_var_pub_replay --secret exp --public base,mod --output results/libgcrypt_var_pub_combined.json
make_report.py results/libgcrypt_var_pub_combined.json results/libgcrypt_var_pub_report.html
make_plot.py results/libgcrypt_var_pub_combined.json "Libgcrypt 1.10.1 (Var Pub)" results/libgcrypt_var_pub_plot.png