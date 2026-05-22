"""Print manifest-resolved runtime fields for grouped tool records."""

from __future__ import annotations

import argparse
import shlex

from tools.shared.tool_artifacts import resolve_klee_tool_layout


def _shell_quote(value: str) -> str:
    return shlex.quote(value)


def main(argv: list[str] | None = None) -> int:
    """Resolve one grouped KLEE tool record for shell or CLI callers."""
    parser = argparse.ArgumentParser(description="Resolve grouped KLEE tool records from the build manifest.")
    parser.add_argument("--tool", required=True, help="KLEE tool id from the build manifest, for example klee-cf")
    parser.add_argument(
        "--field",
        choices=("binary", "include_dir", "runtime_lib_dir"),
        help="Print just one field instead of the full shell assignment block.",
    )
    parser.add_argument(
        "--format",
        choices=("plain", "shell"),
        default="plain",
        help="Output format when --field is omitted.",
    )
    args = parser.parse_args(argv)

    layout = resolve_klee_tool_layout(args.tool)
    values = {
        "binary": str(layout.binary),
        "include_dir": str(layout.include_dir),
        "runtime_lib_dir": str(layout.runtime_lib_dir),
    }

    if args.field is not None:
        print(values[args.field])
        return 0

    if args.format == "shell":
        print(f"KLEE_TOOL_ID={_shell_quote(layout.tool_id)}")
        print(f"KLEE_TOOL_BINARY={_shell_quote(values['binary'])}")
        print(f"KLEE_TOOL_INCLUDE_DIR={_shell_quote(values['include_dir'])}")
        print(f"KLEE_TOOL_RUNTIME_LIB_DIR={_shell_quote(values['runtime_lib_dir'])}")
        return 0

    for key in ("binary", "include_dir", "runtime_lib_dir"):
        print(f"{key}={values[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())