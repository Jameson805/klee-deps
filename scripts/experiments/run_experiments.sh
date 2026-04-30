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
merge_json_module="tools.postprocess.merge_json_runs_by_experiment"
merge_results_module="tools.postprocess.merge_results"
apply_sliced_map_module="tools.postprocess.apply_sliced_map"
merge_csv_by_location_module="tools.postprocess.merge_csv_by_location"
filter_merged_results_module="tools.postprocess.filter_merged_results"
summarize_reproduction_status_module="tools.postprocess.summarize_reproduction_status"
num_copies=10
temp_dir="/datapool/theta-lin-experiments/tmp"
output="/datapool/theta-lin-experiments/20260404"
sliced_map_csv="$repo_root/configs/postprocess/sliced_map.csv"
filtered_locations_csv="$repo_root/configs/postprocess/filtered_locations.csv"
ideal_config_selection_csv="$repo_root/configs/postprocess/ideal_config_selection.csv"
by_library_output_prefix="filtered_reproduction_status_by_library"
run_time="4h"
run_time_seconds="14400"
# output="/datapool/theta-lin-experiments/test_run"
# run_time="1m"
# run_time_seconds="60"
klee_root="/home/theta-lin/klee/build/bin"
postprocess_only=false
benchmarks_all=""
benchmarks_cf=""
benchmarks_eager=""
benchmarks_self_comp=""
benchmarks_binsec=""

usage() {
		cat <<EOF >&2
Usage: $0 [options]

Options:
	--postprocess-only          Run only merge/postprocess steps
	--benchmarks <list>         Apply benchmark list to all tool runners unless overridden
	--benchmarks-cf <list>      Benchmark list for KLEE-CF runner
	--benchmarks-eager <list>   Benchmark list for KLEE-Eager runner
	--benchmarks-self-comp <list> Benchmark list for self-comp runner
	--benchmarks-binsec <list>  Benchmark list for BINSEC runner
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--postprocess-only)
			postprocess_only=true
			shift
			;;
		--benchmarks)
			benchmarks_all="$2"
			shift 2
			;;
		--benchmarks-cf)
			benchmarks_cf="$2"
			shift 2
			;;
		--benchmarks-eager)
			benchmarks_eager="$2"
			shift 2
			;;
		--benchmarks-self-comp)
			benchmarks_self_comp="$2"
			shift 2
			;;
		--benchmarks-binsec)
			benchmarks_binsec="$2"
			shift 2
			;;
		*)
			usage
			exit 2
			;;
	esac
done

if [[ -n "$benchmarks_all" ]]; then
	[[ -z "$benchmarks_cf" ]] && benchmarks_cf="$benchmarks_all"
	[[ -z "$benchmarks_eager" ]] && benchmarks_eager="$benchmarks_all"
	[[ -z "$benchmarks_self_comp" ]] && benchmarks_self_comp="$benchmarks_all"
	[[ -z "$benchmarks_binsec" ]] && benchmarks_binsec="$benchmarks_all"
fi

cf_bench_args=()
eager_bench_args=()
self_comp_bench_args=()
binsec_bench_args=()
[[ -n "$benchmarks_cf" ]] && cf_bench_args+=(--benchmarks "$benchmarks_cf")
[[ -n "$benchmarks_eager" ]] && eager_bench_args+=(--benchmarks "$benchmarks_eager")
[[ -n "$benchmarks_self_comp" ]] && self_comp_bench_args+=(--benchmarks "$benchmarks_self_comp")
[[ -n "$benchmarks_binsec" ]] && binsec_bench_args+=(--benchmarks "$benchmarks_binsec")

run_tagged() {
	local tag=$1
	shift

	"$@" 2>&1 | sed -u "s/^/[$tag] /"
	return "${PIPESTATUS[0]}"
}

declare -a run_pids=()
declare -a run_tags=()
declare -a run_outputs=()

register_run_target() {
	local tag=$1
	local dst=$2
	run_tags+=("$tag")
	run_outputs+=("$dst")
}

terminate_runs() {
	local pid

	for pid in "${run_pids[@]}"; do
		if kill -0 "$pid" 2>/dev/null; then
			kill "$pid" 2>/dev/null || true
		fi
	done

	for pid in "${run_pids[@]}"; do
		wait "$pid" 2>/dev/null || true
	done
}

handle_interrupt() {
	echo "interrupted, stopping experiment runs" >&2
	terminate_runs
	exit 130
}

trap handle_interrupt INT TERM

launch_run() {
	local tag=$1
	local src=$2
	local dst=$3
	shift
	shift
	shift
	register_run_target "$tag" "$dst"

	if $postprocess_only; then
		return 0
	fi

	run_tagged "$tag" \
		"$runner" --tmp-dir "$temp_dir" --clean-destination "$num_copies" \
		"$src" "$dst" "$@" &
	run_pids+=("$!")
}

wait_all() {
	if $postprocess_only; then
		return 0
	fi

	local pid
	local overall_rc=0

	for pid in "${run_pids[@]}"; do
		wait "$pid" || overall_rc=1
	done

	return "$overall_rc"
}

run_postprocess() {
	local idx

	if ! python -c "import ${merge_json_module}" >/dev/null 2>&1; then
		echo "missing helper module: $merge_json_module" >&2
		return 1
	fi

	if ! python -c "import ${merge_results_module}" >/dev/null 2>&1; then
		echo "missing helper module: $merge_results_module" >&2
		return 1
	fi

	if ! python -c "import ${apply_sliced_map_module}" >/dev/null 2>&1; then
		echo "missing helper module: $apply_sliced_map_module" >&2
		return 1
	fi

	if ! python -c "import ${merge_csv_by_location_module}" >/dev/null 2>&1; then
		echo "missing helper module: $merge_csv_by_location_module" >&2
		return 1
	fi

	if ! python -c "import ${filter_merged_results_module}" >/dev/null 2>&1; then
		echo "missing helper module: $filter_merged_results_module" >&2
		return 1
	fi

	if ! python -c "import ${summarize_reproduction_status_module}" >/dev/null 2>&1; then
		echo "missing helper module: $summarize_reproduction_status_module" >&2
		return 1
	fi

	if [[ ! -f "$sliced_map_csv" ]]; then
		echo "missing sliced map CSV: $sliced_map_csv" >&2
		return 1
	fi

	if [[ ! -f "$filtered_locations_csv" ]]; then
		echo "missing filtered locations CSV: $filtered_locations_csv" >&2
		return 1
	fi

	if [[ ! -f "$ideal_config_selection_csv" ]]; then
		echo "missing ideal config selection CSV: $ideal_config_selection_csv" >&2
		return 1
	fi

	for idx in "${!run_outputs[@]}"; do
		local tag="${run_tags[$idx]}"
		local dst="${run_outputs[$idx]}"

		run_tagged "$tag MERGE JSON" \
			python -m "$merge_json_module" "$dst" || return 1
	done

	run_tagged "MERGE CSV ALL" \
		python -m "$merge_results_module" "$output" -o "$output/merged_results.csv" || return 1

	run_tagged "MERGE CSV SLICED" \
		python -m "$merge_results_module" "$output" --sliced -o "$output/sliced_merged_results.csv" || return 1

	run_tagged "RELABEL CSV SLICED" \
		python -m "$apply_sliced_map_module" \
		"$output/sliced_merged_results.csv" \
		--map "$sliced_map_csv" \
		--output "$output/sliced_relabeled_merged_results.csv" || return 1

	run_tagged "MERGE CSV ALL" \
		python -m "$merge_csv_by_location_module" \
		"$output/merged_results.csv" \
		"$output/sliced_relabeled_merged_results.csv" \
		-o "$output/all_merged_results.csv" || return 1

	run_tagged "FILTER CSV ALL" \
		python -m "$filter_merged_results_module" \
		"$output/all_merged_results.csv" \
		--filter "$filtered_locations_csv" \
		--output "$output/filtered_merged_results.csv" || return 1

	run_tagged "SUMMARY REPRO STATUS" \
		python -m "$summarize_reproduction_status_module" \
		"$output" \
		--filter "$filtered_locations_csv" \
		--sliced-map "$sliced_map_csv" \
		--selection-csv "$ideal_config_selection_csv" \
		--by-library-selection-tables \
		--by-library-output-prefix "$output/$by_library_output_prefix" \
		--output "$output/filtered_reproduction_status_summary.csv" || return 1
}

launch_run "KLEE CF Default 4" "results/klee_cf_results" "$output/klee_cf_default_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 "${cf_bench_args[@]}"
launch_run "KLEE CF Default 16" "results/klee_cf_results" "$output/klee_cf_default_16" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 16 "${cf_bench_args[@]}"
launch_run "KLEE CF DFS 4" "results/klee_cf_results" "$output/klee_cf_dfs_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 --search dfs "${cf_bench_args[@]}"
launch_run "KLEE CF DFS 16" "results/klee_cf_results" "$output/klee_cf_dfs_16" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 16 --search dfs "${cf_bench_args[@]}"
launch_run "KLEE CF Rand Path DFS 4" "results/klee_cf_results" "$output/klee_cf_rand_path_dfs_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 --search random-path,dfs "${cf_bench_args[@]}"
launch_run "KLEE CF Rand Path DFS 16" "results/klee_cf_results" "$output/klee_cf_rand_path_dfs_16" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 16 --search random-path,dfs "${cf_bench_args[@]}"

launch_run "KLEE CF NO CONC 4" "results/klee_cf_results" "$output/klee_cf_no_conc_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 --concretize-on-solver-timeout false "${cf_bench_args[@]}"

launch_run "KLEE Eager Default 4" "results/klee_eager_results" "$output/klee_eager_default_4" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 4 "${eager_bench_args[@]}"
launch_run "KLEE Eager Default 16" "results/klee_eager_results" "$output/klee_eager_default_16" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 16 "${eager_bench_args[@]}"
launch_run "KLEE Eager DFS 4" "results/klee_eager_results" "$output/klee_eager_dfs_4" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 4 --search dfs "${eager_bench_args[@]}"
launch_run "KLEE Eager DFS 16" "results/klee_eager_results" "$output/klee_eager_dfs_16" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 16 --search dfs "${eager_bench_args[@]}"
launch_run "KLEE Eager Rand Path DFS 4" "results/klee_eager_results" "$output/klee_eager_rand_path_dfs_4" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 4 --search random-path,dfs "${eager_bench_args[@]}"
launch_run "KLEE Eager Rand Path DFS 16" "results/klee_eager_results" "$output/klee_eager_rand_path_dfs_16" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 16 --search random-path,dfs "${eager_bench_args[@]}"

launch_run "Self Comp Default 4" "results/self_comp_results" "$output/self_comp_default_4" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --sym-size 4 "${self_comp_bench_args[@]}"
launch_run "Self Comp Default 16" "results/self_comp_results" "$output/self_comp_default_16" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --sym-size 16 "${self_comp_bench_args[@]}"
launch_run "Self Comp DFS 4" "results/self_comp_results" "$output/self_comp_dfs_4" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search dfs --sym-size 4 "${self_comp_bench_args[@]}"
launch_run "Self Comp DFS 16" "results/self_comp_results" "$output/self_comp_dfs_16" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search dfs --sym-size 16 "${self_comp_bench_args[@]}"
launch_run "Self Comp Rand Path DFS 4" "results/self_comp_results" "$output/self_comp_rand_path_dfs_4" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search random-path,dfs --sym-size 4 "${self_comp_bench_args[@]}"
launch_run "Self Comp Rand Path DFS 16" "results/self_comp_results" "$output/self_comp_rand_path_dfs_16" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search random-path,dfs --sym-size 16 "${self_comp_bench_args[@]}"

launch_run "Binsec 4" "results/binsec_results" "$output/binsec_4" -- scripts/experiments/run_binsec.sh "$run_time_seconds" --sym-size 4 "${binsec_bench_args[@]}"
launch_run "Binsec 16" "results/binsec_results" "$output/binsec_16" -- scripts/experiments/run_binsec.sh "$run_time_seconds" --sym-size 16 "${binsec_bench_args[@]}"

wait_all || exit 1

run_postprocess || exit 1
exit 0
