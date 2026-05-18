#!/usr/bin/env python3
"""Thin CLI wrapper for the shared KLEE-CF runner implementation."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import CampaignTool
from scripts.experiments.run_klee_family import main_for_mode


CAMPAIGN_TOOL = CampaignTool(tool_id="klee_cf", module_name=__name__)


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the shared KLEE-family runner in KLEE-CF mode."""
    return main_for_mode("klee_cf", argv)


if __name__ == "__main__":
    raise SystemExit(main())
