#!/usr/bin/env python3
"""Launch the ABACUS-only campaign from TOML.

This runner can execute directly against an existing ABACUS checkout or build a
fresh Docker image from an ABACUS repository path and run the campaign inside
that container. The experiment loop stays linear: validate config, launch each
sym-size as multiple direct worker processes, then merge the per-size JSON
outputs on the host.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.common import (
    REPO_ROOT,
    LaunchedProcess,
    benchmark_csv_from_config,
    launch_prefixed_module,
    resolve_repo_path,
    terminate_processes,
    wait_for_processes,
    worker_log_path,
)
from scripts.validation.validate_experiments_abacus import main as validate_experiments_abacus_main
from tools.postprocess.merge_json_runs_by_experiment import main as merge_json_runs_main
from tools.shared.campaign_tools import campaign_tool
from tools.shared.experiment_registry import format_benchmark_selector, selected_benchmarks


DOCKER_IMAGE_TAG = "klee-deps-abacus-local"
DOCKER_PROXY_ENV_VARS = (
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
)


def resolve_host_path(path: str | Path) -> Path:
    """Resolve a host path from config, keeping repo-relative behavior."""
    return Path(resolve_repo_path(path)).expanduser().resolve()


def container_path_for_host_path(host_path: Path, container_workdir: Path) -> Path:
    """Map a host path into the container workdir when it lives in the repo."""
    resolved_host_path = host_path.resolve()
    try:
        relative_path = resolved_host_path.relative_to(REPO_ROOT)
    except ValueError:
        return resolved_host_path
    return container_workdir / relative_path


def append_mount(command: list[str], host_path: Path, container_path: Path, seen_mounts: set[tuple[str, str]]) -> None:
    """Append one Docker bind mount unless it has already been added."""
    mount = (str(host_path), str(container_path))
    if mount in seen_mounts:
        return
    seen_mounts.add(mount)
    command.extend(["-v", f"{host_path}:{container_path}"])


def run_checked(command: list[str], *, cwd: Path = REPO_ROOT) -> int:
    """Run one subprocess command and return its exit status."""
    print(f"$ {' '.join(command)}")
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


def docker_build_command(build_context: Path) -> list[str]:
    """Build the Docker command used for containerized ABACUS campaigns."""
    command = ["docker", "build", "-t", DOCKER_IMAGE_TAG]
    for variable_name in DOCKER_PROXY_ENV_VARS:
        value = os.environ.get(variable_name)
        if value:
            command.extend(["--build-arg", f"{variable_name}={value}"])
    command.append(str(build_context))
    return command


def docker_user_args() -> list[str]:
    """Run Docker containers as the invoking host user when possible."""
    if os.name != "posix":
        return []
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def docker_bootstrap_command(*, container_abacus_root: Path) -> list[str]:
    """Build the ABACUS QIF binary and ia32 pintool inside the container."""
    container_build_root = Path("/tmp/abacus-build")
    bootstrap_script = " && ".join(
        [
            f"rm -rf {container_build_root}",
            f"cmake -S {container_abacus_root} -B {container_build_root} -DCMAKE_BUILD_TYPE=Release",
            f"cmake --build {container_build_root} --parallel",
            f"mkdir -p {container_abacus_root / 'build' / 'App' / 'QIF'}",
            f"cp {container_build_root / 'App' / 'QIF' / 'QIF'} {container_abacus_root / 'build' / 'App' / 'QIF' / 'QIF'}",
            (
                "make "
                f"-C {container_abacus_root / 'Pintools'} "
                f"PIN_ROOT={container_abacus_root / 'Intel-Pin-Archive'} "
                "TARGET=ia32 "
                '-j"$(nproc)"'
            ),
        ]
    )
    return ["bash", "-lc", bootstrap_script]


def run_merge_steps(output_dir: Path, sym_sizes: list[int]) -> int:
    """Merge per-copy JSON outputs for each configured ABACUS sym-size."""
    for sym_size in sym_sizes:
        destination = output_dir / f"abacus_{sym_size}"
        if merge_json_runs_main([str(destination)]) != 0:
            return 1
    return 0


def run_validation_steps(output_dir: Path, sym_sizes: list[int]) -> int:
    """Run host-side ABACUS validation over the merged per-sym outputs."""
    command = ["--output-base", str(output_dir)]
    for sym_size in sym_sizes:
        command.extend(["--sym-size", str(sym_size)])
    print(f"$ {sys.executable} -m scripts.validation.validate_experiments_abacus {' '.join(command)}")
    return validate_experiments_abacus_main(command)


def print_completion_summary(output_dir: Path, *, validated: bool) -> None:
    """Print the short host-side completion summary for ABACUS campaigns."""
    print("All Abacus prototype runs completed.")
    print(f"Collected Abacus output root: {output_dir}")
    print(f"Per-size merged JSON generated under: {output_dir}/abacus_<sym>")
    if validated:
        print("Host-side Abacus validation step completed; see output above for replay counts.")
    else:
        print("Run validation separately on merged results when needed, or rerun with --validate.")


def run_worker_copies(
    *,
    abacus_root: Path,
    benchmark_csv_value: str | None,
    num_copies: int,
    output_dir: Path,
    sym_sizes: list[int],
    tmp_dir: str,
) -> int:
    """Launch direct host-side ABACUS workers for each configured sym-size."""
    tool = campaign_tool("abacus")
    for sym_size in sym_sizes:
        destination = output_dir / f"abacus_{sym_size}"
        launched_runs: list[LaunchedProcess] = []
        try:
            shutil.rmtree(destination, ignore_errors=True)
            destination.mkdir(parents=True, exist_ok=True)
            for copy_index in range(num_copies):
                worker_destination = destination / str(copy_index)
                worker_destination.mkdir(parents=True, exist_ok=True)
                current_worker_log_path = worker_log_path(destination, copy_index)
                worker_argv = tool.build_worker_argv(
                    [str(abacus_root), "--sym-size", str(sym_size)],
                    benchmark_csv=benchmark_csv_value,
                    results_dir=worker_destination,
                    tmp_dir=tmp_dir,
                )
                launched_runs.append(
                    launch_prefixed_module(
                        f"ABACUS SYM {sym_size} #{copy_index}",
                        tool.module_name,
                        worker_argv,
                        cwd=REPO_ROOT,
                        log_path=current_worker_log_path,
                    )
                )
            if wait_for_processes(launched_runs) != 0:
                return 1
        except BaseException:
            terminate_processes(launched_runs)
            raise
    return 0


def run_docker_campaign(
    *,
    docker_abacus_repo: Path,
    config_path: Path,
    output_dir: Path,
    sym_sizes: list[int],
    validate: bool,
    args: argparse.Namespace,
) -> int:
    """Build the Docker image and rerun this campaign inside the container."""
    container_workdir = Path(args.container_workdir or str(REPO_ROOT))
    container_abacus_root = Path(args.container_abacus_root)
    container_config_path = container_path_for_host_path(config_path, container_workdir)

    if run_checked(docker_build_command(docker_abacus_repo)) != 0:
        return 1

    seen_mounts: set[tuple[str, str]] = set()
    command = [
        "docker",
        "run",
        "--rm",
        *docker_user_args(),
        "-w",
        str(container_workdir),
    ]
    append_mount(command, REPO_ROOT, container_workdir, seen_mounts)
    append_mount(command, docker_abacus_repo, container_abacus_root, seen_mounts)

    bootstrap_command = command + [DOCKER_IMAGE_TAG, *docker_bootstrap_command(container_abacus_root=container_abacus_root)]
    if run_checked(bootstrap_command) != 0:
        return 1

    if output_dir.exists():
        container_output_dir = container_path_for_host_path(output_dir, container_workdir)
        if container_output_dir == output_dir.resolve() and not str(output_dir).startswith(str(REPO_ROOT)):
            append_mount(command, output_dir, container_output_dir, seen_mounts)

    try:
        config_path.relative_to(REPO_ROOT)
    except ValueError:
        append_mount(command, config_path.parent, config_path.parent, seen_mounts)

    command.extend(
        [
            DOCKER_IMAGE_TAG,
            "python3",
            "scripts/experiments/run_experiments_abacus.py",
            str(container_config_path),
            "--inside-container",
            "--container-abacus-root",
            str(container_abacus_root),
            "--container-tmp-dir",
            args.container_tmp_dir,
            "--container-workdir",
            str(container_workdir),
        ]
    )

    if run_checked(command) != 0:
        return 1
    if run_merge_steps(output_dir, sym_sizes) != 0:
        return 1
    if validate and run_validation_steps(output_dir, sym_sizes) != 0:
        return 1
    print_completion_summary(output_dir, validated=validate)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the ABACUS-only campaign orchestrator."""
    parser = argparse.ArgumentParser(description="Run the ABACUS-only campaign.")
    parser.add_argument("config", help="Path to ABACUS campaign TOML config")
    parser.add_argument(
        "--docker",
        metavar="ABACUS_REPO",
        help="Build a fresh Docker image from the given ABACUS repo path and run the campaign inside it",
    )
    parser.add_argument(
        "--container-abacus-root",
        default="/abacus",
        help="ABACUS checkout path inside the container",
    )
    parser.add_argument(
        "--container-tmp-dir",
        default="/tmp",
        help="Temporary workspace root used by the in-container run",
    )
    parser.add_argument(
        "--container-workdir",
        help="Container path where the repository is mounted (default: host repo path)",
    )
    parser.add_argument("--postprocess-only", action="store_true", help="Run only merge steps")
    parser.add_argument("--validate", action="store_true", help="Run host-side validation after merge steps")
    parser.add_argument("--inside-container", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    config_path = resolve_host_path(args.config)
    if not config_path.is_file():
        raise SystemExit(f"missing config file: {config_path}")

    with config_path.open("rb") as handle:
        raw_config = tomllib.load(handle)

    campaign = raw_config.get("campaign", {})
    benchmarks_section = raw_config.get("benchmarks", {})
    if not isinstance(campaign, dict):
        raise SystemExit("campaign config must be a TOML table")
    if not isinstance(benchmarks_section, dict):
        raise SystemExit("benchmarks config must be a TOML table")

    num_copies = campaign.get("num_copies", 10)
    if not isinstance(num_copies, int) or num_copies <= 0:
        raise SystemExit("campaign.num_copies must be a positive integer")
    tmp_dir_raw = campaign.get("tmp_dir", "/tmp")
    if not isinstance(tmp_dir_raw, str) or not tmp_dir_raw:
        raise SystemExit("campaign.tmp_dir must be a non-empty string")
    output_raw = campaign.get("output", str(REPO_ROOT / "results/abacus_experiments"))
    if not isinstance(output_raw, str) or not output_raw:
        raise SystemExit("campaign.output must be a non-empty string")
    sym_sizes = campaign.get("sym_sizes", [4, 16])
    if not isinstance(sym_sizes, list) or not sym_sizes:
        raise SystemExit("campaign.sym_sizes must be a non-empty array of integers")
    if not all(isinstance(sym_size, int) and sym_size >= 0 for sym_size in sym_sizes):
        raise SystemExit("campaign.sym_sizes must contain only non-negative integers")

    try:
        benchmark_csv = benchmark_csv_from_config(benchmarks_section.get("abacus"), "benchmarks.abacus")
    except ValueError as error:
        raise SystemExit(str(error)) from error
    try:
        normalized_benchmarks = selected_benchmarks("abacus", benchmark_csv)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    output_dir = resolve_host_path(output_raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_csv_value = (
        None
        if benchmark_csv is None
        else ",".join(
            format_benchmark_selector(library_id, variant_id)
            for library_id, variant_id in normalized_benchmarks
        )
    )

    if args.docker and args.inside_container:
        raise SystemExit("--docker cannot be used together with --inside-container")

    if args.docker and not args.inside_container:
        if args.postprocess_only:
            if run_merge_steps(output_dir, sym_sizes) != 0:
                raise SystemExit(1)
            if args.validate and run_validation_steps(output_dir, sym_sizes) != 0:
                raise SystemExit(1)
            print_completion_summary(output_dir, validated=args.validate)
            return 0
        docker_abacus_repo = resolve_host_path(args.docker)
        if not docker_abacus_repo.is_dir():
            raise SystemExit(f"docker ABACUS repo path does not exist: {docker_abacus_repo}")
        return run_docker_campaign(
            docker_abacus_repo=docker_abacus_repo,
            config_path=config_path,
            output_dir=output_dir,
            sym_sizes=sym_sizes,
            validate=args.validate,
            args=args,
        )

    if args.inside_container:
        abacus_root = Path(args.container_abacus_root).resolve()
        tmp_dir = args.container_tmp_dir
    else:
        abacus_root_raw = campaign.get("abacus_root")
        if not isinstance(abacus_root_raw, str) or not abacus_root_raw:
            raise SystemExit("campaign.abacus_root must be a non-empty string")
        abacus_root = resolve_host_path(abacus_root_raw)
        tmp_dir = tmp_dir_raw

    if not abacus_root.is_dir():
        raise SystemExit(f"abacus root path does not exist: {abacus_root}")

    if not args.postprocess_only:
        if run_worker_copies(
            abacus_root=abacus_root,
            benchmark_csv_value=benchmark_csv_value,
            num_copies=num_copies,
            output_dir=output_dir,
            sym_sizes=sym_sizes,
            tmp_dir=tmp_dir,
        ) != 0:
            raise SystemExit(1)

    if args.inside_container:
        return 0

    if run_merge_steps(output_dir, sym_sizes) != 0:
        raise SystemExit(1)
    if args.validate and run_validation_steps(output_dir, sym_sizes) != 0:
        raise SystemExit(1)
    print_completion_summary(output_dir, validated=args.validate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
