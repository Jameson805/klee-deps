#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import CampaignTool
from scripts.experiments.run_klee_family import main_for_mode


CAMPAIGN_TOOL = CampaignTool(tool_id="klee_eager", module_name=__name__)


def main(argv: list[str] | None = None) -> int:
    return main_for_mode("klee_eager", argv)


if __name__ == "__main__":
    raise SystemExit(main())
