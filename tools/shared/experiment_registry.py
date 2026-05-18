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
from tools.shared.configuration_metadata import case_output_metadata


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
BENCHMARK_CONFIG_DIR = REPO_ROOT / "configs" / "benchmarks"


def _expect_string_list(table: dict[str, object], key: str, location: str) -> list[str]:
    values = expect_array(table.get(key), f"{location}.{key}")
    if not values:
        raise ValueError(f"{location}.{key} must not be empty")
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"{location}.{key} must contain only non-empty strings")
    return list(values)


def format_benchmark_selector(library_id: str, variant_id: str) -> str:
    """Render the canonical CLI selector for one benchmark variant."""
    return f"{library_id}:{variant_id}"


def parse_benchmark_selector(raw_value: str) -> tuple[str, str]:
    """Parse the ``LIBRARY:VARIANT`` selectors accepted by runner CLIs."""
    library_id, separator, variant_id = raw_value.partition(":")
    if not separator or not library_id or not variant_id:
        raise ValueError(
            f"invalid benchmark selector {raw_value!r}; expected LIBRARY:VARIANT"
        )
    return (library_id, variant_id)


def canonical_case_id(library_id: str, variant_id: str, target_id: str, config_id: str) -> str:
    """Build the stable machine-oriented id for one expanded case."""
    parts = [f"{library_id}_{variant_id}"]
    if target_id:
        parts.append(target_id)
    parts.append(config_id)
    return "_".join(parts)


def canonical_case_title(library_id: str, variant_id: str, target_id: str, config_id: str) -> str:
    """Build the stable human-readable title for one expanded case."""
    selector = format_benchmark_selector(library_id, variant_id)
    if target_id:
        return f"{selector} {target_id} ({config_id})"
    return f"{selector} ({config_id})"


def normalized_case_output_metadata(case_table: dict[str, object], location: str) -> dict[str, object]:
    """Validate runner-emitted case metadata with config-location context."""
    try:
        return case_output_metadata(case_table)
    except ValueError as error:
        raise ValueError(f"{location}: {error}") from error


@dataclass(frozen=True)
class BenchmarkBuildConfig:
    script: str
    tool_flag: str
    preset: str
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class BenchmarkRunnerProfile:
    config: str
    preset: str


@dataclass(frozen=True)
class BenchmarkDefinition:
    config_location: str
    library_id: str
    variant_id: str
    code_path: str
    path_prefixes: tuple[str, ...]
    tools: frozenset[str]
    builds: dict[str, BenchmarkBuildConfig]
    build_aliases: dict[str, str]
    runner_profiles: dict[str, BenchmarkRunnerProfile]
    extra_config: dict[str, object]


@dataclass(frozen=True)
class _ParsedVariant:
    variant_id: str
    tools: frozenset[str]
    build_extra_args: tuple[str, ...]
    overrides: dict[str, object]


def definition(library_id: str, variant_id: str) -> BenchmarkDefinition:
    """Return the parsed benchmark definition for one ``library:variant``."""
    try:
        return _BENCHMARKS_BY_IDENTITY[(library_id, variant_id)]
    except KeyError as error:
        raise ValueError(
            f"unknown benchmark {format_benchmark_selector(library_id, variant_id)!r}"
        ) from error


def build_for_tool(benchmark_definition: BenchmarkDefinition, tool_id: str) -> BenchmarkBuildConfig:
    """Resolve the benchmark build configuration for a given tool.

    Multiple tool ids may intentionally share one build key through the
    benchmark descriptor's ``build_aliases`` table.
    """
    if tool_id not in benchmark_definition.tools:
        raise ValueError(
            f"benchmark {format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id)!r} does not support tool {tool_id!r}"
        )
    build_id = benchmark_definition.build_aliases.get(tool_id, tool_id)
    try:
        return benchmark_definition.builds[build_id]
    except KeyError as error:
        raise ValueError(
            f"benchmark {format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id)!r} does not define build metadata for tool {tool_id!r}"
        ) from error


def runner_profile_for_definition(
    benchmark_definition: BenchmarkDefinition,
    profile_id: str | None = None,
) -> tuple[str, BenchmarkRunnerProfile]:
    """Resolve one benchmark-owned runner profile."""
    runner_profiles = benchmark_definition.runner_profiles
    if not runner_profiles:
        raise ValueError(
            f"benchmark {format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id)!r} does not define runner profiles"
        )

    if profile_id is None:
        if len(runner_profiles) == 1:
            resolved_profile_id = next(iter(runner_profiles))
            return resolved_profile_id, runner_profiles[resolved_profile_id]
        available_profiles = ", ".join(sorted(runner_profiles))
        raise ValueError(
            f"benchmark {format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id)!r} requires an explicit runner profile; expected one of {available_profiles}"
        )

    try:
        return profile_id, runner_profiles[profile_id]
    except KeyError as error:
        available_profiles = ", ".join(sorted(runner_profiles))
        raise ValueError(
            f"benchmark {format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id)!r} does not define runner profile {profile_id!r}; expected one of {available_profiles}"
        ) from error


def selected_benchmarks(tool_id: str, benchmark_csv: str | None) -> list[tuple[str, str]]:
    """Return selected ``(library_id, variant_id)`` pairs for one tool."""
    try:
        benchmark_selectors = list(_BENCHMARK_IDENTITIES_BY_TOOL[tool_id])
    except KeyError as error:
        supported_tools = ", ".join(sorted(_BENCHMARK_IDENTITIES_BY_TOOL))
        raise ValueError(f"unknown tool {tool_id!r}; expected one of {supported_tools}") from error
    if not benchmark_csv:
        return benchmark_selectors

    allowed = set(benchmark_selectors)
    selected: list[tuple[str, str]] = []
    for raw_value in benchmark_csv.split(","):
        benchmark_value = raw_value.strip()
        if not benchmark_value:
            continue
        selector = parse_benchmark_selector(benchmark_value)
        if selector not in allowed:
            raise ValueError(f"unknown benchmark '{benchmark_value}' for --benchmarks")
        selected.append(selector)
    if not selected:
        raise ValueError("--benchmarks provided but no valid benchmark names were parsed")
    return selected


def definition_for_path(path: str) -> BenchmarkDefinition | None:
    """Best-effort path-to-benchmark lookup used by converters and replay."""
    normalized_path = path.replace("\\", "/")
    for benchmark_definition in _BENCHMARK_DEFINITIONS:
        if any(prefix in normalized_path for prefix in benchmark_definition.path_prefixes):
            return benchmark_definition
    return None


def supported_tool_ids() -> tuple[str, ...]:
    """Return all tool ids exposed by the parsed benchmark descriptors."""
    return tuple(sorted(_BENCHMARK_IDENTITIES_BY_TOOL))


def _parse_build(build_id: str, raw_build: object, location: str) -> BenchmarkBuildConfig:
    if not build_id:
        raise ValueError(f"{location} contains an empty build key")
    build_table = expect_table(raw_build, location)
    return BenchmarkBuildConfig(
        script=expect_string(build_table, "script", location),
        tool_flag=expect_string(build_table, "tool_flag", location),
        preset=expect_string(build_table, "preset", location),
        extra_args=tuple(optional_string_list(build_table, "extra_args", location)),
    )


def _parse_builds(raw_builds: object, location: str) -> dict[str, BenchmarkBuildConfig]:
    if raw_builds is None:
        return {}
    builds_table = expect_table(raw_builds, f"{location}.builds")
    return {
        build_id: _parse_build(build_id, raw_build, f"{location}.builds.{build_id}")
        for build_id, raw_build in builds_table.items()
    }


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


def _parse_runner_profiles(
    raw_runner_profiles: object,
    location: str,
) -> dict[str, BenchmarkRunnerProfile]:
    if raw_runner_profiles is None:
        return {}

    profiles_table = expect_table(raw_runner_profiles, f"{location}.runner_profiles")
    profiles: dict[str, BenchmarkRunnerProfile] = {}
    for profile_id, raw_profile in profiles_table.items():
        profile_location = f"{location}.runner_profiles.{profile_id}"
        if not profile_id:
            raise ValueError(f"{location}.runner_profiles contains an empty profile key")
        profile_table = expect_table(raw_profile, profile_location)
        profiles[profile_id] = BenchmarkRunnerProfile(
            config=expect_string(profile_table, "config", profile_location),
            preset=expect_string(profile_table, "preset", profile_location),
        )
    return profiles


def _parse_variant(
    variant_id: str,
    raw_variant: object,
    location: str,
    default_tools: frozenset[str],
) -> _ParsedVariant:
    if not variant_id:
        raise ValueError(f"{location}.variants contains an empty variant key")

    variant_table = expect_table(raw_variant, location)
    raw_variant_tools = variant_table.get("tools")
    variant_tools = (
        frozenset(_expect_string_list(variant_table, "tools", location))
        if raw_variant_tools is not None
        else default_tools
    )
    invalid_tools = sorted(variant_tools - default_tools)
    if invalid_tools:
        raise ValueError(
            f"{location}.tools lists unsupported tools: {', '.join(invalid_tools)}"
        )

    return _ParsedVariant(
        variant_id=variant_id,
        tools=variant_tools,
        build_extra_args=tuple(optional_string_list(variant_table, "build_extra_args", location)),
        overrides={
            key: value
            for key, value in variant_table.items()
            if key not in {"tools", "build_extra_args"}
        },
    )


def _generated_definitions(
    definition_table: dict[str, object],
    location: str,
) -> list[BenchmarkDefinition]:
    library_id = expect_string(definition_table, "library", location)
    code_path = expect_string(definition_table, "code_path", location)
    path_prefixes = tuple(
        prefix.replace("\\", "/")
        for prefix in _expect_string_list(definition_table, "path_prefixes", location)
    )
    tools = frozenset(_expect_string_list(definition_table, "tools", location))
    builds = _parse_builds(definition_table.get("builds"), location)
    build_aliases = _parse_build_aliases(
        definition_table.get("build_aliases"),
        tools,
        builds,
        location,
    )
    runner_profiles = _parse_runner_profiles(definition_table.get("runner_profiles"), location)
    variants_table = expect_table(definition_table.get("variants"), f"{location}.variants")
    if not variants_table:
        raise ValueError(f"{location}.variants must not be empty")

    parsed_variants = [
        _parse_variant(variant_id, raw_variant, f"{location}.variants.{variant_id}", tools)
        for variant_id, raw_variant in variants_table.items()
    ]

    generic_fields = frozenset(
        {
            "library",
            "code_path",
            "path_prefixes",
            "tools",
            "builds",
            "build_aliases",
            "runner_profiles",
            "variants",
        }
    )

    definitions: list[BenchmarkDefinition] = []
    for parsed_variant in parsed_variants:
        variant_builds = {
            build_id: BenchmarkBuildConfig(
                script=build.script,
                tool_flag=build.tool_flag,
                preset=build.preset,
                extra_args=build.extra_args + parsed_variant.build_extra_args,
            )
            for build_id, build in builds.items()
        }
        merged_definition_table = dict(definition_table)
        merged_definition_table.update(parsed_variant.overrides)
        merged_extra_config = {
            key: value
            for key, value in merged_definition_table.items()
            if key not in generic_fields
        }
        definitions.append(
            BenchmarkDefinition(
                config_location=location,
                library_id=library_id,
                variant_id=parsed_variant.variant_id,
                code_path=code_path,
                path_prefixes=path_prefixes,
                tools=parsed_variant.tools,
                builds=variant_builds,
                build_aliases=build_aliases,
                runner_profiles=runner_profiles,
                extra_config=merged_extra_config,
            )
        )

    return definitions


def _load_registry() -> tuple[
    tuple[BenchmarkDefinition, ...],
    dict[tuple[str, str], BenchmarkDefinition],
    dict[str, tuple[tuple[str, str], ...]],
]:
    definitions: list[BenchmarkDefinition] = []
    identities_by_tool_lists: dict[str, list[tuple[str, str]]] = {}
    seen_identities: set[tuple[str, str]] = set()
    generic_fields = frozenset(
        {
            "library",
            "code_path",
            "path_prefixes",
            "tools",
            "builds",
            "build_aliases",
            "runner_profiles",
            "variants",
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
            if "variants" not in definition_table:
                raise ValueError(f"{location} must define variants")
            loaded_definitions = _generated_definitions(definition_table, location)
            for benchmark_definition in loaded_definitions:
                identity = (benchmark_definition.library_id, benchmark_definition.variant_id)
                if identity in seen_identities:
                    raise ValueError(
                        f"duplicate benchmark selector '{format_benchmark_selector(benchmark_definition.library_id, benchmark_definition.variant_id)}' in {config_path.relative_to(REPO_ROOT)}"
                    )
                definitions.append(benchmark_definition)
                seen_identities.add(identity)
                for tool_id in benchmark_definition.tools:
                    identities_by_tool_lists.setdefault(tool_id, []).append(identity)
    if not definitions:
        raise ValueError(f"no benchmark descriptors found in {BENCHMARK_CONFIG_DIR}")

    return (
        tuple(definitions),
        {
            (benchmark_definition.library_id, benchmark_definition.variant_id): benchmark_definition
            for benchmark_definition in definitions
        },
        {
            tool_id: tuple(identities_by_tool_lists[tool_id])
            for tool_id in sorted(identities_by_tool_lists)
        },
    )


_BENCHMARK_DEFINITIONS, _BENCHMARKS_BY_IDENTITY, _BENCHMARK_IDENTITIES_BY_TOOL = _load_registry()
