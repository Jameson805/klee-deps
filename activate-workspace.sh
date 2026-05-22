#!/usr/bin/env bash

# Source the shared conda environment and prepend executable directories from
# this workspace's manifest. The manifest keeps runtime resolution explicit so
# separate worktrees can share one env without sharing build outputs.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "source ./activate-workspace.sh" >&2
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_NAME="${ENV_NAME:-klee-deps-build}"
BUILD_MANIFEST="${BUILD_MANIFEST:-$ROOT_DIR/build/tool-paths.json}"
OPAM_ROOT_DEFAULT="$ROOT_DIR/build/opam-root"
BINSEC_SWITCH_ROOT="$ROOT_DIR/build/deps/src/binsec"
PIN_ROOT_VALUE=""

if ! command -v conda >/dev/null 2>&1; then
    echo "conda is required but was not found on PATH" >&2
    return 1
fi

eval "$(conda shell.bash hook)"
conda activate "$ENV_NAME"

if [[ -f "$BUILD_MANIFEST" ]]; then
    # Read direct executable directories from the manifest instead of
    # hardcoding tool paths so activation follows whichever artifacts this
    # workspace built.
    mapfile -t workspace_bin_dirs < <(
        python - "$BUILD_MANIFEST" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

seen = set()
for artifact_id, record in data.get("artifacts", {}).items():
    if not isinstance(record, dict):
        continue
    if record.get("kind") != "executable":
        continue
    path = Path(record.get("path", ""))
    if not path.exists():
        continue
    if path.name != artifact_id:
        continue
    directory = str(path.parent.resolve())
    if directory in seen:
        continue
    seen.add(directory)
    print(directory)
PY
    )

    for workspace_bin_dir in "${workspace_bin_dirs[@]}"; do
        case ":$PATH:" in
            *":$workspace_bin_dir:"*) ;;
            *) export PATH="$workspace_bin_dir:$PATH" ;;
        esac
    done

    # Artifact ids such as `klee-cf` map to real binaries named `klee`, so
    # expose those manifest ids as shell functions instead of filesystem
    # wrappers under build/bin/.
    eval "$({
        python - "$BUILD_MANIFEST" <<'PY'
import json
from pathlib import Path
import re
import shlex
import sys

manifest_path = Path(sys.argv[1])
with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
for artifact_id, record in sorted(data.get("artifacts", {}).items()):
    if not isinstance(record, dict) or record.get("kind") != "executable":
        continue
    path = Path(record.get("path", ""))
    if not path.is_file() or path.name == artifact_id:
        continue
    if not identifier.match(artifact_id):
        continue
    quoted_path = shlex.quote(str(path.resolve()))
    print(f'function {artifact_id}() {{ {quoted_path} "$@"; }}')
PY
    })"

    if python - "$BUILD_MANIFEST" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

record = data.get("artifacts", {}).get("binsec")
if not isinstance(record, dict):
    raise SystemExit(1)

path = Path(record.get("path", ""))
raise SystemExit(0 if path.is_file() else 1)
PY
    then
        unset OPAMSWITCH OPAMROOT OPAMNOENVNOTICE
        eval "$(opam env --root "$OPAM_ROOT_DEFAULT" --set-root --set-switch --switch "$BINSEC_SWITCH_ROOT" --shell=bash)"
    fi

    PIN_ROOT_VALUE="$({
        python - "$BUILD_MANIFEST" <<'PY'
import json
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
with manifest_path.open(encoding="utf-8") as handle:
    data = json.load(handle)

record = data.get("artifacts", {}).get("intel_pin_root")
if isinstance(record, dict):
    path = Path(record.get("path", ""))
    if path.is_dir() and (path / "pin").is_file():
        print(path.resolve())
PY
    } )"
fi

export KLEE_DEPS_ROOT="$ROOT_DIR"
export KLEE_DEPS_BUILD_MANIFEST="$BUILD_MANIFEST"
if [[ -n "$PIN_ROOT_VALUE" ]]; then
    export PIN_ROOT="$PIN_ROOT_VALUE"
fi
echo "Activated $ENV_NAME with workspace tools from $BUILD_MANIFEST" >&2
