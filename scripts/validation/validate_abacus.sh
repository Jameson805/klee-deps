#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"

if ! command -v python >/dev/null 2>&1; then
    echo "python not found in PATH" >&2
    exit 1
fi

results_dir="results/abacus_results"
output_dir=""
timeout=300
sym_size_override=""
reproduce_module="tools.postprocess.reproduce_positives"
pin_root=""

usage() {
    cat <<'EOF'
Usage: validate_abacus.sh [options]

Options:
    --results-dir DIR        Input directory of raw Abacus JSON files (default: results/abacus_results)
    --output-dir DIR         Output directory for validated JSON files (default: <results-dir>, in-place overwrite)
  --sym-size N             Override sym size instead of reading it from each JSON file
  --timeout N              Replay timeout in seconds (default: 300)
    --pin-root PATH         Path to external Intel Pin kit (defaults to PIN_ROOT)
    --reproduce-module NAME Python module to run for reproduction (default: tools.postprocess.reproduce_positives)
  -h, --help               Show this help

Notes:
  - This script is intended to run on the host, outside the Abacus container.
    - It validates the JSON produced by scripts/experiments/run_abacus.sh using host-side klee_fix_pub_replay executables.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --results-dir)
            [[ $# -lt 2 ]] && echo "Missing value for --results-dir" >&2 && exit 1
            results_dir="$2"
            shift 2
            ;;
        --results-dir=*)
            results_dir="${1#--results-dir=}"
            shift
            ;;
        --output-dir)
            [[ $# -lt 2 ]] && echo "Missing value for --output-dir" >&2 && exit 1
            output_dir="$2"
            shift 2
            ;;
        --output-dir=*)
            output_dir="${1#--output-dir=}"
            shift
            ;;
        --sym-size)
            [[ $# -lt 2 ]] && echo "Missing value for --sym-size" >&2 && exit 1
            sym_size_override="$2"
            shift 2
            ;;
        --sym-size=*)
            sym_size_override="${1#--sym-size=}"
            shift
            ;;
        --timeout)
            [[ $# -lt 2 ]] && echo "Missing value for --timeout" >&2 && exit 1
            timeout="$2"
            shift 2
            ;;
        --timeout=*)
            timeout="${1#--timeout=}"
            shift
            ;;
        --pin-root)
            [[ $# -lt 2 ]] && echo "Missing value for --pin-root" >&2 && exit 1
            pin_root="$2"
            shift 2
            ;;
        --pin-root=*)
            pin_root="${1#--pin-root=}"
            shift
            ;;
        --reproduce-module)
            [[ $# -lt 2 ]] && echo "Missing value for --reproduce-module" >&2 && exit 1
            reproduce_module="$2"
            shift 2
            ;;
        --reproduce-module=*)
            reproduce_module="${1#--reproduce-module=}"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$output_dir" ]]; then
    output_dir="$results_dir"
fi

if [[ ! -d "$results_dir" ]]; then
    echo "results directory not found: $results_dir" >&2
    exit 1
fi

if ! python -c "import ${reproduce_module}" >/dev/null 2>&1; then
    echo "reproduce module not importable: $reproduce_module" >&2
    exit 1
fi

if ! [[ "$timeout" =~ ^[0-9]+$ ]]; then
    echo "Invalid --timeout value: $timeout" >&2
    exit 1
fi

if [[ -n "$sym_size_override" ]] && ! [[ "$sym_size_override" =~ ^[0-9]+$ ]]; then
    echo "Invalid --sym-size value: $sym_size_override" >&2
    exit 1
fi

mkdir -p "$output_dir"

resolve_replay_executable() {
    local json_name="$1"
    case "$json_name" in
        mbedtls.json)
            printf '%s\n' 'benchmarks/mbedtls-3.2.1/klee_fix_pub_replay'
            ;;
        libgcrypt.json)
            printf '%s\n' 'benchmarks/libgcrypt-and-libgpg-error/klee_fix_pub_replay'
            ;;
        openssl_recp.json)
            printf '%s\n' 'benchmarks/openssl-1.1.1q/klee_fix_pub_replay_recp'
            ;;
        openssl_mont.json)
            printf '%s\n' 'benchmarks/openssl-1.1.1q/klee_fix_pub_replay_mont'
            ;;
        openssl_mont_consttime.json)
            printf '%s\n' 'benchmarks/openssl-1.1.1q/klee_fix_pub_replay_mont_consttime'
            ;;
        openssl_mont_word.json)
            printf '%s\n' 'benchmarks/openssl-1.1.1q/klee_fix_pub_replay_mont_word'
            ;;
        bearssl_aes_big.json)
            printf '%s\n' 'benchmarks/bearssl/klee_fix_pub_replay_binsec_aes_big'
            ;;
        bearssl_des_tab.json)
            printf '%s\n' 'benchmarks/bearssl/klee_fix_pub_replay_appliedcryp_des'
            ;;
        *)
            return 1
            ;;
    esac
}

resolve_build_script() {
    local json_name="$1"
    case "$json_name" in
        mbedtls.json)
            printf '%s\n' 'benchmarks/mbedtls-3.2.1/build.sh'
            ;;
        libgcrypt.json)
            printf '%s\n' 'benchmarks/libgcrypt-and-libgpg-error/build.sh'
            ;;
        openssl_recp.json|openssl_mont.json|openssl_mont_consttime.json|openssl_mont_word.json)
            printf '%s\n' 'benchmarks/openssl-1.1.1q/build.sh'
            ;;
        bearssl_aes_big.json|bearssl_des_tab.json)
            printf '%s\n' 'benchmarks/bearssl/build.sh'
            ;;
        *)
            return 1
            ;;
    esac
}

resolve_library() {
    local json_name="$1"
    case "$json_name" in
        mbedtls.json)
            printf '%s\n' 'mbedtls'
            ;;
        libgcrypt.json)
            printf '%s\n' 'libgcrypt'
            ;;
        openssl_recp.json|openssl_mont.json|openssl_mont_consttime.json|openssl_mont_word.json)
            printf '%s\n' 'openssl'
            ;;
        bearssl_aes_big.json|bearssl_des_tab.json)
            printf '%s\n' 'bearssl'
            ;;
        *)
            return 1
            ;;
    esac
}

read_sym_size() {
    local json_file="$1"
    python - "$json_file" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    obj = json.load(f)

notes = obj.get('notes', {})
ref = notes.get('abacus_reference_secret', {})
sym_size = ref.get('sym_size')
if sym_size is None:
    sym_size = 1
print('' if sym_size is None else sym_size)
PY
}

json_has_counterexamples() {
    local json_file="$1"
    python - "$json_file" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    obj = json.load(f)

rows = obj.get('data') if isinstance(obj, dict) else obj
if not isinstance(rows, list) or len(rows) == 0:
    raise SystemExit(1)

for row in rows:
    if not isinstance(row, dict):
        continue
    cex = row.get('counterexamples')
    if isinstance(cex, dict) and any(
        isinstance(key, str) and (key.endswith('__prime') or key.endswith('_prime'))
        for key in cex
    ):
        raise SystemExit(0)

raise SystemExit(1)
PY
}

shopt -s nullglob
json_files=("$results_dir"/*.json)
shopt -u nullglob

if [[ ${#json_files[@]} -eq 0 ]]; then
    echo "No JSON files found in $results_dir" >&2
    exit 1
fi

for json_file in "${json_files[@]}"; do
    json_name="$(basename "$json_file")"
    replay_exe="$(resolve_replay_executable "$json_name")" || {
        echo "Skipping unsupported JSON file: $json_name" >&2
        continue
    }
    library="$(resolve_library "$json_name")" || {
        echo "Skipping JSON with unknown library mapping: $json_name" >&2
        continue
    }

    sym_size="$sym_size_override"
    if [[ -z "$sym_size" ]]; then
        sym_size="$(read_sym_size "$json_file")"
    fi
    if ! [[ "$sym_size" =~ ^[0-9]+$ ]]; then
        echo "Could not determine sym size for $json_name; use --sym-size to override." >&2
        exit 1
    fi

    if [[ ! -x "$replay_exe" ]]; then
        build_script="$(resolve_build_script "$json_name")" || {
            echo "Missing replay executable: $replay_exe" >&2
            echo "Could not resolve build script for $json_name" >&2
            exit 1
        }
        if [[ ! -x "$build_script" ]]; then
            echo "Missing replay executable: $replay_exe" >&2
            echo "Build script not found or not executable: $build_script" >&2
            exit 1
        fi

        echo "Replay executable not found: $replay_exe"
        if [[ "$json_name" == bearssl_aes_big.json || "$json_name" == bearssl_des_tab.json ]]; then
            echo "Building with $build_script --klee-cf --preset default"
            "$build_script" --klee-cf --preset default
        else
            echo "Building with $build_script --klee-cf --preset size_$sym_size"
            "$build_script" --klee-cf --preset "size_$sym_size"
        fi
    fi

    if [[ ! -x "$replay_exe" ]]; then
        echo "Missing replay executable after build attempt: $replay_exe" >&2
        exit 1
    fi

    output_json="$output_dir/$json_name"

    if ! json_has_counterexamples "$json_file"; then
        echo "Skipping empty JSON file: $json_name"
        input_abs="$(cd "$(dirname "$json_file")" && pwd)/$(basename "$json_file")"
        output_abs="$(cd "$(dirname "$output_json")" && pwd)/$(basename "$output_json")"
        if [[ "$input_abs" != "$output_abs" ]]; then
            cp "$json_file" "$output_json"
        fi
        continue
    fi

    echo "Validating $json_name with $replay_exe"
    cmd=(
        python -m "$reproduce_module"
        --abacus-json "$json_file"
        --output "$output_json"
        --executable "$replay_exe"
        --library "$library"
        --sym-size "$sym_size"
        --timeout "$timeout"
    )
    if [[ -n "$pin_root" ]]; then
        cmd+=(--pin-root "$pin_root")
    fi
    "${cmd[@]}"
done

echo "Validated Abacus outputs written to $output_dir"
