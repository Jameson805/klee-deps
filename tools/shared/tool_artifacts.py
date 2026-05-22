"""Resolve workspace runtime artifacts from the build manifest.

This module intentionally stays generic: it knows only how to load the
workspace build manifest and resolve named artifacts or grouped tool records
from it. Tool-specific decisions about which manifest id to request stay in the
runner that needs the artifact. Keeping resolution repo-local lets multiple
worktrees share one conda environment while still selecting different build
outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_MANIFEST = REPO_ROOT / "build" / "tool-paths.json"


@dataclass(frozen=True)
class KleeToolLayout:
    """Resolved paths for one KLEE tool entry from the build manifest."""

    tool_id: str
    binary: Path
    include_dir: Path
    runtime_lib_dir: Path


def build_manifest_path() -> Path:
    """Return the repo-local build manifest path for the current workspace."""
    return Path(DEFAULT_BUILD_MANIFEST).resolve()


def load_build_manifest() -> dict[str, object]:
    """Load the workspace build manifest or raise a user-facing error."""
    manifest_path = build_manifest_path()
    if not manifest_path.is_file():
        raise SystemExit(
            f"missing build manifest: {manifest_path}. Run ./build_all.sh for the required tool first."
        )

    with manifest_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit(f"invalid build manifest: expected JSON object in {manifest_path}")
    return data


def resolve_artifact_path(artifact_id: str, *, expected_kind: str | None = None) -> Path:
    """Resolve one artifact path from the workspace build manifest."""
    manifest_path = build_manifest_path()
    manifest = load_build_manifest()
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit(f"invalid build manifest: missing artifacts table in {manifest_path}")

    record = artifacts.get(artifact_id)
    if not isinstance(record, dict):
        raise SystemExit(
            f"missing runtime artifact {artifact_id!r} in {manifest_path}. Run ./build_all.sh for that tool first."
        )

    if expected_kind is not None and record.get("kind") != expected_kind:
        raise SystemExit(
            f"runtime artifact {artifact_id!r} in {manifest_path} has kind {record.get('kind')!r}, "
            f"expected {expected_kind!r}"
        )

    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise SystemExit(f"runtime artifact {artifact_id!r} in {manifest_path} is missing a path")

    path = Path(raw_path).resolve()
    if not path.exists():
        raise SystemExit(
            f"runtime artifact {artifact_id!r} points to missing path {path}. Re-run ./build_all.sh for that tool."
        )
    return path


def resolve_tool_record(tool_id: str, *, expected_kind: str | None = None) -> dict[str, object]:
    """Resolve one grouped tool record from the workspace build manifest."""
    manifest_path = build_manifest_path()
    manifest = load_build_manifest()
    tools = manifest.get("tools")
    if not isinstance(tools, dict):
        raise SystemExit(f"invalid build manifest: missing tools table in {manifest_path}")

    record = tools.get(tool_id)
    if not isinstance(record, dict):
        raise SystemExit(
            f"missing tool record {tool_id!r} in {manifest_path}. Run ./build_all.sh for that tool first."
        )

    if expected_kind is not None and record.get("kind") != expected_kind:
        raise SystemExit(
            f"tool record {tool_id!r} in {manifest_path} has kind {record.get('kind')!r}, "
            f"expected {expected_kind!r}"
        )

    return record


def _resolve_record_path(
    record: dict[str, object],
    *,
    tool_id: str,
    field: str,
    expected_directory: bool,
) -> Path:
    raw_path = record.get(field)
    if not isinstance(raw_path, str) or not raw_path:
        raise SystemExit(f"tool record {tool_id!r} is missing {field!r}")

    path = Path(raw_path).resolve()
    if expected_directory:
        if not path.is_dir():
            raise SystemExit(f"tool record {tool_id!r} field {field!r} is not a directory: {path}")
    elif not path.is_file():
        raise SystemExit(f"tool record {tool_id!r} field {field!r} is not a file: {path}")
    return path


def resolve_klee_tool_layout(tool_id: str) -> KleeToolLayout:
    """Resolve the grouped manifest entry for one KLEE tool."""
    record = resolve_tool_record(tool_id, expected_kind="klee-tool")
    return KleeToolLayout(
        tool_id=tool_id,
        binary=_resolve_record_path(record, tool_id=tool_id, field="binary", expected_directory=False),
        include_dir=_resolve_record_path(record, tool_id=tool_id, field="include_dir", expected_directory=True),
        runtime_lib_dir=_resolve_record_path(record, tool_id=tool_id, field="runtime_lib_dir", expected_directory=True),
    )


def resolve_executable_path(artifact_id: str) -> Path:
    """Resolve one executable artifact path from the workspace build manifest."""
    path = resolve_artifact_path(artifact_id, expected_kind="executable")
    if not path.is_file():
        raise SystemExit(f"runtime artifact {artifact_id!r} is not a file: {path}")
    return path


def resolve_intel_pin_root() -> Path:
    """Resolve the workspace-managed Intel Pin installation directory."""
    path = resolve_artifact_path("intel_pin_root", expected_kind="directory")
    if not path.is_dir():
        raise SystemExit(f"runtime artifact 'intel_pin_root' is not a directory: {path}")
    if not (path / "pin").is_file():
        raise SystemExit(
            f"workspace Intel Pin install is incomplete: missing pin launcher under {path}. "
            "Run ./build_all.sh pin or ./build_all.sh all."
        )
    return path
