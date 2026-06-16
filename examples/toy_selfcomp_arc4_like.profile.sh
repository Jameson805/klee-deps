#!/usr/bin/env bash
# Profiling helper for examples/toy_selfcomp_arc4_like.c
#
# This script captures:
# 1) self-comp compare-profile counters
# 2) cf baseline run log
# 3) optional self-comp callgrind hotspots
#
# Usage:
#   ./examples/toy_selfcomp_arc4_like.profile.sh
#
# Optional env:
#   OUT_BASE=/tmp/my_toy_profiles
#   DO_CALLGRIND=0

set -euo pipefail

ROOT_SELFCOMP="${ROOT_SELFCOMP:-/dkucc/home/yl925/klee-deps-self-comp-trace-overhead}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOY_SRC="$REPO_ROOT/examples/toy_selfcomp_arc4_like.c"
OUT_BASE="${OUT_BASE:-/tmp/toy_selfcomp_profiles}"
DO_CALLGRIND="${DO_CALLGRIND:-1}"

mkdir -p "$OUT_BASE"

cd "$ROOT_SELFCOMP"
source ./activate-workspace.sh

# Rebuild current self-comp binary so profile reflects latest instrumentation.
cmake --build build/klee-self-comp --target klee -- -j"$(nproc)"

run_klee() {
  local mode="$1"
  local bin="$2"
  local out="$OUT_BASE/$mode"

  rm -rf "$out"
  mkdir -p "$out"

  clang-16 "$TOY_SRC" -g -emit-llvm -O0 -Xclang -disable-O0-optnone -c \
    -I klee-self-comp/include -o "$out/toy.bc"

  timeout --foreground --signal=INT --kill-after=30s 10s "$bin" \
    --output-dir="$out/klee-out" \
    --kdalloc \
    --kdalloc-constants-size=1 \
    --kdalloc-globals-size=1 \
    --kdalloc-heap-size=1 \
    --kdalloc-stack-size=1 \
    --write-no-tests \
    --max-time=3900s \
    "$out/toy.bc" >"$out/klee.log" 2>&1 || true

  echo "=== $mode ==="
  grep -nE '^KLEE: expr-compare profile|^KLEE:   |^KLEE:     ' "$out/klee.log" || true
  tail -n 20 "$out/klee.log" || true
}

run_klee "selfcomp" "build/klee-self-comp/bin/klee"
run_klee "cf" "build/klee-cf/bin/klee"

if [[ "$DO_CALLGRIND" == "1" ]]; then
  out="$OUT_BASE/selfcomp_callgrind"
  rm -rf "$out"
  mkdir -p "$out"

  clang-16 "$TOY_SRC" -g -emit-llvm -O0 -Xclang -disable-O0-optnone -c \
    -I klee-self-comp/include -o "$out/toy.bc"

  timeout --foreground --signal=INT --kill-after=30s 10s \
    valgrind --tool=callgrind --trace-children=no \
    --callgrind-out-file="$out/callgrind.out" \
    build/klee-self-comp/bin/klee \
    --output-dir="$out/klee-out" \
    --kdalloc \
    --kdalloc-constants-size=1 \
    --kdalloc-globals-size=1 \
    --kdalloc-heap-size=1 \
    --kdalloc-stack-size=1 \
    --write-no-tests \
    --max-time=3900s \
    "$out/toy.bc" >"$out/klee.log" 2>&1 || true

  echo "=== selfcomp_callgrind ==="
  callgrind_annotate --auto=yes "$out/callgrind.out" | head -n 120 || true
fi

cat <<EOF

Done.
Artifacts under: $OUT_BASE
- selfcomp/klee.log
- cf/klee.log
- selfcomp_callgrind/callgrind.out (if DO_CALLGRIND=1)
EOF
