#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$script_dir"

# Default output root from configs/experiments/run_experiments_abacus.toml
output_base="$repo_root/results/abacus_experiments"
sym_sizes=(4 16)
parallel=false
validate_runner="./validate_abacus.sh"

usage() {
    cat <<'EOF'
Usage: validate_experiments_abacus.sh [options]

Options:
    --output-base DIR      Output root containing abacus_<sym> directories (default: <repo>/results/abacus_experiments)
  --sym-size N           Sym size to validate (repeatable; default: 4 and 16)
  --parallel             Validate all selected sym sizes in parallel
  --sequential           Validate all selected sym sizes sequentially (default)
  -h, --help             Show this help

Notes:
  - This wrapper runs validate_abacus.sh for each selected abacus_<sym> directory.
  - Sequential mode is safer if host resources are limited.
EOF
}

custom_sym_sizes=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-base)
            [[ $# -lt 2 ]] && echo "Missing value for --output-base" >&2 && exit 1
            output_base="$2"
            shift 2
            ;;
        --output-base=*)
            output_base="${1#--output-base=}"
            shift
            ;;
        --sym-size)
            [[ $# -lt 2 ]] && echo "Missing value for --sym-size" >&2 && exit 1
            if ! $custom_sym_sizes; then
                sym_sizes=()
                custom_sym_sizes=true
            fi
            sym_sizes+=("$2")
            shift 2
            ;;
        --sym-size=*)
            if ! $custom_sym_sizes; then
                sym_sizes=()
                custom_sym_sizes=true
            fi
            sym_sizes+=("${1#--sym-size=}")
            shift
            ;;
        --parallel)
            parallel=true
            shift
            ;;
        --sequential)
            parallel=false
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

if [[ ! -x "$validate_runner" ]]; then
    echo "missing or non-executable validator: $validate_runner" >&2
    exit 1
fi

if [[ ! -d "$output_base" ]]; then
    echo "output base directory not found: $output_base" >&2
    exit 1
fi

if [[ ${#sym_sizes[@]} -eq 0 ]]; then
    echo "At least one --sym-size is required" >&2
    exit 1
fi

for sym in "${sym_sizes[@]}"; do
    if ! [[ "$sym" =~ ^[0-9]+$ ]]; then
        echo "Invalid --sym-size value: $sym" >&2
        exit 1
    fi

done

run_one() {
    local sym="$1"
    local results_dir="$output_base/abacus_${sym}"

    if [[ ! -d "$results_dir" ]]; then
        echo "Missing results directory: $results_dir" >&2
        return 1
    fi

    echo "[VALIDATE SYM ${sym}] validating $results_dir"
    "$validate_runner" --results-dir "$results_dir" --sym-size "$sym"
    echo "[VALIDATE SYM ${sym}] done"
}

if $parallel; then
    pids=()
    for sym in "${sym_sizes[@]}"; do
        run_one "$sym" &
        pids+=("$!")
    done

    for pid in "${pids[@]}"; do
        wait "$pid"
    done
else
    for sym in "${sym_sizes[@]}"; do
        run_one "$sym"
    done
fi

echo "All requested Abacus validations completed under: $output_base"
