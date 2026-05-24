#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

cat > "$tmpdir/canonicalizable.c" <<'EOF'
int canonicalizable(int *a, int n) {
        int i = 0;
        int sum = 0;

        while (i < n) {
                if (a[i] == 0) {
                        i++;
                        continue;
                }
                sum += a[i];
                i++;
        }

        return sum;
}
EOF

clang -O0 -Xclang -disable-O0-optnone -S -emit-llvm "$tmpdir/canonicalizable.c" -o "$tmpdir/canonicalizable.ll"
opt -S \
        -load ./build/libLoopLimiter.so \
        -load-pass-plugin=./build/libLoopLimiter.so \
        -passes='loop-simplify,loop-limiter,verify' \
        -max-iterations=5 \
        -break \
        "$tmpdir/canonicalizable.ll" \
        -o "$tmpdir/canonicalizable.instrumented.ll" \
        2> "$tmpdir/canonicalizable.err"

grep -Eq 'loop.exit.or.bound|loop.stay.and.not.bound' "$tmpdir/canonicalizable.instrumented.ll"
if grep -q 'falling back to klee_silent_exit' "$tmpdir/canonicalizable.err"; then
        echo 'canonicalizable loop unexpectedly fell back to klee_silent_exit' >&2
        exit 1
fi

cat > "$tmpdir/fallback.ll" <<'EOF'
define void @fallback_to_exit(i32 %n) {
entry:
    br label %header

header:
    %i = phi i32 [ 0, %entry ], [ %inc, %latch ]
    br label %body

body:
    %cmp = icmp sge i32 %i, %n
    br i1 %cmp, label %exit, label %latch

latch:
    %inc = add nsw i32 %i, 1
    br label %header

exit:
    ret void
}
EOF

opt -S \
        -load ./build/libLoopLimiter.so \
        -load-pass-plugin=./build/libLoopLimiter.so \
        -passes='loop-simplify,loop-limiter,verify' \
        -max-iterations=5 \
        -break \
        "$tmpdir/fallback.ll" \
        -o "$tmpdir/fallback.instrumented.ll" \
        2> "$tmpdir/fallback.err"

grep -q 'falling back to klee_silent_exit' "$tmpdir/fallback.err"
grep -q 'call void @klee_silent_exit(i32 1)' "$tmpdir/fallback.instrumented.ll"

echo 'loop-limiter tests passed'
