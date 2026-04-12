#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
converter_module="tools.converters.abacus_log_to_json"

if ! command -v python >/dev/null 2>&1; then
    echo "Error: python not found in PATH" >&2
    exit 1
fi

sym_size=4
abacus_root=""
benchmarks_csv=""
default_benchmarks=(mbedtls libgcrypt openssl)
selected_benchmarks=("${default_benchmarks[@]}")
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sym-size)
            [[ $# -lt 2 ]] && echo "Missing value for --sym-size" >&2 && exit 1
            sym_size="$2"
            shift 2
            ;;
        --benchmarks)
            [[ $# -lt 2 ]] && echo "Missing value for --benchmarks" >&2 && exit 1
            benchmarks_csv="$2"
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
    echo "Usage: $0 <abacus_root> [--sym-size N] [--benchmarks LIST]" >&2
    exit 1
fi
if ! [[ "$sym_size" =~ ^[0-9]+$ ]]; then
    echo "Invalid --sym-size value: $sym_size" >&2
    exit 1
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

cd "$repo_root"
results_dir="$repo_root/results/abacus_results"
rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

run_case() {
    local exe="$1"
    local outfile="$2"
    local library=""
    case "$exe" in
        *mbedtls-3.2.1*)
            library="mbedtls"
            ;;
        *libgcrypt-and-libgpg-error*)
            library="libgcrypt"
            ;;
        *openssl-1.1.1q*)
            library="openssl"
            ;;
    esac
    if [[ -z "$library" ]]; then
        echo "Error: cannot infer library from executable '$exe'" >&2
        exit 2
    fi
    local case_log="${results_dir}/${outfile%.txt}.log"
    local case_json="${results_dir}/${outfile%.txt}.json"
    {
        "${abacus_root}/Intel-Pin-Archive/pin" -t "${abacus_root}/Pintools/obj-ia32/MyPinToolLinux.so" -- "$exe"
        "${abacus_root}/build/App/QIF/QIF" ./Inst_data.txt -f Function.txt -d "$exe" -o "${results_dir}/$outfile"
    } 2>&1 | tee "$case_log"
    python -m "$converter_module" \
        --log "$case_log" \
        --out "$case_json" \
        --sym-size "$sym_size" \
        --code-root "$repo_root" \
        --library "$library"
    rm -f Inst_data.txt Function.txt
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"

    benchmarks/mbedtls-3.2.1/build.sh --abacus --sym-size ${sym_size}
    run_case "benchmarks/mbedtls-3.2.1/abacus_fix_pub" "mbedtls.txt"
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"

    benchmarks/libgcrypt-and-libgpg-error/build.sh --abacus --sym-size ${sym_size}
    run_case "benchmarks/libgcrypt-and-libgpg-error/abacus_fix_pub" "libgcrypt.txt"
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"

    benchmarks/openssl-1.1.1q/build.sh --abacus --sym-size ${sym_size}
    for algo in recp mont mont_consttime mont_word; do
        run_case "benchmarks/openssl-1.1.1q/abacus_fix_pub_${algo}" "openssl_${algo}.txt"
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
