# BINSEC Wrong-Location Reproducer

This note explains why BINSEC can report an insecure instruction whose replayed
counterexample diverges earlier at a different source location.

The standalone reproducer is:

- [example/toy_binsec_wrong_location.c](/dkucc/home/yl925/klee-deps/example/toy_binsec_wrong_location.c)
- [example/toy_binsec_wrong_location_var_pub.cfg](/dkucc/home/yl925/klee-deps/example/toy_binsec_wrong_location_var_pub.cfg)

## Reproduction

From the repo root:

```bash
source ./activate-workspace.sh

clang -O0 -g -fno-omit-frame-pointer -no-pie \
  example/toy_binsec_wrong_location.c \
  -o example/toy_binsec_wrong_location

clang -O0 -g -fno-omit-frame-pointer -no-pie -DREPLAY \
  example/toy_binsec_wrong_location.c \
  -o example/toy_binsec_wrong_location_replay

binsec -sse -checkct \
  -fml-solver z3 \
  -smt-solver z3 \
  -sse-timeout 60 \
  -sse-jump-enum 10 \
  -sse-script example/toy_binsec_wrong_location_var_pub.cfg \
  -sse-depth 1000000 \
  -sse-heuristics nurs \
  -checkct-features control-flow,memory-access \
  -checkct-stats-file /tmp/toy_binsec_wrong_location.toml \
  example/toy_binsec_wrong_location \
  2>&1 | tee /tmp/toy_binsec_wrong_location.log

python -m tools.converters.binsec_toml_to_json \
  --toml /tmp/toy_binsec_wrong_location.toml \
  --output-log /tmp/toy_binsec_wrong_location.log \
  --executable example/toy_binsec_wrong_location \
  --secret-input secret:4:secret_buf \
  --replay-executable example/toy_binsec_wrong_location_replay \
  --reproduce \
  --out /tmp/toy_binsec_wrong_location.json \
  --code-path example \
  --library unknown
```

Expected outcome:

- BINSEC reports two insecure memory instructions.
- The first one replays as `success`.
- The second one replays as `location_mismatch` and lands on the first one.

## What BINSEC Reports

The source has two distinct statements:

- [example/toy_binsec_wrong_location.c](/dkucc/home/yl925/klee-deps/example/toy_binsec_wrong_location.c#L99)
- [example/toy_binsec_wrong_location.c](/dkucc/home/yl925/klee-deps/example/toy_binsec_wrong_location.c#L100)

The corresponding load instructions are:

- `0x401136` for line 99
- `0x401153` for line 100

BINSEC reports both addresses as insecure in `/tmp/toy_binsec_wrong_location.toml`.

## Why Replay Lands Earlier

The important point is that BINSEC stores a separate insecurity model for each
reported instruction. Those models witness that the reported instruction is
insecure, but they do not require all earlier memory accesses to stay equal.

For the second reported instruction `0x401153`, BINSEC emits this witness pair:

- `secret1 = 0x222c3a7b`
- `secret2 = 0x00000000`

In the toy source, the two indices are:

- line 99: `secret_buf & 0x3`
- line 100: `(secret_buf + 1) & 0x3`

For that witness pair:

- line 99 indices are `3` and `0`
- line 100 indices are `0` and `1`

So the witness that proves line 100 insecure also already changes line 99.
When the replay engine runs the two concrete executions and compares traces, it
stops at the first actual divergence, which is the line 99 load. That is why
the replay result for the line 100 row is `location_mismatch`.

The same pattern holds for the line 99 witness too: its model also changes both
loads. BINSEC is not trying to synthesize a trace pair whose first divergence is
the reported instruction. It is only proving that the reported instruction can
observe secret-dependent behavior.

## Finding

This is not best explained as a replay bug. It is a semantic mismatch between:

- BINSEC `checkct`, which reports per-instruction insecurity models
- replay, which classifies by the first concrete divergence in the trace

So when BINSEC reports a later instruction inside a correlated block of secret-
dependent accesses, its model may still replay to an earlier instruction in the
same block. If the project wants `success` to mean "same statement", the replay
result should stay `location_mismatch` in that case.
