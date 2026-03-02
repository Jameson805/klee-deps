#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# BINSEC -> JSON converter (Python 3.11+ for tomllib)
repo_root="$(cd .. && pwd)"
converter_py="$repo_root/utils/binsec_toml_to_json.py"
python_bin="$repo_root/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
    python_bin="$(command -v python3 || true)"
fi

sym_size=4
jump_enum=10
sse_depth=1000000000000
max_time=""

patch_memset_ifunc=0

do_reproduce=1

usage() {
    cat <<EOF
Usage: $0 [--sym-size <n>] [--jump-enum <n>] [--sse-depth <n>] <max_time_seconds>

  <max_time_seconds>   Required integer (timeout in seconds for BINSEC)
  --sym-size <n>       Optional integer, default: 4
  --jump-enum <n>      Optional integer, default: 10
  --sse-depth <n>      Optional integer, default: 1000000000
  --patch-memset-ifunc Optional, pin `memset_func`'s PLT/GOT slot to a concrete memset impl
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
        --sse-depth)
            sse_depth="${2:-}"; shift 2 ;;
        --patch-memset-ifunc)
            patch_memset_ifunc=1; shift ;;
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
for pair in "max_time:$max_time" "sym_size:$sym_size" "jump_enum:$jump_enum" "sse_depth:$sse_depth"; do
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
echo "sse_depth=$sse_depth"
echo "patch_memset_ifunc=$patch_memset_ifunc"
echo "##########"

results_dir="binsec_results"
rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

code_path_for_executable() {
    local exe="$1"
    case "$exe" in
        mbedtls-3.2.1/*)
            echo "mbedtls-3.2.1"
            ;;
        libgcrypt-and-libgpg-error/*)
            echo "libgcrypt-and-libgpg-error"
            ;;
        openssl-1.1.1q/*)
            echo "openssl-1.1.1q"
            ;;
        *)
            echo ""
            ;;
    esac
}

replay_executable_for_executable() {
    local exe="$1"

    # mbedtls/libgcrypt convention: binsec_{fix,var}_pub -> binsec_{fix,var}_pub_replay
    if [[ "$exe" =~ /binsec_(fix|var)_pub$ ]]; then
        echo "${exe}_replay"
        return 0
    fi

    # openssl convention: binsec_{fix,var}_pub_<algo> -> binsec_{fix,var}_pub_replay_<algo>
    if [[ "$exe" =~ /binsec_fix_pub_(.+)$ ]]; then
        echo "${exe/binsec_fix_pub_/binsec_fix_pub_replay_}"
        return 0
    fi
    if [[ "$exe" =~ /binsec_var_pub_(.+)$ ]]; then
        echo "${exe/binsec_var_pub_/binsec_var_pub_replay_}"
        return 0
    fi

    echo ""
}

convert_case_to_json() {
    local stats_file="$1"     # e.g. mbedtls_fix_pub.toml (filename only)
    local executable="$2"     # e.g. mbedtls-3.2.1/binsec_fix_pub

    if [[ ! -f "$results_dir/$stats_file" ]]; then
        echo "Warning: missing stats file $results_dir/$stats_file; skipping JSON conversion" >&2
        return 0
    fi
    if [[ ! -f "$results_dir/output.log" ]]; then
        echo "Warning: missing $results_dir/output.log; skipping JSON conversion" >&2
        return 0
    fi
    if [[ ! -f "$converter_py" ]]; then
        echo "Warning: missing converter script: $converter_py; skipping JSON conversion" >&2
        return 0
    fi
    if [[ -z "$python_bin" ]]; then
        echo "Error: python3 not found; cannot run JSON conversion" >&2
        return 1
    fi

    local out_json="$results_dir/${stats_file%.toml}.json"
    local code_path
    code_path="$(code_path_for_executable "$executable")"

    echo "-----"
    echo "Converting $results_dir/$stats_file -> $out_json"
    echo "-----"

    local cmd=(
        "$python_bin" "$converter_py"
        --toml "$results_dir/$stats_file"
        --output-log "$results_dir/output.log"
        --executable "$executable"
        --sym-size "$sym_size"
        --out "$out_json"
    )
    if [[ -n "$code_path" ]]; then
        cmd+=(--code-path "$code_path")
    fi

    if [[ "$do_reproduce" -eq 1 ]]; then
        local replay_exe
        replay_exe="$(replay_executable_for_executable "$executable")"
        if [[ -z "$replay_exe" ]]; then
            echo "Error: cannot infer replay executable for '$executable'" >&2
            return 2
        fi
        if [[ ! -x "$replay_exe" ]]; then
            echo "Error: inferred replay executable is not runnable: $replay_exe" >&2
            return 2
        fi
        cmd+=(--reproduce --replay-executable "$replay_exe")
    fi

    "${cmd[@]}"
}

run_case() {
    local title="$1"           # e.g. "Mbed TLS 3.2.1 (Fix Pub)"
    local sse_script="$2"      # e.g. binsec_fix_pub.cfg
    local stats_file="$3"      # e.g. mbedtls_fix_pub.toml (filename only)
    local executable="$4"      # e.g. mbedtls-3.2.1/binsec_fix_pub

    local sse_script_to_use="$sse_script"
    if [[ "$patch_memset_ifunc" -eq 1 ]]; then
        local patcher_py="$repo_root/utils/binsec_patch_memset_ifunc.py"
        if [[ -f "$patcher_py" && -n "$python_bin" ]]; then
            local out_cfg="$results_dir/patched_${sse_script%.cfg}_$(basename "$executable").cfg"
            "$python_bin" "$patcher_py" \
                --exe "$executable" \
                --base-cfg "$sse_script" \
                --out-cfg "$out_cfg" \
                >/dev/null
            sse_script_to_use="$out_cfg"
        else
            echo "Warning: --patch-memset-ifunc requested but patcher or python is missing; using base script" >&2
        fi
    fi

    echo "========="
    echo "$title"
    echo "========="

    binsec -sse -checkct \
        -sse-timeout "$max_time" \
        -sse-jump-enum "$jump_enum" \
        -sse-script "$sse_script_to_use" \
        -sse-depth "$sse_depth" \
        -sse-heuristics nurs \
        -checkct-features control-flow,memory-access \
        -checkct-stats-file "$results_dir/$stats_file" \
        "$executable"

    convert_case_to_json "$stats_file" "$executable"
}

_BUILT_MBEDTLS=0
_BUILT_LIBGCRYPT=0
_BUILT_OPENSSL=0

ensure_built_mbedtls() {
    if [[ "$_BUILT_MBEDTLS" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"
    mbedtls-3.2.1/build.sh --binsec --sym-size "${sym_size}"
    _BUILT_MBEDTLS=1
}

ensure_built_libgcrypt() {
    if [[ "$_BUILT_LIBGCRYPT" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"
    libgcrypt-and-libgpg-error/build.sh --binsec --sym-size "${sym_size}"
    _BUILT_LIBGCRYPT=1
}

ensure_built_openssl() {
    if [[ "$_BUILT_OPENSSL" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"
    openssl-1.1.1q/build.sh --binsec --sym-size "${sym_size}"
    _BUILT_OPENSSL=1
}

run_mbedtls_case() {
    local kind="$1"  # fix_pub | var_pub
    ensure_built_mbedtls
    case "$kind" in
        fix_pub)
            run_case "Mbed TLS 3.2.1 (Fix Pub)" "binsec_fix_pub.cfg" "mbedtls_fix_pub.toml" "mbedtls-3.2.1/binsec_fix_pub"
            ;;
        var_pub)
            run_case "Mbed TLS 3.2.1 (Var Pub)" "binsec_var_pub.cfg" "mbedtls_var_pub.toml" "mbedtls-3.2.1/binsec_var_pub"
            ;;
        *)
            echo "Error: unknown mbedtls kind '$kind'" >&2
            return 2
            ;;
    esac
}

run_libgcrypt_case() {
    local kind="$1"  # fix_pub | var_pub
    ensure_built_libgcrypt
    case "$kind" in
        fix_pub)
            run_case "Libgcrypt 1.10.1 (Fix Pub)" "binsec_fix_pub.cfg" "libgcrypt_fix_pub.toml" "libgcrypt-and-libgpg-error/binsec_fix_pub"
            ;;
        var_pub)
            run_case "Libgcrypt 1.10.1 (Var Pub)" "binsec_var_pub.cfg" "libgcrypt_var_pub.toml" "libgcrypt-and-libgpg-error/binsec_var_pub"
            ;;
        *)
            echo "Error: unknown libgcrypt kind '$kind'" >&2
            return 2
            ;;
    esac
}

run_openssl_case() {
    local algo="$1"  # recp | mont | mont_consttime | mont_word
    local kind="$2"  # fix_pub | var_pub
    ensure_built_openssl
    case "$kind" in
        fix_pub)
            run_case "OpenSSL 1.1.1q ${algo} (Fix Pub)" "binsec_fix_pub.cfg" "openssl_${algo}_fix_pub.toml" "openssl-1.1.1q/binsec_fix_pub_${algo}"
            ;;
        var_pub)
            run_case "OpenSSL 1.1.1q ${algo} (Var Pub)" "binsec_var_pub.cfg" "openssl_${algo}_var_pub.toml" "openssl-1.1.1q/binsec_var_pub_${algo}"
            ;;
        *)
            echo "Error: unknown openssl kind '$kind'" >&2
            return 2
            ;;
    esac
}

########################
# Cases (comment out any single line to skip)
########################

run_mbedtls_case fix_pub
run_mbedtls_case var_pub

run_libgcrypt_case fix_pub
run_libgcrypt_case var_pub

run_openssl_case recp fix_pub
run_openssl_case recp var_pub
run_openssl_case mont fix_pub
run_openssl_case mont var_pub
run_openssl_case mont_consttime fix_pub
run_openssl_case mont_consttime var_pub
run_openssl_case mont_word fix_pub
run_openssl_case mont_word var_pub
