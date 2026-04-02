#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  parallel_klee_copies.sh [-t|--tmp-dir <dir>] [--clean-destination] <num_copies> <output_subdir> <destination_dir> -- <command> [args...]

Example:
  parallel_klee_copies.sh 3 results/klee_cf_results output -- ./scripts/experiments/run_klee_cf.sh
  parallel_klee_copies.sh --tmp-dir /var/tmp 3 results/klee_cf_results output -- ./scripts/experiments/run_klee_cf.sh
  parallel_klee_copies.sh --clean-destination 3 results/klee_cf_results output -- ./scripts/experiments/run_klee_cf.sh

Arguments:
  -t, --tmp-dir   Parent directory where temporary copies are created (default: /tmp).
  --clean-destination  Remove destination/<worker_index> before copying results.
  num_copies       Number of parallel copies/jobs to run.
  output_subdir    Path (inside each copy) to collect after command finishes.
  destination_dir  Folder where per-copy outputs are collected as destination_dir/0, /1, ...
  command          Command to execute in each copy root.
EOF
}

tmp_dir=/tmp
clean_destination=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--tmp-dir)
      if [[ $# -lt 2 ]]; then
        echo "error: missing value for $1" >&2
        usage
        exit 1
      fi
      tmp_dir=$2
      shift 2
      ;;
    --clean-destination)
      clean_destination=1
      shift
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 4 ]]; then
  usage
  exit 1
fi

num_copies=$1
output_subdir=$2
destination_dir=$3
shift 3

if [[ ${1:-} == "--" ]]; then
  shift
fi

if [[ $# -eq 0 ]]; then
  echo "error: missing command to run" >&2
  usage
  exit 1
fi

if ! [[ "$num_copies" =~ ^[1-9][0-9]*$ ]]; then
  echo "error: num_copies must be a positive integer" >&2
  exit 1
fi

command=("$@")

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace_root=$(cd -- "$script_dir/../.." && pwd)
destination_abs=$(mkdir -p -- "$destination_dir" && cd -- "$destination_dir" && pwd)
if [[ "$clean_destination" -eq 1 ]]; then
  rm -rf -- "$destination_abs"
  mkdir -p -- "$destination_abs"
fi
mkdir -p -- "$tmp_dir"

run_root=$(mktemp -d -p "$tmp_dir" "klee-deps-parallel.$(date +%Y%m%d-%H%M%S).$$.XXXXXX")
log_dir="$run_root/logs"
mkdir -p -- "$log_dir"

declare -a pids=()
overall_rc=0

collect_results() {
  local i copy_dir src dst logs_dst
  local stdout_src stderr_src status_src
  local stdout_dst stderr_dst status_dst
  local status_file rc

  overall_rc=0

  for ((i = 0; i < num_copies; i++)); do
    copy_dir="$run_root/copy-$i"
    if [[ ! -d "$copy_dir" ]]; then
      continue
    fi

    src="$copy_dir/$output_subdir"
    dst="$destination_abs/$i"

    logs_dst="$dst/_logs"
    mkdir -p -- "$dst"
    mkdir -p -- "$logs_dst"

    stdout_src="$log_dir/$i.stdout.log"
    stderr_src="$log_dir/$i.stderr.log"
    status_src="$log_dir/$i.status"
    stdout_dst="$logs_dst/stdout.log"
    stderr_dst="$logs_dst/stderr.log"
    status_dst="$logs_dst/status"

    if [[ -f "$stdout_src" ]]; then
      cp -a -- "$stdout_src" "$stdout_dst"
    fi
    if [[ -f "$stderr_src" ]]; then
      cp -a -- "$stderr_src" "$stderr_dst"
    fi
    if [[ -f "$status_src" ]]; then
      cp -a -- "$status_src" "$status_dst"
    fi

    if [[ -d "$src" ]]; then
      cp -a -- "$src/." "$dst/"
    else
      echo "warning: output path not found for copy $i: $output_subdir" >&2
    fi

    status_file="$log_dir/$i.status"
    rc=1
    if [[ -f "$status_file" ]]; then
      rc=$(<"$status_file")
    fi

    if [[ "$rc" -ne 0 ]]; then
      overall_rc=1
      echo "copy $i failed with exit code $rc" >&2
      echo "  stdout: $stdout_dst" >&2
      echo "  stderr: $stderr_dst" >&2
      echo "  status: $status_dst" >&2
    fi
  done
}

terminate_workers() {
  local pid

  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  for pid in "${pids[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
}

cleanup() {
  terminate_workers
  rm -rf -- "$run_root"
}

handle_interrupt() {
  echo "interrupted, stopping workers" >&2
  terminate_workers
  collect_results
  echo "collected partial outputs in: $destination_abs" >&2
  exit 130
}

trap cleanup EXIT
trap handle_interrupt INT TERM

for ((i = 0; i < num_copies; i++)); do
  copy_dir="$run_root/copy-$i"
  cp -a -- "$workspace_root/." "$copy_dir"
  echo "starting worker $i in: $copy_dir"

  (
    set +e
    cd -- "$copy_dir" || exit 1
    "${command[@]}" >"$log_dir/$i.stdout.log" 2>"$log_dir/$i.stderr.log"
    echo "$?" >"$log_dir/$i.status"
    exit 0
  ) &

  pids+=("$!")
done

for pid in "${pids[@]}"; do
  wait "$pid" || true
done

collect_results

if [[ "$overall_rc" -ne 0 ]]; then
  echo "one or more parallel runs failed" >&2
  exit "$overall_rc"
fi

echo "all runs completed successfully"
echo "collected outputs in: $destination_abs"
