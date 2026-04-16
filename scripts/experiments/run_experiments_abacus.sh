#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"

if ! command -v python >/dev/null 2>&1; then
	echo "python not found in PATH" >&2
	exit 1
fi

runner="$repo_root/scripts/experiments/parallel_klee_copies.sh"
num_copies=10
temp_dir="/tmp"
output_base="$repo_root/results/abacus_experiments"
abacus_root=""
sym_sizes=(4 16)
merge_json_module="tools.postprocess.merge_json_runs_by_experiment"
benchmarks_abacus=""

usage() {
	cat <<'EOF'
Usage:
  run_experiments_abacus.sh --abacus-root <path> [options]

Options:
  --abacus-root PATH     Path to Abacus root inside the current container
  --num-copies N         Number of parallel workspace copies (default: 10)
  --tmp-dir DIR          Parent temp directory for workspace copies (default: /tmp)
  --output DIR           Destination root for collected outputs
  --sym-size N           Sym size to run (repeatable; default: 4 and 16)
  --benchmarks LIST      Comma-separated benchmark groups for run_abacus.sh
						 valid: mbedtls,libgcrypt,openssl,bearssl,constantine
  -h, --help             Show this help

Notes:
  - This script is designed to run inside one already-running Abacus container.
  - It does not create additional containers; parallelism comes from workspace copies only.
  - It parallelizes by making temporary copies of the current workspace and running
    scripts/experiments/run_abacus.sh in each copy using parallel_klee_copies.sh.
  - Collected output subdir is results/abacus_results under each worker destination.
  - This script runs experiments and merges per-size JSON (abacus_4, abacus_16).
  - Cross-size merge and validation are separate later steps.
EOF
}

run_tagged() {
	local tag=$1
	shift
	"$@" 2>&1 | sed -u "s/^/[$tag] /"
	return "${PIPESTATUS[0]}"
}

run_postprocess() {
	local sym dst tag

	if ! python -c "import ${merge_json_module}" >/dev/null 2>&1; then
		echo "missing helper module: $merge_json_module" >&2
		return 1
	fi

	for sym in "${sym_sizes[@]}"; do
		dst="$output_base/abacus_${sym}"
		tag="ABACUS SYM ${sym} MERGE JSON"
		run_tagged "$tag" python -m "$merge_json_module" "$dst" || return 1
	done
}

if [[ ! -x "$runner" ]]; then
	echo "missing or non-executable runner: $runner" >&2
	exit 1
fi

custom_sym_sizes=false
while [[ $# -gt 0 ]]; do
	case "$1" in
		--num-copies)
			[[ $# -lt 2 ]] && echo "Missing value for --num-copies" >&2 && exit 1
			num_copies="$2"
			shift 2
			;;
		--num-copies=*)
			num_copies="${1#--num-copies=}"
			shift
			;;
		--tmp-dir)
			[[ $# -lt 2 ]] && echo "Missing value for --tmp-dir" >&2 && exit 1
			temp_dir="$2"
			shift 2
			;;
		--tmp-dir=*)
			temp_dir="${1#--tmp-dir=}"
			shift
			;;
		--output)
			[[ $# -lt 2 ]] && echo "Missing value for --output" >&2 && exit 1
			output_base="$2"
			shift 2
			;;
		--output=*)
			output_base="${1#--output=}"
			shift
			;;
		--abacus-root)
			[[ $# -lt 2 ]] && echo "Missing value for --abacus-root" >&2 && exit 1
			abacus_root="$2"
			shift 2
			;;
		--abacus-root=*)
			abacus_root="${1#--abacus-root=}"
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
		--benchmarks)
			[[ $# -lt 2 ]] && echo "Missing value for --benchmarks" >&2 && exit 1
			benchmarks_abacus="$2"
			shift 2
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

if ! [[ "$num_copies" =~ ^[1-9][0-9]*$ ]]; then
	echo "Invalid --num-copies value: $num_copies" >&2
	exit 1
fi

if [[ "${#sym_sizes[@]}" -eq 0 ]]; then
	echo "At least one --sym-size is required" >&2
	exit 1
fi

for sym in "${sym_sizes[@]}"; do
	if ! [[ "$sym" =~ ^[0-9]+$ ]]; then
		echo "Invalid --sym-size value: $sym" >&2
		exit 1
	fi
done

if [[ -z "$abacus_root" ]]; then
	echo "Missing required option: --abacus-root" >&2
	usage
	exit 1
fi

if [[ ! -d "$abacus_root" ]]; then
	echo "abacus root path does not exist: $abacus_root" >&2
	exit 1
fi

mkdir -p "$output_base"

for sym in "${sym_sizes[@]}"; do
	dst="$output_base/abacus_${sym}"
	bench_args=()
	if [[ -n "$benchmarks_abacus" ]]; then
		bench_args+=(--benchmarks "$benchmarks_abacus")
	fi
	run_tagged "ABACUS SYM ${sym}" \
		"$runner" --tmp-dir "$temp_dir" --clean-destination "$num_copies" \
		"results/abacus_results" "$dst" -- \
		scripts/experiments/run_abacus.sh "$abacus_root" --sym-size "$sym" "${bench_args[@]}"
done

run_postprocess || exit 1

echo "All Abacus prototype runs completed."
echo "Collected Abacus output root: $output_base"
echo "Per-size merged JSON generated under: $output_base/abacus_<sym>"
echo "Run validation separately on merged results when needed."
