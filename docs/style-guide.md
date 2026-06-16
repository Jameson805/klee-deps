# Repository Style Guide

This document is the source of truth for code and documentation style in this repository.

The repository-specific Copilot instructions in `.github/copilot-instructions.md` point here and restate the highest-priority rules.

## General Style

- Keep code and documentation pragmatic and direct.
- Prefer the smallest owning code path over broad edits.
- Keep benchmark identity explicit as `library_id` plus `variant_id`.
- Use explicit metadata files and structured fields instead of deriving semantics from filenames.
- Keep generated or edited source-like files newline-terminated.

## Python

- Put a concise module docstring at the top of public CLI modules and shared modules.
- Document public helper functions whose behavior is reused across modules or relied on by build scripts, runners, or postprocessing.
- Use absolute repository imports such as `scripts.experiments.common` or `tools.shared.experiment_registry`.
- Run repository Python entrypoints with `python -m ...` from the repository root.
- Shell wrappers and benchmark build scripts should also invoke repository Python modules with `python -m ...` instead of direct file paths.
- Use type hints on shared and public Python functions when the surrounding file already does.

## C++ And KLEE Changes

- For new or substantially changed C++ code, document important classes and functions that define behavior, invariants, or integration points.
- For modified KLEE code, add a short local overview near the modified area or in the owning file describing what changed and how it fits into the surrounding KLEE flow.
- Keep modified KLEE executor logic auditable. Do not hide solver, fork, constraint, and model interactions behind unnecessary helper layers.
- When changing KLEE state invariants, update every direct mutation path that can bypass the invariant before relying on it elsewhere.
- Do not add defensive checks that contradict an intended invariant. Enforce the invariant at the state-mutation boundary and let downstream code assume it.

## Architecture And Abstraction Rules

- Keep tool-specific parsing in the runner or converter that owns it.
- Do not move tool-specific behavior into shared code unless multiple tools genuinely reuse it.
- Prefer explicit data flow over clever abstractions.
- Long orchestration functions are acceptable when they are the clearest representation of the workflow.
- Do not introduce a helper, abstraction, option, statistic, or documentation term until there are at least two real call sites or a clear readability win at the current call site.
- Prefer one visible control-flow path over layers of named helpers when the behavior is local, especially in modified KLEE executor code.

## CLI And User-Facing Surfaces

- Keep CLI surfaces minimal.
- Add one user-facing option when one mode controls one coherent behavior.
- Avoid exposing tuning knobs until there is evidence that users need them.
- Keep option names, statistics, documentation labels, and implementation behavior synchronized in the same change.

## Documentation

- Document code sections whose behavior is hard to infer, easy to misuse, constrained by subtle pitfalls, or kept as temporary patches.
- Explain the reason for non-obvious designs and workarounds, not just the mechanical behavior.
- Give extra context around workspace isolation, replay behavior, metadata propagation, fairness of comparisons, and KLEE integration boundaries.
- Use short comments for local rationale and longer nearby documentation when future readers need control-flow or design context.
- Keep landing pages short and push detail into focused docs.

## Validation

- Use the narrowest relevant executable validation after edits.
- For KLEE-CF changes, prefer `cmake --build build/klee-cf --target klee -j4` from the repository root after activating the workspace.
- For repository Python entrypoints, validate with `python -m ...` from the repository root.
- Do not run repository Python modules by direct file path.

## AI-Assisted Editing Rules

- Treat this guide as an implementation constraint, not optional prose.
- Before editing, identify the smallest owning code path and keep the change local to that path.
- After the first working version, reread touched code specifically for over-abstraction, stale guards, misleading names, and documentation drift.