#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"

# BINSEC -> JSON converter (Python 3.11+ for tomllib)
converter_module="tools.converters.binsec_toml_to_json"
python_bin="$repo_root/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
    python_bin="$(command -v python3 || true)"
fi

# Use an explicit SMT solver that understands SMT-LIB set-option (e.g., z3/cvc5).
binsec_fml_solver="z3"
binsec_smt_solver="z3"

sym_size=4
jump_enum=10
sse_depth=1000000000000
max_time=""

patch_memset_ifunc=0

do_reproduce=1
benchmarks_csv=""
default_benchmarks=(mbedtls libgcrypt openssl bearssl)
selected_benchmarks=("${default_benchmarks[@]}")

usage() {
    cat <<'EOF'
Usage: $0 [--sym-size <n>] [--jump-enum <n>] [--sse-depth <n>] <max_time_seconds>

  <max_time_seconds>   Required integer (timeout in seconds for BINSEC)
  --sym-size <n>       Optional integer, default: 4
  --jump-enum <n>      Optional integer, default: 10
  --sse-depth <n>      Optional integer, default: 1000000000
  --fml-solver <name>  Optional SMT backend for BINSEC, default: z3
  --smt-solver <name>  Optional SMT solver command for BINSEC, default: z3
  --patch-memset-ifunc Optional, pin `memset_func`'s PLT/GOT slot to a concrete memset impl
  --benchmarks <list>  Optional comma-separated benchmark groups to run
        valid: mbedtls,libgcrypt,openssl,bearssl
  default: all valid groups
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
        --fml-solver)
            binsec_fml_solver="${2:-}"; shift 2 ;;
        --smt-solver)
            binsec_smt_solver="${2:-}"; shift 2 ;;
        --patch-memset-ifunc)
            patch_memset_ifunc=1; shift ;;
        --benchmarks)
            benchmarks_csv="${2:-}"; shift 2 ;;
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

if [[ -z "$binsec_fml_solver" ]]; then
    echo "Error: fml solver name must be non-empty (got '$binsec_fml_solver')" >&2
    exit 1
fi

if [[ -z "$binsec_smt_solver" ]]; then
    echo "Error: smt solver name must be non-empty (got '$binsec_smt_solver')" >&2
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

echo "##########"
echo "Args:"
echo "max_time=$max_time"
echo "sym_size=$sym_size"
echo "jump_enum=$jump_enum"
echo "sse_depth=$sse_depth"
echo "binsec_fml_solver=$binsec_fml_solver"
echo "binsec_smt_solver=$binsec_smt_solver"
echo "patch_memset_ifunc=$patch_memset_ifunc"
echo "benchmarks=$(IFS=','; echo "${selected_benchmarks[*]}")"
echo "##########"

results_dir="$repo_root/results/binsec_results"
rm -rf "$results_dir"
mkdir -p "$results_dir"
exec > >(tee -a "$results_dir/output.log") 2>&1

code_path_for_executable() {
    local exe="$1"
    case "$exe" in
        benchmarks/mbedtls-3.2.1/*)
            echo "benchmarks/mbedtls-3.2.1"
            ;;
        benchmarks/libgcrypt-and-libgpg-error/*)
            echo "benchmarks/libgcrypt-and-libgpg-error"
            ;;
        benchmarks/openssl-1.1.1q/*)
            echo "benchmarks/openssl-1.1.1q"
            ;;
        benchmarks/bearssl/*)
            echo "benchmarks/bearssl"
            ;;
        *)
            echo ""
            ;;
    esac
}

library_for_executable() {
    local exe="$1"
    case "$exe" in
        benchmarks/mbedtls-3.2.1/*)
            echo "mbedtls"
            ;;
        benchmarks/libgcrypt-and-libgpg-error/*)
            echo "libgcrypt"
            ;;
        benchmarks/openssl-1.1.1q/*)
            echo "openssl"
            ;;
        benchmarks/bearssl/*)
            echo "bearssl"
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
    shift 2
    local converter_args=("$@")

    if [[ ! -f "$results_dir/$stats_file" ]]; then
        echo "Warning: missing stats file $results_dir/$stats_file; skipping JSON conversion" >&2
        return 0
    fi
    if [[ ! -f "$results_dir/output.log" ]]; then
        echo "Warning: missing $results_dir/output.log; skipping JSON conversion" >&2
        return 0
    fi
    if ! "$python_bin" -c "import ${converter_module}" >/dev/null 2>&1; then
        echo "Warning: missing converter module: $converter_module; skipping JSON conversion" >&2
        return 0
    fi
    if [[ -z "$python_bin" ]]; then
        echo "Error: python3 not found; cannot run JSON conversion" >&2
        return 1
    fi

    local out_json="$results_dir/${stats_file%.toml}.json"
    local code_path
    local library
    code_path="$(code_path_for_executable "$executable")"
    library="$(library_for_executable "$executable")"
    if [[ -z "$library" ]]; then
        echo "Error: cannot infer library for executable '$executable'" >&2
        return 2
    fi

    echo "-----"
    echo "Converting $results_dir/$stats_file -> $out_json"
    echo "-----"

    local cmd=(
        "$python_bin" -m "$converter_module"
        --toml "$results_dir/$stats_file"
        --output-log "$results_dir/output.log"
        --executable "$executable"
        --library "$library"
        --sym-size "$sym_size"
        --out "$out_json"
    )
    if [[ -n "$code_path" ]]; then
        cmd+=(--code-path "$code_path")
    fi
    if [[ "${#converter_args[@]}" -gt 0 ]]; then
        cmd+=("${converter_args[@]}")
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
    shift 4
    local converter_args=("$@")

    local sse_script_to_use="$sse_script"
    local cfg_stem
    cfg_stem="$(basename "${sse_script%.cfg}")"

    if [[ "$patch_memset_ifunc" -eq 1 ]]; then
        local patcher_py="$repo_root/tools/converters/binsec_patch_memset_ifunc.py"
        if [[ -f "$patcher_py" && -n "$python_bin" ]]; then
            local out_cfg="$results_dir/patched_memset_${cfg_stem}_$(basename "$executable").cfg"
            "$python_bin" "$patcher_py" \
                --exe "$executable" \
                --base-cfg "$sse_script_to_use" \
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
        -fml-solver "$binsec_fml_solver" \
        -smt-solver "$binsec_smt_solver" \
        -sse-timeout "$max_time" \
        -sse-jump-enum "$jump_enum" \
        -sse-script "$sse_script_to_use" \
        -sse-depth "$sse_depth" \
        -sse-heuristics nurs \
        -checkct-features control-flow,memory-access \
        -checkct-stats-file "$results_dir/$stats_file" \
        "$executable"

    convert_case_to_json "$stats_file" "$executable" "${converter_args[@]}"
}

_BUILT_MBEDTLS=0
_BUILT_LIBGCRYPT=0
_BUILT_OPENSSL=0
_BUILT_BEARSSL=0

ensure_built_mbedtls() {
    if [[ "$_BUILT_MBEDTLS" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for Mbed TLS 3.2.1"
    echo "##########"
    benchmarks/mbedtls-3.2.1/build.sh --binsec --preset "size_${sym_size}"
    _BUILT_MBEDTLS=1
}

ensure_built_libgcrypt() {
    if [[ "$_BUILT_LIBGCRYPT" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for Libgcrypt 1.10.1"
    echo "##########"
    benchmarks/libgcrypt-and-libgpg-error/build.sh --binsec --preset "size_${sym_size}"
    _BUILT_LIBGCRYPT=1
}

ensure_built_openssl() {
    if [[ "$_BUILT_OPENSSL" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for OpenSSL 1.1.1q"
    echo "##########"
    benchmarks/openssl-1.1.1q/build.sh --binsec --preset "size_${sym_size}"
    _BUILT_OPENSSL=1
}

ensure_built_bearssl() {
    if [[ "$_BUILT_BEARSSL" -eq 1 ]]; then
        return 0
    fi
    echo "##########"
    echo "Begin experiments for BearSSL 0.6"
    echo "##########"
    benchmarks/bearssl/build.sh --binsec --preset default
    _BUILT_BEARSSL=1
}

run_mbedtls_case() {
    local kind="$1"  # fix_pub | var_pub
    ensure_built_mbedtls
    case "$kind" in
        fix_pub)
            run_case "Mbed TLS 3.2.1 (Fix Pub)" "$repo_root/benchmarks/mbedtls-3.2.1/generated/binsec_fix_pub.cfg" "mbedtls_fix_pub.toml" "benchmarks/mbedtls-3.2.1/binsec_fix_pub"
            ;;
        var_pub)
            run_case "Mbed TLS 3.2.1 (Var Pub)" "$repo_root/benchmarks/mbedtls-3.2.1/generated/binsec_var_pub.cfg" "mbedtls_var_pub.toml" "benchmarks/mbedtls-3.2.1/binsec_var_pub"
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
            run_case "Libgcrypt 1.10.1 (Fix Pub)" "$repo_root/benchmarks/libgcrypt-and-libgpg-error/generated/binsec_fix_pub.cfg" "libgcrypt_fix_pub.toml" "benchmarks/libgcrypt-and-libgpg-error/binsec_fix_pub"
            ;;
        var_pub)
            run_case "Libgcrypt 1.10.1 (Var Pub)" "$repo_root/benchmarks/libgcrypt-and-libgpg-error/generated/binsec_var_pub.cfg" "libgcrypt_var_pub.toml" "benchmarks/libgcrypt-and-libgpg-error/binsec_var_pub"
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
            run_case "OpenSSL 1.1.1q ${algo} (Fix Pub)" "$repo_root/benchmarks/openssl-1.1.1q/generated/binsec_fix_pub.cfg" "openssl_${algo}_fix_pub.toml" "benchmarks/openssl-1.1.1q/binsec_fix_pub_${algo}"
            ;;
        var_pub)
            run_case "OpenSSL 1.1.1q ${algo} (Var Pub)" "$repo_root/benchmarks/openssl-1.1.1q/generated/binsec_var_pub.cfg" "openssl_${algo}_var_pub.toml" "benchmarks/openssl-1.1.1q/binsec_var_pub_${algo}"
            ;;
        *)
            echo "Error: unknown openssl kind '$kind'" >&2
            return 2
            ;;
    esac
}

run_bearssl_case() {
    local target="$1"  # aes_big | des_tab
    ensure_built_bearssl
    case "$target" in
        aes_big)
            run_case "BearSSL 0.6 aes_big" "$repo_root/benchmarks/bearssl/generated/binsec_aes_big/binsec_fix_pub.cfg" "bearssl_aes_big.toml" "benchmarks/bearssl/binsec_fix_pub_binsec_aes_big" --secret-input "skey:48:skey_buf" --secret-input "data:32:data_buf"
            ;;
        des_tab)
            run_case "BearSSL 0.6 des_tab" "$repo_root/benchmarks/bearssl/generated/appliedcryp_des/binsec_fix_pub.cfg" "bearssl_des_tab.toml" "benchmarks/bearssl/binsec_fix_pub_appliedcryp_des" --secret-input "skey:256:skey_buf" --secret-input "data:16:data_buf"
            ;;
        *)
            echo "Error: unknown bearssl target '$target'" >&2
            return 2
            ;;
    esac
}

########################
# Cases (comment out any single line to skip)
########################

for benchmark in "${selected_benchmarks[@]}"; do
    case "$benchmark" in
        mbedtls)
            run_mbedtls_case fix_pub
            run_mbedtls_case var_pub
            ;;
        libgcrypt)
            run_libgcrypt_case fix_pub
            run_libgcrypt_case var_pub
            ;;
        openssl)
            run_openssl_case recp fix_pub
            run_openssl_case recp var_pub
            run_openssl_case mont fix_pub
            run_openssl_case mont var_pub
            run_openssl_case mont_consttime fix_pub
            run_openssl_case mont_consttime var_pub
            run_openssl_case mont_word fix_pub
            run_openssl_case mont_word var_pub
            ;;
        bearssl)
            run_bearssl_case aes_big
            run_bearssl_case des_tab
            ;;
    esac
done
