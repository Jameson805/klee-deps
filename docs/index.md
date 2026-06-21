# Documentation Index

This directory is the entrypoint for detailed repository documentation.

## Start Here

If you are new to the repository:

1. Read `../README.md` for build and activation.
2. Read `architecture/benchmark-pipeline.md` for the end-to-end flow.
3. Read `tools/binsec.md` or the KLEE tool page you plan to run.

## Reading Paths

If you want to run one tool:

- `tools/klee-cf.md`
- `tools/klee-eager.md`
- `tools/klee-self-comp.md`
- `tools/binsec.md`

If you want to understand how the repository is wired together:

- `architecture/benchmark-pipeline.md`
- `architecture/runner-config.md`
- `benchmarks/benchmark-inventory.md`
- `benchmarks/rsa-overview.md`
- `benchmarks/models/modexp.md`
- `benchmarks/models/constantine.md`
- `benchmarks/models/bounded.md`
- `benchmarks/models/abacus.md`
- `benchmarks/models/other.md`

If you want the implementation details behind a focused change or experiment:

- `notes/klee-cf-candidate-models.md`
- `notes/expr-compare-findings.md`
- `notes/binsec-external-calls.md`
- `notes/binsec-wrong-location-reproducer.md`
- `notes/true-ct-violations-new-libraries.md`

If you want operational lessons and failure modes from external tools:

- `experiences/binsec-challenges.md`

If you want toy inputs and local reproducers:

- `../examples/README.md`

If you want repository editing rules:

- `style-guide.md`

## Document Map

- `architecture/benchmark-pipeline.md`: benchmark descriptor to postprocessing pipeline, plus guidance for adding benchmarks and tools
- `architecture/runner-config.md`: runner-config schema, generated artifacts, and BINSEC cfg generation
- `benchmarks/benchmark-inventory.md`: implemented and planned benchmark families, selectors, and classification gaps
- `benchmarks/rsa-overview.md`: why RSA benchmarks are split into padding, primitive, and full decrypt layers
- `benchmarks/models/modexp.md`: modular-exponentiation input model, defaults, public modes, and backend mapping
- `benchmarks/models/constantine.md`: Constantine-style known-violation rows and reused BINSEC/Rel2 rows
- `benchmarks/models/bounded.md`: bounded verification rows from BINSEC/Rel2 and ABACUS constant-time-claim benchmarks
- `benchmarks/models/abacus.md`: ABACUS overlap models, differences, and compatibility guidance
- `benchmarks/models/other.md`: implemented targets whose primary source grouping is separate or ambiguous
- `tools/klee-cf.md`: KLEE-CF usage, implementation model, and focused example links
- `tools/klee-eager.md`: KLEE-Eager usage, runner surface, and eager-specific fallback notes
- `tools/klee-self-comp.md`: self-composition model, output limitations, and performance notes
- `tools/binsec.md`: repository-specific BINSEC build, run, conversion, and replay flow
- `experiences/binsec-challenges.md`: external-call limits, loader issues, replay mismatches, and mitigation patterns
- `notes/`: deeper writeups that support the high-level pages instead of replacing them
- `style-guide.md`: source of truth for repository code and documentation style