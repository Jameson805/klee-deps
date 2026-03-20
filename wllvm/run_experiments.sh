#!/usr/bin/env bash
cd "$(dirname "$0")"

runner="./parallel_klee_copies.sh"
merge_json_runner="./merge_json_runs_by_experiment.py"
merge_results_runner="./merge_results.py"
num_copies=10
temp_dir="/datapool/theta-lin-experiments/tmp"
output="/datapool/theta-lin-experiments/20260316"
run_time="2h"
run_time_seconds="7200"
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

	if [[ ! -f "$merge_json_runner" ]]; then
		echo "missing helper script: $merge_json_runner" >&2
		return 1
	fi

	if [[ ! -f "$merge_results_runner" ]]; then
		echo "missing helper script: $merge_results_runner" >&2
		return 1
	fi

	for idx in "${!run_outputs[@]}"; do
		local tag="${run_tags[$idx]}"
		local dst="${run_outputs[$idx]}"

		run_tagged "$tag MERGE JSON" \
			"$merge_json_runner" "$dst" || return 1
	done

	run_tagged "MERGE CSV ALL" \
		"$merge_results_runner" "$output" -o "$output/merged_results.csv" || return 1

	run_tagged "MERGE CSV SLICED" \
		"$merge_results_runner" "$output" --sliced -o "$output/sliced_merged_results.csv" || return 1
}
# launch_run "KLEE CF 4" "wllvm/klee_cf_results" "$output/klee_cf_4" -- wllvm/run_klee_cf.sh "$run_time" --sym-size 4
# launch_run "KLEE CF 16" "wllvm/klee_cf_results" "$output/klee_cf_16" -- wllvm/run_klee_cf.sh "$run_time" --sym-size 16
launch_run "KLEE Eager 4" "wllvm/klee_eager_results" "$output/klee_eager_4" -- wllvm/run_klee_eager.sh "$run_time" --sym-size 4
launch_run "KLEE Eager 16" "wllvm/klee_eager_results" "$output/klee_eager_16" -- wllvm/run_klee_eager.sh "$run_time" --sym-size 16
# launch_run "Self Comp 4" "wllvm/self_comp_results" "$output/self_comp_4" -- wllvm/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search dfs --sym-size 4
# launch_run "Self Comp 16" "wllvm/self_comp_results" "$output/self_comp_16" -- wllvm/run_self_comp.sh --klee-root "$klee_root" --max-time "$run_time" --search dfs --sym-size 16
# launch_run "Binsec 4" "wllvm/binsec_results" "$output/binsec_4" -- wllvm/run_binsec.sh "$run_time_seconds" --sym-size 4
# launch_run "Binsec 16" "wllvm/binsec_results" "$output/binsec_16" -- wllvm/run_binsec.sh "$run_time_seconds" --sym-size 16

wait_all || exit 1

run_postprocess || exit 1
exit 0
