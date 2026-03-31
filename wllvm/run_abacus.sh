#!/usr/bin/env bash
set -euo pipefail

sym_size=4
abacus_root=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sym-size)
            [[ $# -lt 2 ]] && echo "Missing value for --sym-size" >&2 && exit 1
            sym_size="$2"
            shift 2
            ;;
        --sym-size=*)
            sym_size="${1#--sym-size=}"
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            if [[ -z "$abacus_root" ]]; then
                abacus_root="$1"
                shift
            else
                echo "Unexpected extra argument: $1" >&2
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$abacus_root" ]]; then
    echo "Usage: $0 <abacus_root> [--sym-size N]" >&2
    exit 1
fi
if ! [[ "$sym_size" =~ ^[0-9]+$ ]]; then
    echo "Invalid --sym-size value: $sym_size" >&2
    exit 1
fi

cd "$(dirname "$0")"
results_dir="abacus_results"
rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

run_case() {
    local exe="$1"
    local outfile="$2"
    local case_log="${results_dir}/${outfile%.txt}.log"
    local case_json="${results_dir}/${outfile%.txt}.json"
    {
        "${abacus_root}/Intel-Pin-Archive/pin" -t "${abacus_root}/Pintools/obj-ia32/MyPinToolLinux.so" -- "$exe"
        "${abacus_root}/build/App/QIF/QIF" ./Inst_data.txt -f Function.txt -d "$exe" -o "${results_dir}/$outfile"
    } 2>&1 | tee "$case_log"
    python3 abacus_log_to_json.py \
        --log "$case_log" \
        --out "$case_json" \
        --sym-size "$sym_size" \
        --code-root "$(pwd)"
    rm -f Inst_data.txt Function.txt
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"

    mbedtls-3.2.1/build.sh --abacus --sym-size ${sym_size}
    run_case "mbedtls-3.2.1/abacus_fix_pub" "mbedtls.txt"
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"

    libgcrypt-and-libgpg-error/build.sh --abacus --sym-size ${sym_size}
    run_case "libgcrypt-and-libgpg-error/abacus_fix_pub" "libgcrypt.txt"
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"

    openssl-1.1.1q/build.sh --abacus --sym-size ${sym_size}
    for algo in recp mont mont_consttime mont_word; do
        run_case "openssl-1.1.1q/abacus_fix_pub_${algo}" "openssl_${algo}.txt"
    done
}

run_mbedtls
run_libgcrypt
run_openssl
