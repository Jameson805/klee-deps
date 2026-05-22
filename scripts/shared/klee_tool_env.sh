#!/usr/bin/env bash

load_klee_tool_layout() {
    local repo_root="$1"
    local tool_id="${2:-${KLEE_TOOL_ID:-klee-cf}}"

    eval "$(cd "$repo_root" && python -m tools.resolve_tool_runtime --tool "$tool_id" --format shell)"
}