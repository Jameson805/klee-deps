"""Discover runner modules for the tools that benchmark descriptors expose.

Keeping this outside ``experiment_registry`` avoids mixing benchmark schema
parsing with dynamic runner-module loading.
"""

from __future__ import annotations

import importlib

from scripts.experiments.common import CampaignTool
from tools.shared.experiment_registry import supported_tool_ids


_CAMPAIGN_TOOLS_BY_ID: dict[str, CampaignTool] | None = None


def available_campaign_tools() -> dict[str, CampaignTool]:
    """Return discovered tools keyed by tool id.

    Discovery is derived from benchmark descriptors: if a benchmark exposes a
    tool id, this module expects to find ``scripts.experiments.run_<tool_id>``.
    """
    global _CAMPAIGN_TOOLS_BY_ID
    if _CAMPAIGN_TOOLS_BY_ID is None:
        _CAMPAIGN_TOOLS_BY_ID = _load_campaign_tools()
    return dict(_CAMPAIGN_TOOLS_BY_ID)


def campaign_tool(tool_id: str) -> CampaignTool:
    """Return one discovered campaign tool or raise a user-facing error."""
    tools = available_campaign_tools()
    try:
        return tools[tool_id]
    except KeyError as error:
        supported_tools = ", ".join(sorted(tools))
        raise ValueError(f"unknown campaign tool {tool_id!r}; expected one of {supported_tools}") from error


def _load_campaign_tools() -> dict[str, CampaignTool]:
    """Import each runner module referenced by the benchmark registry."""
    tools: dict[str, CampaignTool] = {}
    for tool_id in supported_tool_ids():
        module_name = f"scripts.experiments.run_{tool_id}"
        module = importlib.import_module(module_name)
        spec = getattr(module, "CAMPAIGN_TOOL", None)
        if spec is None:
            factory = getattr(module, "campaign_tool", None)
            if factory is None:
                spec = CampaignTool(tool_id=tool_id, module_name=module.__name__)
            else:
                spec = factory()
                if not isinstance(spec, CampaignTool):
                    raise TypeError(
                        f"{module.__name__}.campaign_tool() must return CampaignTool, got {type(spec).__name__}"
                    )
        elif not isinstance(spec, CampaignTool):
            raise TypeError(
                f"{module.__name__}.CAMPAIGN_TOOL must be CampaignTool, got {type(spec).__name__}"
            )
        if spec.tool_id != tool_id:
            raise ValueError(
                f"{module.__name__} campaign metadata reported tool_id {spec.tool_id!r}, expected {tool_id!r}"
            )
        tools[tool_id] = spec
    return tools
