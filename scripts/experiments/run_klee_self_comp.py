#!/usr/bin/env python3
"""Thin CLI wrapper for the shared KLEE self-composition runner implementation."""

from __future__ import annotations

from scripts.experiments.common import CampaignTool
from scripts.experiments.run_klee_family import main_for_mode


CAMPAIGN_TOOL = CampaignTool(tool_id="klee_self_comp", module_name=__name__, case_parallel_arg="--max-parallel-cases")


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the shared KLEE-family runner in KLEE self-composition mode."""
    return main_for_mode("klee_self_comp", argv)


if __name__ == "__main__":
    raise SystemExit(main())
