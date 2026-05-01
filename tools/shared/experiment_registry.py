"""Load generic benchmark metadata shared by experiment runners.

The registry owns only cross-tool facts such as benchmark ids, build metadata,
path inference, and supported runner ids. Tool-specific case tables remain in
`extra_config` and are parsed by the runner that actually executes them so the
shared layer does not grow a second schema language.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from scripts.experiments.common import (
    expect_array,
    expect_string,
    expect_table,
    optional_string,
    optional_string_list,
)


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
                    if key not in generic_fields
                },
            )
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


_BENCHMARK_DEFINITIONS, _BENCHMARKS_BY_ID, _BENCHMARK_IDS_BY_TOOL = _load_registry()