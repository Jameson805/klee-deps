"""Load generic benchmark metadata shared by experiment runners.

The registry owns only cross-tool facts such as benchmark ids, build metadata,
path inference, and supported runner ids. Tool-specific case tables remain in
`extra_config` and are parsed by the runner that actually executes them so the
shared layer does not grow a second schema language.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import tomllib

from scripts.experiments.common import (
    CampaignTool,
    expect_array,
    expect_string,
    expect_table,
    optional_string,
    optional_string_list,
)
from tools.shared.configuration_metadata import case_output_metadata


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
BENCHMARK_CONFIG_DIR = REPO_ROOT / "configs" / "benchmarks"


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def expect_string_list(table: dict[str, object], key: str, location: str) -> list[str]:
    values = expect_array(table.get(key), f"{location}.{key}")
    if not values:
        raise ValueError(f"{location}.{key} must not be empty")
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"{location}.{key} must contain only non-empty strings")
    return list(values)


def public_mode_label(public_mode: str) -> str:
    labels = {
        "fix_pub": "Fix Pub",
        "var_pub": "Var Pub",
        "var_pub_lim_loop_break": "Var Pub Lim Loop Break",
    }
    try:
        return labels[public_mode]
    except KeyError as error:
        raise ValueError(f"unsupported public mode {public_mode!r}") from error


def _expand_mode_cases(definition_table: dict[str, object], location: str) -> dict[str, object]:
    raw_mode_cases = definition_table.get("mode_cases")
    if raw_mode_cases is None:
        return {}

    templates = expect_table(
        definition_table.get("mode_case_templates"),
        f"{location}.mode_case_templates",
    )
    mode_cases = expect_array(raw_mode_cases, f"{location}.mode_cases")
    benchmark_display_name = expect_string(definition_table, "display_name", location)
    default_code_path = expect_string(definition_table, "code_path", location)

    expanded: dict[str, list[dict[str, object]]] = {
        "abacus_cases": [],
        "self_comp_cases": [],
        "binsec_cases": [],
        "klee_cases": [],
    }
    for index, raw_case in enumerate(mode_cases):
        case_location = f"{location}.mode_cases[{index}]"
        case_table = expect_table(raw_case, case_location)
        case_display_name = expect_string(case_table, "display_name", case_location)
        artifact_suffix = expect_string(case_table, "artifact_suffix", case_location)
        output_stem = expect_string(case_table, "output_stem", case_location)
        replay_opts = expect_string(case_table, "replay_opts", case_location)
        ct_json = expect_string(case_table, "ct_json", case_location)
        memory_flag = case_table.get("memory_flag")
        if not isinstance(memory_flag, bool):
            raise ValueError(f"{case_location}.memory_flag must be a boolean")

        public_modes = optional_string_list(case_table, "public_modes", case_location) or ["fix_pub", "var_pub"]
        abacus_modes = optional_string_list(case_table, "abacus_modes", case_location) or ["fix_pub"]
        code_path = optional_string(case_table, "code_path", case_location) or default_code_path
        secret_layout = optional_string(case_table, "secret_layout", case_location)
        public_layout = optional_string(case_table, "public_layout", case_location)
        secret_inputs = optional_string_list(case_table, "secret_inputs", case_location)
        public_inputs = optional_string_list(case_table, "public_inputs", case_location)
        runner_config = optional_string(case_table, "runner_config", case_location)
        preset_name = optional_string(case_table, "preset_name", case_location)

        for public_mode in public_modes:
            case_title = f"{benchmark_display_name} {case_display_name} ({public_mode_label(public_mode)})"
            shared_metadata = {
                "source_column_suffix": public_mode,
                "public_mode": public_mode,
                "sliced": False,
            }
            expanded["self_comp_cases"].append(
                {
                    "title": f"{case_title} Self-Comp",
                    "bitcode": expect_string(templates, "self_comp_bitcode", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    "result_name": f"{output_stem}_self_comp_{public_mode}",
                    "json_name": f"{output_stem}_{public_mode}.json",
                    "replay_executable": expect_string(templates, "self_comp_replay_executable", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    **shared_metadata,
                    **({"secret_layout": secret_layout} if secret_layout else {}),
                    **({"public_layout": public_layout} if public_layout else {}),
                }
            )
            expanded["binsec_cases"].append(
                {
                    "title": case_title,
                    "sse_script": expect_string(templates, "binsec_sse_script", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    "stats_file": f"{output_stem}_{public_mode}.toml",
                    "executable": expect_string(templates, "binsec_executable", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    **shared_metadata,
                    **({"secret_inputs": secret_inputs} if secret_inputs else {}),
                    **({"public_inputs": public_inputs} if public_inputs else {}),
                }
            )
            expanded["klee_cases"].append(
                {
                    "title": case_title,
                    "bitcode": expect_string(templates, "klee_bitcode", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    "result_name": f"{output_stem}_{public_mode}",
                    "replay_script": expect_string(templates, "klee_replay_script", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    "replay_opts": replay_opts,
                    "ct_json": ct_json,
                    "code_path": code_path,
                    "memory_flag": memory_flag,
                    **shared_metadata,
                }
            )

        for public_mode in abacus_modes:
            expanded["abacus_cases"].append(
                {
                    "executable": expect_string(templates, "abacus_executable", f"{location}.mode_case_templates").format(public_mode=public_mode, artifact_suffix=artifact_suffix),
                    "outfile": f"{output_stem}_{public_mode}.txt",
                    "source_column_suffix": public_mode,
                    "public_mode": public_mode,
                    "sliced": False,
                    **({"runner_config": runner_config} if runner_config else {}),
                    **({"preset_name": preset_name} if preset_name else {}),
                }
            )

    return expanded


def normalized_case_output_metadata(case_table: dict[str, object], location: str) -> dict[str, object]:
    try:
        return case_output_metadata(case_table)
    except ValueError as error:
        raise ValueError(f"{location}: {error}") from error


@dataclass(frozen=True)
class BenchmarkBuildConfig:
    script: str
    tool_flag: str
    preset: str = ""
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkDefinition:
    config_location: str
    benchmark_id: str
    display_name: str
    library_id: str
    code_path: str
    path_prefixes: tuple[str, ...]
    tools: frozenset[str]
    builds: dict[str, BenchmarkBuildConfig]
    build_aliases: dict[str, str]
    extra_config: dict[str, object]


def definition(benchmark_id: str) -> BenchmarkDefinition:
    try:
        return _BENCHMARKS_BY_ID[benchmark_id]
    except KeyError as error:
        raise ValueError(f"unknown benchmark {benchmark_id!r}") from error


def build_for_tool(benchmark_id: str, tool_id: str) -> BenchmarkBuildConfig:
    benchmark_definition = definition(benchmark_id)
    if tool_id not in benchmark_definition.tools:
        raise ValueError(f"benchmark {benchmark_id!r} does not support tool {tool_id!r}")
    build_id = benchmark_definition.build_aliases.get(tool_id, tool_id)
    try:
        return benchmark_definition.builds[build_id]
    except KeyError as error:
        raise ValueError(
            f"benchmark {benchmark_id!r} does not define build metadata for tool {tool_id!r}"
        ) from error


def selected_benchmarks(tool_id: str, benchmark_csv: str | None) -> list[str]:
    benchmark_ids = _benchmark_ids_for_tool(tool_id)
    if not benchmark_csv:
        return benchmark_ids

    allowed = set(benchmark_ids)
    selected: list[str] = []
    for raw_value in benchmark_csv.split(","):
        benchmark_id = raw_value.strip()
        if not benchmark_id:
            continue
        if benchmark_id not in allowed:
            raise ValueError(f"unknown benchmark '{benchmark_id}' for --benchmarks")
        selected.append(benchmark_id)
    if not selected:
        raise ValueError("--benchmarks provided but no valid benchmark names were parsed")
    return selected


def definition_for_path(path: str) -> BenchmarkDefinition | None:
    normalized_path = normalize_path(path)
    for benchmark_definition in _BENCHMARK_DEFINITIONS:
        if any(prefix in normalized_path for prefix in benchmark_definition.path_prefixes):
            return benchmark_definition
    return None


def available_campaign_tools() -> dict[str, CampaignTool]:
    global _CAMPAIGN_TOOLS_BY_ID
    if _CAMPAIGN_TOOLS_BY_ID is None:
        _CAMPAIGN_TOOLS_BY_ID = _load_campaign_tools()
    return dict(_CAMPAIGN_TOOLS_BY_ID)


def campaign_tool(tool_id: str) -> CampaignTool:
    tools = available_campaign_tools()
    try:
        return tools[tool_id]
    except KeyError as error:
        supported_tools = ", ".join(sorted(tools))
        raise ValueError(f"unknown campaign tool {tool_id!r}; expected one of {supported_tools}") from error


def _benchmark_ids_for_tool(tool_id: str) -> list[str]:
    try:
        return list(_BENCHMARK_IDS_BY_TOOL[tool_id])
    except KeyError as error:
        supported_tools = ", ".join(sorted(_BENCHMARK_IDS_BY_TOOL))
        raise ValueError(f"unknown tool {tool_id!r}; expected one of {supported_tools}") from error


def _parse_builds(raw_builds: object, location: str) -> dict[str, BenchmarkBuildConfig]:
    if raw_builds is None:
        return {}
    builds_table = expect_table(raw_builds, f"{location}.builds")
    builds: dict[str, BenchmarkBuildConfig] = {}
    for build_id, raw_build in builds_table.items():
        if not build_id:
            raise ValueError(f"{location}.builds contains an empty build key")
        build_table = expect_table(raw_build, f"{location}.builds.{build_id}")
        builds[build_id] = BenchmarkBuildConfig(
            script=expect_string(build_table, "script", f"{location}.builds.{build_id}"),
            tool_flag=expect_string(build_table, "tool_flag", f"{location}.builds.{build_id}"),
            preset=optional_string(build_table, "preset", f"{location}.builds.{build_id}") or "",
            extra_args=tuple(
                optional_string_list(build_table, "extra_args", f"{location}.builds.{build_id}")
            ),
        )
    return builds


def _parse_build_aliases(
    raw_build_aliases: object,
    tools: frozenset[str],
    builds: dict[str, BenchmarkBuildConfig],
    location: str,
) -> dict[str, str]:
    if raw_build_aliases is None:
        return {}
    aliases_table = expect_table(raw_build_aliases, f"{location}.build_aliases")
    aliases: dict[str, str] = {}
    for tool_id, raw_build_id in aliases_table.items():
        if tool_id not in tools:
            raise ValueError(f"{location}.build_aliases.{tool_id} is not listed in tools")
        if tool_id in builds:
            raise ValueError(
                f"{location}.build_aliases.{tool_id} is redundant because builds.{tool_id} already exists"
            )
        if not isinstance(raw_build_id, str) or not raw_build_id:
            raise ValueError(f"{location}.build_aliases.{tool_id} must be a non-empty string")
        if raw_build_id not in builds:
            raise ValueError(
                f"{location}.build_aliases.{tool_id} references unknown build {raw_build_id!r}"
            )
        aliases[tool_id] = raw_build_id
    return aliases


def _load_registry() -> tuple[
    tuple[BenchmarkDefinition, ...],
    dict[str, BenchmarkDefinition],
    dict[str, tuple[str, ...]],
]:
    definitions: list[BenchmarkDefinition] = []
    ids_by_tool_lists: dict[str, list[str]] = {}
    seen_ids: set[str] = set()
    generic_fields = frozenset(
        {
            "benchmark_id",
            "display_name",
            "library_id",
            "code_path",
            "path_prefixes",
            "tools",
            "builds",
            "build_aliases",
        }
    )
    for config_path in sorted(BENCHMARK_CONFIG_DIR.glob("*.toml")):
        with config_path.open("rb") as handle:
            raw_config = tomllib.load(handle)
        benchmarks = expect_array(
            raw_config.get("benchmarks"),
            f"{config_path.relative_to(REPO_ROOT)}.benchmarks",
        )
        for index, raw_definition in enumerate(benchmarks):
            location = f"{config_path.relative_to(REPO_ROOT)}.benchmarks[{index}]"
            definition_table = expect_table(raw_definition, location)
            benchmark_id = expect_string(definition_table, "benchmark_id", location)
            if benchmark_id in seen_ids:
                raise ValueError(
                    f"duplicate benchmark id '{benchmark_id}' in {config_path.relative_to(REPO_ROOT)}"
                )
            tools = frozenset(expect_string_list(definition_table, "tools", location))
            builds = _parse_builds(definition_table.get("builds"), location)
            benchmark_definition = BenchmarkDefinition(
                config_location=location,
                benchmark_id=benchmark_id,
                display_name=expect_string(definition_table, "display_name", location),
                library_id=expect_string(definition_table, "library_id", location),
                code_path=expect_string(definition_table, "code_path", location),
                path_prefixes=tuple(
                    normalize_path(prefix)
                    for prefix in expect_string_list(definition_table, "path_prefixes", location)
                ),
                tools=tools,
                builds=builds,
                build_aliases=_parse_build_aliases(
                    definition_table.get("build_aliases"),
                    tools,
                    builds,
                    location,
                ),
                # Preserve runner-specific raw tables verbatim so each runner
                # can validate only the sections it understands.
                extra_config={
                    key: value
                    for key, value in definition_table.items()
                    if key not in generic_fields and key not in {"mode_cases", "mode_case_templates"}
                },
            )
            benchmark_definition.extra_config.update(_expand_mode_cases(definition_table, location))
            definitions.append(benchmark_definition)
            seen_ids.add(benchmark_id)
            for tool_id in tools:
                ids_by_tool_lists.setdefault(tool_id, []).append(benchmark_id)
    if not definitions:
        raise ValueError(f"no benchmark descriptors found in {BENCHMARK_CONFIG_DIR}")

    return (
        tuple(definitions),
        {
            benchmark_definition.benchmark_id: benchmark_definition
            for benchmark_definition in definitions
        },
        {
            tool_id: tuple(ids_by_tool_lists[tool_id])
            for tool_id in sorted(ids_by_tool_lists)
        },
    )


def _load_campaign_tools() -> dict[str, CampaignTool]:
    tools: dict[str, CampaignTool] = {}
    for tool_id in sorted(_BENCHMARK_IDS_BY_TOOL):
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


_BENCHMARK_DEFINITIONS, _BENCHMARKS_BY_ID, _BENCHMARK_IDS_BY_TOOL = _load_registry()
_CAMPAIGN_TOOLS_BY_ID: dict[str, CampaignTool] | None = None
