#!/usr/bin/env python3
"""Thin CLI wrapper for the shared KLEE-Eager runner implementation."""

from __future__ import annotations

from scripts.experiments.common import CampaignTool
from scripts.experiments.run_klee_family import main_for_mode


CAMPAIGN_TOOL = CampaignTool(tool_id="klee_eager", module_name=__name__)


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the shared KLEE-family runner in KLEE-Eager mode."""
    return main_for_mode("klee_eager", argv)


if __name__ == "__main__":
    raise SystemExit(main())
