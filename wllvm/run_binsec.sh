#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

sym_size=4
jump_enum=3
max_time=""

usage() {
    cat <<EOF
Usage: $0 [--sym-size <n>] [--jump-enum <n>] <max_time_seconds>

  <max_time_seconds>   Required integer (timeout in seconds for BINSEC)
  --sym-size <n>       Optional integer, default: 4
  --jump-enum <n>      Optional integer, default: 3
EOF
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sym-size)
            sym_size="${2:-}"; shift 2 ;;
        --jump-enum)
            jump_enum="${2:-}"; shift 2 ;;
        -*)
            echo "Unknown option: $1"; usage ;;
        *)
            if [[ -z "$max_time" ]]; then
                max_time="$1"; shift
            else
                echo "Unexpected argument: $1"; usage
            fi ;;
    esac
done

if [[ -z "$max_time" ]]; then
    echo "Error: <max_time_seconds> is required."
    usage
fi

# Validate integers
for pair in "max_time:$max_time" "sym_size:$sym_size" "jump_enum:$jump_enum"; do
    name="${pair%%:*}"
    val="${pair##*:}"
    if ! [[ "$val" =~ ^[0-9]+$ ]]; then
        echo "Error: $name must be a non-negative integer (got '$val')" >&2
        exit 1
    fi
done

echo "##########"
echo "Args:"
echo "max_time=$max_time"
echo "sym_size=$sym_size"
echo "jump_enum=$jump_enum"
echo "##########"

results_dir="binsec_results"
rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

run_case() {
    local sse_script="$1"      # e.g. binsec_fix_pub.cfg
    local stats_file="$2"      # e.g. mbedtls_fix_pub.toml (filename only)
    local executable="$3"      # e.g. mbedtls-3.2.1/binsec_fix_pub
    binsec -sse -checkct \
        -sse-timeout "$max_time" \
        -sse-jump-enum "$jump_enum" \
        -sse-script "$sse_script" \
        -checkct-stats-file "$results_dir/$stats_file" \
        "$executable"
}

run_mbedtls() {
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"

    mbedtls-3.2.1/build.sh ${sym_size}
    run_case "binsec_fix_pub.cfg" "mbedtls_fix_pub.toml" "mbedtls-3.2.1/binsec_fix_pub"
    run_case "binsec_var_pub.cfg" "mbedtls_var_pub.toml" "mbedtls-3.2.1/binsec_var_pub"
}

run_libgcrypt() {
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"

    libgcrypt-and-libgpg-error/build.sh ${sym_size}
    run_case "binsec_fix_pub.cfg" "libgcrypt_fix_pub.toml" "libgcrypt-and-libgpg-error/binsec_fix_pub"
    run_case "binsec_var_pub.cfg" "libgcrypt_var_pub.toml" "libgcrypt-and-libgpg-error/binsec_var_pub"
}

run_openssl() {
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"

    openssl-1.1.1q/build.sh ${sym_size}
    for algo in recp mont mont_consttime mont_word; do
        run_case "binsec_fix_pub.cfg" "openssl_${algo}_fix_pub.toml" "openssl-1.1.1q/binsec_fix_pub_${algo}"
        run_case "binsec_var_pub.cfg" "openssl_${algo}_var_pub.toml" "openssl-1.1.1q/binsec_var_pub_${algo}"
    done
}

run_mbedtls
run_libgcrypt
run_openssl
