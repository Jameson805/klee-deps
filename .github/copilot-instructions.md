# Repository Instructions For Copilot

Before editing code or documentation in this repository, read and follow `docs/style-guide.md`. Treat it as an implementation constraint, not background context.

Read `docs/index.md` when you need the current documentation map.

Highest-priority rules:

- Keep changes pragmatic, direct, and local to the smallest owning code path.
- Prefer explicit data flow over clever abstractions. Do not introduce helpers, abstractions, options, statistics, or documentation terms unless there are at least two real call sites or a clear readability win at the current call site.
- Keep modified KLEE executor logic auditable. Avoid hiding solver, fork, constraint, and model interactions behind unnecessary helper layers.
- Do not add defensive checks that contradict an intended invariant. Enforce the invariant at the state-mutation boundary, document that boundary, and let downstream code assume it.
- Keep CLI surfaces minimal. Add one user-facing option for one coherent behavior, and avoid exposing tuning knobs without evidence that users need them.
- Keep option names, statistics, documentation labels, and implementation behavior synchronized in the same change.
- When changing KLEE state invariants, update every direct mutation path that can bypass the invariant before relying on it elsewhere.
- After the first working version, reread touched code for over-abstraction, stale guards, misleading names, and documentation drift before considering the change done.
- Repository Python entrypoints must use `python -m ...` from the repository root.
- Keep landing pages short and move detailed material into focused docs under `docs/`.

Validation expectations:

- Use the narrowest relevant executable validation after edits.
- For KLEE-CF changes, prefer `cmake --build build/klee-cf --target klee -j4` from the repository root after activating the workspace.
- For repository Python entrypoints, use `python -m ...` from the repository root. Do not run repository Python modules by direct file path.