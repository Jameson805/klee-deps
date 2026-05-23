#!/usr/bin/env python3
"""Build config-driven benchmarks through one shared entrypoint."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

from scripts.experiments.common import (
    REPO_ROOT,
    expect_array,
    expect_string,
    expect_table,
    optional_string,
    optional_string_list,
    resolve_repo_path,
)
from tools.shared.experiment_registry import definition, parse_benchmark_selector, runner_profile_for_definition
from tools.shared.tool_artifacts import resolve_klee_tool_layout


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _render(value: str, *, code_path: Path, target_id: str, output_target: str) -> str:
    return value.format(
        repo_root=str(REPO_ROOT),
        code_path=str(code_path),
        target=target_id,
        target_output=output_target,
    )


def _shell_run(command: str, *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(["bash", "-euo", "pipefail", "-c", command], cwd=cwd, env=env, check=True)


def _string_list(table: dict[str, object], key: str, location: str) -> tuple[str, ...]:
    return optional_string_list(table, key, location)


def _bool_value(table: dict[str, object], key: str, location: str, *, default: bool) -> bool:
    value = table.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{location}.{key} must be a boolean when present")
    return value


def _tool_mode(tool_id: str) -> str:
    if tool_id in {"klee", "klee_cf", "klee_eager", "klee_self_comp"}:
        return "klee"
    if tool_id in {"binsec", "abacus"}:
        return tool_id
    raise ValueError(f"unsupported build tool {tool_id!r}")


def _load_build_config(benchmark_definition) -> tuple[dict[str, object], list[dict[str, object]]]:
    location = benchmark_definition.config_location
    build = expect_table(
        benchmark_definition.extra_config.get("build"),
        f"{location}.build",
    )
    targets = expect_array(benchmark_definition.extra_config.get("targets"), f"{location}.targets")
    if not targets:
        raise ValueError(f"{location}.targets must not be empty")
    return build, [expect_table(raw_target, f"{location}.targets[{index}]") for index, raw_target in enumerate(targets)]


def _resolve_runner_config_path(benchmark_definition, target_table: dict[str, object], target_location: str) -> str:
    profile_id = optional_string(target_table, "runner_profile", target_location)
    _, profile = runner_profile_for_definition(benchmark_definition, profile_id)
    return str(resolve_repo_path(profile.config))


def _include_flags(include_dirs: tuple[str, ...], *, code_path: Path, target_id: str, output_target: str) -> list[str]:
    flags: list[str] = []
    for include_dir in include_dirs:
        flags.extend(["-I", _render(include_dir, code_path=code_path, target_id=target_id, output_target=output_target)])
    return flags


def _render_path_list(
    values: tuple[str, ...],
    *,
    code_path: Path,
    target_id: str,
    output_target: str,
) -> list[str]:
    return [
        _render(value, code_path=code_path, target_id=target_id, output_target=output_target)
        for value in values
    ]


def _output_target(target_id: str, variant_id: str) -> str:
    if variant_id == "default":
        return target_id
    return f"{target_id}_{variant_id}"


def _artifact_dir(code_path: Path, mode: str, output_target: str) -> Path:
    return code_path / "artifacts" / mode / output_target


def _tool_build_config(build_table: dict[str, object], mode: str, location: str) -> dict[str, object]:
    tools_table = expect_table(build_table.get("tools") or {}, f"{location}.tools")
    raw_mode_table = tools_table.get(mode)
    if raw_mode_table is None:
        return {}
    return expect_table(raw_mode_table, f"{location}.tools.{mode}")


def _run_shared_commands(
    commands: tuple[str, ...],
    *,
    cwd: Path,
    env: dict[str, str],
    variables: dict[str, str],
) -> None:
    for command in commands:
        _shell_run(command.format(**variables), cwd=cwd, env=env)


def _generate_runner_artifacts(
    benchmark_definition,
    *,
    target_table: dict[str, object],
    target_location: str,
    generated_dir: Path,
    preset: str | None,
    mode: str,
) -> None:
    command = [
        "python",
        "-m",
        "tools.generate_runner_artifacts",
        "--config",
        _resolve_runner_config_path(benchmark_definition, target_table, target_location),
        "--header-out",
        str(generated_dir / "runner_config.generated.h"),
    ]
    if preset:
        command.extend(["--preset", preset])
    if mode == "binsec":
        command.extend(
            [
                "--binsec-base",
                str(REPO_ROOT / "configs/binsec/binsec_base.cfg"),
                "--binsec-fix-pub-out",
                str(generated_dir / "binsec_fix_pub.cfg"),
                "--binsec-var-pub-out",
                str(generated_dir / "binsec_var_pub.cfg"),
            ]
        )
    generated_dir.mkdir(parents=True, exist_ok=True)
    _run(command, cwd=REPO_ROOT)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one benchmark through the shared config-driven builder.")
    parser.add_argument("--benchmark", required=True, help="Benchmark selector in LIBRARY:VARIANT form")
    parser.add_argument(
        "--tool",
        required=True,
        choices=["klee", "klee_cf", "klee_eager", "klee_self_comp", "binsec", "abacus"],
        help="Tool id requesting the build; KLEE-family tool ids share the KLEE build mode",
    )
    parser.add_argument("--preset", help="Optional preset name passed to runner artifact generation")
    parser.add_argument("--skip-deps", action="store_true", help="Skip benchmark dependency build hooks")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    library_id, variant_id = parse_benchmark_selector(args.benchmark)
    benchmark_definition = definition(library_id, variant_id)
    build_table, targets = _load_build_config(benchmark_definition)

    mode = _tool_mode(args.tool)
    code_path = resolve_repo_path(benchmark_definition.code_path)
    build_location = f"{benchmark_definition.config_location}.build"
    mode_build_table = _tool_build_config(build_table, mode, build_location)
    common_flags = list(_string_list(build_table, "common_flags", build_location))
    include_dirs = _string_list(build_table, "include_dirs", build_location)
    link_libraries = _string_list(build_table, "link_libraries", build_location)
    prepare_commands = _string_list(build_table, "prepare_commands", build_location)
    build_dep_commands = _string_list(build_table, "build_dep_commands", build_location)
    binsec_link_flags = _string_list(mode_build_table, "link_flags", f"{build_location}.tools.binsec")
    klee_link_flags = _string_list(mode_build_table, "link_flags", f"{build_location}.tools.klee")
    abacus_link_flags = _string_list(mode_build_table, "link_flags", f"{build_location}.tools.abacus")
    abacus_concrete_pubs = _bool_value(
        mode_build_table,
        "concrete_pubs",
        f"{build_location}.tools.abacus",
        default=False,
    )

    if mode == "klee" and not os.environ.get("LLVM_COMPILER") and shutil.which("wllvm"):
        os.environ["LLVM_COMPILER"] = "clang"

    noind_flags = ["-fno-pie", "-fno-plt", "-no-pie" if mode == "abacus" else "-Wl,-no-pie"]
    dep_cc = "clang"
    if mode == "abacus":
        dep_cc = "gcc"
    elif mode == "klee":
        dep_cc = "wllvm"

    dep_cflags = ["-g", "-O0"]
    dep_ldflags: list[str] = []
    if mode == "abacus":
        dep_cflags.append("-m32")
        dep_ldflags.append("-m32")
    dep_cflags.extend(["-fno-pie", "-fno-plt"])
    dep_ldflags.append("-no-pie" if mode == "abacus" else "-Wl,-no-pie")

    klee_layout = None
    if mode == "klee":
        tool_id = os.environ.get("KLEE_TOOL_ID", "klee-cf")
        klee_layout = resolve_klee_tool_layout(tool_id)

    shared_env = os.environ.copy()
    command_vars = {
        "repo_root": str(REPO_ROOT),
        "code_path": str(code_path),
        "mode": mode,
        "variant": variant_id,
        "preset": args.preset or "",
        "cc": dep_cc,
        "dep_cflags": " ".join(dep_cflags),
        "dep_ldflags": " ".join(dep_ldflags),
        "build_dir": str(code_path / "build"),
        "install_root": str((code_path / "build").resolve()),
        "openssl_arch": "linux-generic32" if mode == "abacus" else "linux-generic64",
        "libgcrypt_host": "--host=i686-pc-linux-gnu" if mode == "abacus" else "",
    }

    _run_shared_commands(prepare_commands, cwd=code_path, env=shared_env, variables=command_vars)
    if build_dep_commands and not args.skip_deps:
        _run_shared_commands(build_dep_commands, cwd=code_path, env=shared_env, variables=command_vars)

    built_targets = 0
    for index, target_table in enumerate(targets):
        target_location = f"{benchmark_definition.config_location}.targets[{index}]"
        target_id = expect_string(target_table, "target", target_location)
        output_target = _output_target(target_id, variant_id)
        generated_dir = code_path / "generated" / output_target
        sources = [
            _render(source, code_path=code_path, target_id=target_id, output_target=output_target)
            for source in _string_list(target_table, "build_sources", target_location)
        ]
        if not sources:
            raise ValueError(f"{target_location}.build_sources must not be empty")
        define_flags = [f"-D{define}" for define in _string_list(target_table, "defines", target_location)]
        rendered_link_libraries = _render_path_list(
            link_libraries,
            code_path=code_path,
            target_id=target_id,
            output_target=output_target,
        )

        print(f"Building {benchmark_definition.library_id} benchmark: {target_id}")
        _generate_runner_artifacts(
            benchmark_definition,
            target_table=target_table,
            target_location=target_location,
            generated_dir=generated_dir,
            preset=args.preset,
            mode=mode,
        )
        artifact_dir = _artifact_dir(code_path, mode, output_target)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        flags = [
            *common_flags,
            *_include_flags(include_dirs, code_path=code_path, target_id=target_id, output_target=output_target),
            "-I",
            str(generated_dir),
        ]

        if mode == "klee":
            assert klee_layout is not None
            klee_flags = [
                "-I",
                str(klee_layout.include_dir),
                "-L",
                str(klee_layout.runtime_lib_dir),
                f"-Wl,-rpath={klee_layout.runtime_lib_dir}",
                "-lkleeRuntest",
            ]
            var_exe = artifact_dir / "var_pub"
            fix_exe = artifact_dir / "fix_pub"
            var_replay = artifact_dir / "var_pub_replay"
            fix_replay = artifact_dir / "fix_pub_replay"

            _run(["wllvm", *flags, *klee_flags, *klee_link_flags, *define_flags, "-DKLEE_CF", *sources, *rendered_link_libraries, "-o", var_exe], cwd=code_path)
            _run(["extract-bc", var_exe], cwd=code_path)
            _run(["wllvm", *flags, *klee_flags, *klee_link_flags, *define_flags, "-DKLEE_CF", "-DCONCRETE_PUBS", *sources, *rendered_link_libraries, "-o", fix_exe], cwd=code_path)
            _run(["extract-bc", fix_exe], cwd=code_path)
            _run(["clang", *flags, *noind_flags, *klee_link_flags, *define_flags, "-DREPLAY", *sources, *rendered_link_libraries, "-o", var_replay], cwd=code_path)
            _run(["clang", *flags, *noind_flags, *klee_link_flags, *define_flags, "-DREPLAY", "-DCONCRETE_PUBS", *sources, *rendered_link_libraries, "-o", fix_replay], cwd=code_path)
        elif mode == "binsec":
            var_exe = artifact_dir / "var_pub"
            fix_exe = artifact_dir / "fix_pub"
            var_replay = artifact_dir / "var_pub_replay"
            fix_replay = artifact_dir / "fix_pub_replay"

            _run(["clang", *flags, "-static", *noind_flags, *binsec_link_flags, *define_flags, "-DBINSEC", *sources, *rendered_link_libraries, "-o", var_exe], cwd=code_path)
            _run(["clang", *flags, "-static", *noind_flags, *binsec_link_flags, *define_flags, "-DBINSEC", "-DCONCRETE_PUBS", *sources, *rendered_link_libraries, "-o", fix_exe], cwd=code_path)
            _run(["clang", *flags, "-static", *noind_flags, *binsec_link_flags, *define_flags, "-DREPLAY", *sources, *rendered_link_libraries, "-o", var_replay], cwd=code_path)
            _run(["clang", *flags, "-static", *noind_flags, *binsec_link_flags, *define_flags, "-DREPLAY", "-DCONCRETE_PUBS", *sources, *rendered_link_libraries, "-o", fix_replay], cwd=code_path)
        else:
            abacus_defs = ["-DABACUS"]
            if abacus_concrete_pubs:
                abacus_defs.append("-DCONCRETE_PUBS")
            _run(["gcc", *flags, "-m32", *noind_flags, *abacus_link_flags, *define_flags, *abacus_defs, *sources, *rendered_link_libraries, "-o", artifact_dir / "fix_pub"], cwd=code_path)

        built_targets += 1

    print(f"Done. mode={mode} preset={args.preset or '<default>'} targets={built_targets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())