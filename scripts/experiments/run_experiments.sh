#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root"

runner="$repo_root/scripts/experiments/parallel_klee_copies.sh"
merge_json_module="tools.postprocess.merge_json_runs_by_experiment"
merge_results_module="tools.postprocess.merge_results"
num_copies=10
temp_dir="/datapool/theta-lin-experiments/tmp"
# output="/datapool/theta-lin-experiments/20260331"
# run_time="4h"
# run_time_seconds="14400"
output="/datapool/theta-lin-experiments/test_run"
run_time="1m"
run_time_seconds="60"
klee_root="/home/theta-lin/klee/build/bin"
postprocess_only=false

if [[ "${1:-}" == "--postprocess-only" ]]; then
	postprocess_only=true
	shift
fi

if [[ "$#" -ne 0 ]]; then
	echo "usage: $0 [--postprocess-only]" >&2
	exit 2
fi

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

	if ! python3 -c "import ${merge_json_module}" >/dev/null 2>&1; then
		echo "missing helper module: $merge_json_module" >&2
		return 1
	fi

	if ! python3 -c "import ${merge_results_module}" >/dev/null 2>&1; then
		echo "missing helper module: $merge_results_module" >&2
		return 1
	fi

	for idx in "${!run_outputs[@]}"; do
		local tag="${run_tags[$idx]}"
		local dst="${run_outputs[$idx]}"

		run_tagged "$tag MERGE JSON" \
			python3 -m "$merge_json_module" "$dst" || return 1
	done

	run_tagged "MERGE CSV ALL" \
		python3 -m "$merge_results_module" "$output" -o "$output/merged_results.csv" || return 1

	run_tagged "MERGE CSV SLICED" \
		python3 -m "$merge_results_module" "$output" --sliced -o "$output/sliced_merged_results.csv" || return 1
}

launch_run "KLEE CF Default 4" "results/klee_cf_results" "$output/klee_cf_default_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4
# launch_run "KLEE CF Default 16" "results/klee_cf_results" "$output/klee_cf_default_16" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 16
# launch_run "KLEE CF DFS 4" "results/klee_cf_results" "$output/klee_cf_dfs_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 --search dfs
# launch_run "KLEE CF DFS 16" "results/klee_cf_results" "$output/klee_cf_dfs_16" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 16 --search dfs
# launch_run "KLEE CF Rand Path DFS 4" "results/klee_cf_results" "$output/klee_cf_rand_path_dfs_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 --search random-path,dfs
# launch_run "KLEE CF Rand Path DFS 16" "results/klee_cf_results" "$output/klee_cf_rand_path_dfs_16" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 16 --search random-path,dfs

# launch_run "KLEE CF NO CONC 4" "results/klee_cf_results" "$output/klee_cf_no_conc_4" -- scripts/experiments/run_klee_cf.sh "$run_time" --sym-size 4 --concretize-on-solver-timeout false

launch_run "KLEE Eager Default 4" "results/klee_eager_results" "$output/klee_eager_default_4" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 4
# launch_run "KLEE Eager Default 16" "results/klee_eager_results" "$output/klee_eager_default_16" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 16
# launch_run "KLEE Eager DFS 4" "results/klee_eager_results" "$output/klee_eager_dfs_4" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 4 --search dfs
# launch_run "KLEE Eager DFS 16" "results/klee_eager_results" "$output/klee_eager_dfs_16" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 16 --search dfs
# launch_run "KLEE Eager Rand Path DFS 4" "results/klee_eager_results" "$output/klee_eager_rand_path_dfs_4" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 4 --search random-path,dfs
# launch_run "KLEE Eager Rand Path DFS 16" "results/klee_eager_results" "$output/klee_eager_rand_path_dfs_16" -- scripts/experiments/run_klee_eager.sh "$run_time" --sym-size 16 --search random-path,dfs

launch_run "Self Comp Default 4" "results/self_comp_results" "$output/self_comp_default_4" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --sym-size 4
# launch_run "Self Comp Default 16" "results/self_comp_results" "$output/self_comp_default_16" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --sym-size 16
# launch_run "Self Comp DFS 4" "results/self_comp_results" "$output/self_comp_dfs_4" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search dfs --sym-size 4
# launch_run "Self Comp DFS 16" "results/self_comp_results" "$output/self_comp_dfs_16" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search dfs --sym-size 16
# launch_run "Self Comp Rand Path DFS 4" "results/self_comp_results" "$output/self_comp_rand_path_dfs_4" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search random-path,dfs --sym-size 4
# launch_run "Self Comp Rand Path DFS 16" "results/self_comp_results" "$output/self_comp_rand_path_dfs_16" -- scripts/experiments/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search random-path,dfs --sym-size 16

launch_run "Binsec 4" "results/binsec_results" "$output/binsec_4" -- scripts/experiments/run_binsec.sh "$run_time_seconds" --sym-size 4
# launch_run "Binsec 16" "results/binsec_results" "$output/binsec_16" -- scripts/experiments/run_binsec.sh "$run_time_seconds" --sym-size 16

wait_all || exit 1

run_postprocess || exit 1
exit 0
