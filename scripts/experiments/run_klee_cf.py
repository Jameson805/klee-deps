#!/usr/bin/env python3

from __future__ import annotations

from scripts.experiments.run_klee_family import main_for_mode


def main(argv: list[str] | None = None) -> int:
    return main_for_mode("klee_cf", argv)


if __name__ == "__main__":
    raise SystemExit(main())
