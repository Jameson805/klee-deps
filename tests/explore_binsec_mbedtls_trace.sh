#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
benchmark_dir="$repo_root/benchmarks/mbedtls-3.2.1"
bignum_source="$benchmark_dir/library/bignum.c"

binsec_root="${BINSEC_ROOT:-/home/theta-lin/binsec}"
binsec_path=""
preset="size_4"
kind="var_pub"
timeout_seconds=60
jump_enum=10
sse_depth=1000000000000
fml_solver="z3"
smt_solver="z3"
skip_build=0
output_dir=""

usage() {
    cat <<EOF
Usage: $0 [options]

Exploratory helper that runs BINSEC checkct on Mbed TLS, scrapes the traced
instruction addresses from the BINSEC log, and reports DWARF-based coverage for
benchmarks/mbedtls-3.2.1/library/bignum.c.

Options:
  --preset NAME        Runner preset to build, default: size_4
  --kind KIND          One of: fix_pub, var_pub (default: var_pub)
  --timeout N          BINSEC -sse-timeout in seconds, default: 60
  --jump-enum N        BINSEC -sse-jump-enum value, default: 10
  --sse-depth N        BINSEC -sse-depth value, default: 1000000000000
  --fml-solver NAME    BINSEC formula solver, default: z3
  --smt-solver NAME    BINSEC SMT solver, default: z3
  --binsec PATH        Explicit BINSEC executable to run
  --binsec-root PATH   BINSEC checkout root, default: /home/theta-lin/binsec
  --skip-build         Reuse existing Mbed TLS BINSEC artifacts
  --out-dir PATH       Output directory, default: results/binsec_trace/<timestamp>
  -h, --help           Show this message

Notes:
  - Coverage is computed as unique bignum.c line numbers reached by traced
    instructions divided by the unique bignum.c line numbers present in the
    executable's DWARF decoded line table.
  - The script expects a BINSEC build that exposes the -checkct frontend.
EOF
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: required command not found: $1" >&2
        exit 1
    fi
}

resolve_existing_executable() {
    local candidate="$1"
    local resolved=""

    [[ -z "$candidate" ]] && return 1

    resolved="$(readlink -f "$candidate" 2>/dev/null || true)"
    if [[ -n "$resolved" && -x "$resolved" ]]; then
        printf '%s\n' "$resolved"
        return 0
    fi

    if [[ -x "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
    fi

    return 1
}

resolve_binsec_command() {
    local installed_bin
    local resolved=""
    local on_path=""

    if [[ -n "$binsec_path" ]]; then
        if resolved="$(resolve_existing_executable "$binsec_path")"; then
            binsec_cmd=("$resolved")
            return 0
        fi
        echo "Error: --binsec path is not executable: $binsec_path" >&2
        exit 1
    fi

    on_path="$(command -v binsec 2>/dev/null || true)"
    if [[ -n "$on_path" ]]; then
        binsec_cmd=("$on_path")
        return 0
    fi

    installed_bin="$binsec_root/_build/install/default/bin/binsec"
    if resolved="$(resolve_existing_executable "$installed_bin")"; then
        binsec_cmd=("$resolved")
        return 0
    fi

    if command -v dune >/dev/null 2>&1 && [[ -f "$binsec_root/dune-project" ]]; then
        binsec_cmd=(dune exec --root "$binsec_root" -- binsec)
        return 0
    fi

    echo "Error: unable to find a runnable BINSEC command." >&2
    echo "Tried: PATH, $installed_bin, and dune exec under $binsec_root." >&2
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --preset)
            preset="${2:-}"
            shift 2
            ;;
        --kind)
            kind="${2:-}"
            shift 2
            ;;
        --timeout)
            timeout_seconds="${2:-}"
            shift 2
            ;;
        --jump-enum)
            jump_enum="${2:-}"
            shift 2
            ;;
        --sse-depth)
            sse_depth="${2:-}"
            shift 2
            ;;
        --fml-solver)
            fml_solver="${2:-}"
            shift 2
            ;;
        --smt-solver)
            smt_solver="${2:-}"
            shift 2
            ;;
        --binsec)
            binsec_path="${2:-}"
            shift 2
            ;;
        --binsec-root)
            binsec_root="${2:-}"
            shift 2
            ;;
        --skip-build)
            skip_build=1
            shift
            ;;
        --out-dir)
            output_dir="${2:-}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

case "$kind" in
    fix_pub|var_pub)
        ;;
    *)
        echo "Error: --kind must be either fix_pub or var_pub (got '$kind')" >&2
        exit 1
        ;;
esac

for pair in "timeout_seconds:$timeout_seconds" "jump_enum:$jump_enum" "sse_depth:$sse_depth"; do
    name="${pair%%:*}"
    value="${pair##*:}"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "Error: $name must be a non-negative integer (got '$value')" >&2
        exit 1
    fi
done

if [[ -z "$output_dir" ]]; then
    run_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    output_dir="$repo_root/results/binsec_trace/mbedtls_${kind}_${preset}_${run_stamp}"
fi
mkdir -p "$output_dir"

require_cmd addr2line
require_cmd awk
require_cmd comm
require_cmd grep
require_cmd objdump
require_cmd sort
require_cmd tee
require_cmd xargs

resolve_binsec_command

set +e
binsec_help="$(${binsec_cmd[@]} -help 2>&1)"
binsec_help_status=$?
set -e
printf '%s\n' "$binsec_help" > "$output_dir/binsec_help_probe.log"
if [[ "$binsec_help_status" -ne 0 ]] || ! grep -q -- '-checkct' "$output_dir/binsec_help_probe.log"; then
    echo "Error: selected BINSEC command does not expose -checkct." >&2
    if grep -q 'The plugin "checkct" cannot be loaded' "$output_dir/binsec_help_probe.log"; then
        echo "Hint: the BINSEC checkout appears to have a broken checkct plugin install; clean/rebuild it or pass --binsec PATH to a working binary." >&2
    else
        echo "Hint: pass --binsec PATH to a BINSEC binary with checkct support, or rebuild the checkout under $binsec_root." >&2
    fi
    echo "Saved probe output to $output_dir/binsec_help_probe.log" >&2
    exit 1
fi

if [[ "$skip_build" -eq 0 ]]; then
    "$benchmark_dir/build.sh" --binsec --preset "$preset"
fi

case "$kind" in
    fix_pub)
        sse_script="$benchmark_dir/generated/binsec_fix_pub.cfg"
        executable="$benchmark_dir/binsec_fix_pub"
        ;;
    var_pub)
        sse_script="$benchmark_dir/generated/binsec_var_pub.cfg"
        executable="$benchmark_dir/binsec_var_pub"
        ;;
esac

if [[ ! -f "$sse_script" ]]; then
    echo "Error: missing BINSEC script: $sse_script" >&2
    exit 1
fi

if [[ ! -x "$executable" ]]; then
    echo "Error: missing BINSEC executable: $executable" >&2
    exit 1
fi

if [[ ! -f "$bignum_source" ]]; then
    echo "Error: missing source file: $bignum_source" >&2
    exit 1
fi

trace_log="$output_dir/binsec.trace.log"
stats_file="$output_dir/checkct_stats.toml"
visited_addrs="$output_dir/visited.addrs"
visited_addr2line="$output_dir/visited.addr2line"
visited_bignum_locations="$output_dir/visited.bignum.locations"
visited_bignum_lines="$output_dir/visited.bignum.lines"
all_bignum_lines="$output_dir/all.bignum.lines"
missing_bignum_lines="$output_dir/missing.bignum.lines"
report_file="$output_dir/coverage_summary.txt"

echo "Output directory: $output_dir"
echo "BINSEC command: ${binsec_cmd[*]}"
echo "Preset: $preset"
echo "Kind: $kind"
echo "Executable: $executable"
echo "SSE script: $sse_script"
echo "Tracing BINSEC execution..."

cd "$repo_root"
set +e
"${binsec_cmd[@]}" -sse -checkct \
    -fml-solver "$fml_solver" \
    -smt-solver "$smt_solver" \
    -sse-timeout "$timeout_seconds" \
    -sse-jump-enum "$jump_enum" \
    -sse-script "$sse_script" \
    -sse-depth "$sse_depth" \
    -sse-heuristics nurs \
    -checkct-features control-flow,memory-access \
    -checkct-stats-file "$stats_file" \
    -sse-no-screen \
    -sse-debug-level 2 \
    "$executable" 2>&1 | tee "$trace_log"
binsec_status=${PIPESTATUS[0]}
set -e

if [[ "$binsec_status" -ne 0 ]]; then
    echo "Error: BINSEC exited with status $binsec_status" >&2
    echo "Trace log retained at $trace_log" >&2
    exit "$binsec_status"
fi

LC_ALL=C awk '/^\[sse:[^]]+\] 0x[[:xdigit:]]+/ { print $2 }' "$trace_log" | sort -u > "$visited_addrs"
if [[ ! -s "$visited_addrs" ]]; then
    echo "Error: no traced instruction addresses were found in $trace_log" >&2
    echo "The parser expects -sse-debug-level 2 to emit instruction traces on an [sse:*] channel." >&2
    exit 1
fi

xargs -r -a "$visited_addrs" addr2line -e "$executable" -f -C -p | LC_ALL=C sort -u > "$visited_addr2line"

awk '/bignum\.c:[0-9]+/ { print $0 }' "$visited_addr2line" > "$visited_bignum_locations"
awk '
    /bignum\.c:[0-9]+/ {
        line = $0
        sub(/^.*bignum\.c:/, "", line)
        sub(/[^0-9].*$/, "", line)
        if (line ~ /^[0-9]+$/) {
            print line
        }
    }
' "$visited_addr2line" | LC_ALL=C sort -u > "$visited_bignum_lines"

objdump --dwarf=decodedline "$executable" | awk '$1 ~ /(^|\/)bignum\.c$/ && $2 ~ /^[0-9]+$/ { print $2 }' | LC_ALL=C sort -u > "$all_bignum_lines"
if [[ ! -s "$all_bignum_lines" ]]; then
    echo "Error: no DWARF line-table entries were found for bignum.c in $executable" >&2
    exit 1
fi

comm -23 "$all_bignum_lines" "$visited_bignum_lines" > "$missing_bignum_lines"

visited_addr_count="$(wc -l < "$visited_addrs" | tr -d '[:space:]')"
visited_line_count="$(wc -l < "$visited_bignum_lines" | tr -d '[:space:]')"
all_line_count="$(wc -l < "$all_bignum_lines" | tr -d '[:space:]')"
coverage_pct="$(awk -v visited="$visited_line_count" -v total="$all_line_count" 'BEGIN { if (total == 0) { printf "0.00" } else { printf "%.2f", (100.0 * visited) / total } }')"

{
    echo "Mbed TLS BINSEC trace coverage"
    echo "output_dir=$output_dir"
    echo "binsec_command=${binsec_cmd[*]}"
    echo "preset=$preset"
    echo "kind=$kind"
    echo "executable=$executable"
    echo "sse_script=$sse_script"
    echo "trace_log=$trace_log"
    echo "visited_addresses=$visited_addr_count"
    echo "visited_bignum_lines=$visited_line_count"
    echo "total_bignum_lines=$all_line_count"
    echo "coverage_percent=$coverage_pct"
    echo "visited_line_file=$visited_bignum_lines"
    echo "all_line_file=$all_bignum_lines"
    echo "missing_line_file=$missing_bignum_lines"
    echo "visited_location_file=$visited_bignum_locations"
} | tee "$report_file"

echo
echo "Coverage summary written to $report_file"
