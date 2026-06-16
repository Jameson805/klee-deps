# BINSEC Challenges And Lessons Learned

This document summarizes the main operational and semantic issues the repository has hit while using BINSEC across the benchmark set.

It is meant to complement `../tools/binsec.md`. The tool page explains how the repository runs BINSEC. This page explains what tends to go wrong, why it goes wrong, and what mitigations currently exist.

## Problem Classes

The major recurring BINSEC issues in this repository are:

1. External-call handling.
2. Dynamic-loader and glibc interaction.
3. Build-shape sensitivity.
4. Replay-versus-reporting mismatches.

## External Calls

The biggest recurring integration surface is external calls.

The current deep dive is preserved in `../notes/binsec-external-calls.md`.

The short version is:

- ordinary PLT-imported calls are the easiest case
- `.plt.got` cases are more awkward
- IFUNC- or loader-sensitive paths are poor fits for direct symbolic execution from `main`
- benchmark-local generated cfgs plus narrow stubs work better than trying to model a full userspace runtime

## Build Shape Matters

For this repository, BINSEC works best when the benchmark executable is shaped intentionally for symbolic execution rather than simply reusing whatever is convenient for the KLEE modes.

Important practical lessons include:

- keep the executable non-PIE
- preserve normal dynamic libc import boundaries where that gives clean hook points
- do not assume build flags that help another tool will also help BINSEC

These are repository-specific integration choices, not generic truths about all BINSEC uses.

## Loader And IFUNC Problems

When execution falls into dynamic-loader machinery, finalization code, or glibc IFUNC dispatch, the symbolic run often stops being about the crypto code under test.

The repository preference is therefore to keep BINSEC focused on the benchmark-relevant surface rather than treating full loader semantics as part of the analysis target.

## Replay Mismatch Cases

Replay is useful for checking and classifying positives, but it does not have the same semantics as BINSEC's per-instruction reporting.

The focused reproducer in `../notes/binsec-wrong-location-reproducer.md` shows the important mismatch:

- BINSEC can report a later insecure instruction using a model that already diverges earlier
- replay stops at the first concrete divergence
- a row can therefore replay as `location_mismatch` even when BINSEC correctly reported the later instruction as insecure

That is a semantic mismatch between two stages, not necessarily a replay bug.

## What Breaks First On New Benchmarks

When adding a new BINSEC-integrated benchmark, the first breakage is often one of:

- unresolved imports
- startup or teardown code that is outside the crypto logic of interest
- build flags that remove clean hook points
- replay layout assumptions that do not match the generated executable shape

## Practical Mitigation Pattern

The repository's working pattern is:

1. Start with a benchmark-local generated cfg and the shared BINSEC prelude.
2. Keep stubs small and purposeful.
3. Keep the executable shape friendly to direct symbolic execution.
4. Use focused reproducers when the issue is semantic rather than purely operational.

## Supporting Notes

- `../notes/binsec-external-calls.md`
- `../notes/binsec-wrong-location-reproducer.md`

Those notes stay useful as detailed records. This page is the shorter map of what they mean for day-to-day repository use.