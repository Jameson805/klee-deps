#!/usr/bin/env python3
"""Generate benchmark-local runner artifacts from one runner-config preset.

Benchmark build scripts call this helper to materialize the shared generated
header and, when needed, Binsec cfg files. Keeping that logic here avoids
duplicating preset parsing rules across many shell scripts.
"""
import argparse
import os
from pathlib import Path
import re
import sys
import tomllib


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_runner_config(config_path: str | Path) -> dict[str, object]:
    """Load and validate the top-level TOML object for one runner config."""
    path = Path(config_path)

    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
    except OSError as exc:
        raise ValueError(f"failed to load runner config {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"failed to parse runner config {path}: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError(f"runner config {path} root must be a table")

    return config


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate runner artifacts for one selected preset")
    parser.add_argument("--config", required=True, help="Path to runner config")
    parser.add_argument("--preset", required=False, help="Preset name to materialize")
    parser.add_argument("--header-out", "--out", dest="header_out", help="Path to generated header")
    parser.add_argument("--binsec-base", help="Path to shared Binsec base config")
    parser.add_argument("--binsec-fix-pub-out", help="Path to generated Binsec fix_pub config")
    parser.add_argument("--binsec-var-pub-out", help="Path to generated Binsec var_pub config")
    args = parser.parse_args()

    if not args.header_out and not args.binsec_fix_pub_out and not args.binsec_var_pub_out:
        _die("select at least one artifact output")

    if (args.binsec_fix_pub_out or args.binsec_var_pub_out) and not args.binsec_base:
        _die("Binsec outputs require --binsec-base")

    return args


def _normalize_preset_bytes(label: str, resolved_size: int, value: object) -> list[int]:
    if isinstance(value, int):
        if value < 0:
            _die(f"{label} must be non-negative")
        if value >= (1 << (resolved_size * 8)):
            _die(f"{label}=0x{value:x} does not fit in {resolved_size} bytes")
        byte_values: list[int] = []
        for index in range(resolved_size):
            shift = (resolved_size - index - 1) * 8
            byte_values.append((value >> shift) & 0xFF)
        return byte_values

    if isinstance(value, list) and value:
        byte_values = []
        for byte_value in value:
            if not isinstance(byte_value, int) or byte_value < 0 or byte_value > 0xFF:
                _die(f"{label} contains invalid byte value: {byte_value!r}")
            byte_values.append(byte_value)
        if len(byte_values) != resolved_size:
            _die(f"{label} has {len(byte_values)} bytes but expected {resolved_size}")
        return byte_values

    _die(f"{label} must be either a non-negative integer or a non-empty list of bytes")


def _load_resolved_config(config_path: str, selected_preset_name: str | None) -> dict[str, object]:
    """Resolve one config/preset pair into concrete byte-oriented values."""
    try:
        cfg = load_runner_config(config_path)
    except ValueError as exc:
        _die(str(exc))

    if not isinstance(cfg, dict):
        _die("config root must be a dictionary")

    for key in ("inputs", "mode_policy", "presets"):
        if key not in cfg:
            _die(f"missing top-level key: {key}")

    inputs = cfg["inputs"]
    mode_policy = cfg["mode_policy"]
    presets = cfg["presets"]
    if not isinstance(inputs, list) or not inputs:
        _die("inputs must be a non-empty list")
    if not isinstance(mode_policy, dict):
        _die("mode_policy must be a dictionary")
    if not isinstance(presets, dict) or not presets:
        _die("presets must be a non-empty dictionary")

    var_pub_policy = mode_policy.get("var_pub")
    fix_pub_policy = mode_policy.get("fix_pub")
    abacus_policy = mode_policy.get("abacus")
    if not isinstance(var_pub_policy, dict):
        _die("mode_policy.var_pub must be a dictionary")
    if not isinstance(fix_pub_policy, dict):
        _die("mode_policy.fix_pub must be a dictionary")
    if not isinstance(abacus_policy, dict):
        _die("mode_policy.abacus must be a dictionary")
    if var_pub_policy.get("public_symbolic") is not True:
        _die("mode_policy.var_pub.public_symbolic must be True")
    if fix_pub_policy.get("public_symbolic") is not False:
        _die("mode_policy.fix_pub.public_symbolic must be False")
    if abacus_policy.get("public_fixed") is not True:
        _die("mode_policy.abacus.public_fixed must be True; symbolic ABACUS public inputs are not implemented")

    input_specs: dict[str, dict] = {}
    input_order: list[str] = []
    secret_input_ids: list[str] = []
    public_input_ids: list[str] = []
    input_names: set[str] = set()

    for inp in inputs:
        if not isinstance(inp, dict):
            _die("each input must be a dictionary")

        input_id = inp.get("id")
        if not isinstance(input_id, str) or not IDENTIFIER_RE.match(input_id):
            _die(f"invalid input id: {input_id!r}")
        if input_id in input_specs:
            _die(f"duplicate input id: {input_id}")

        input_name = inp.get("name")
        if not isinstance(input_name, str) or not IDENTIFIER_RE.match(input_name):
            _die(f"input {input_id} has invalid name: {input_name!r}")
        if input_name in input_names:
            _die(f"duplicate input name: {input_name}")

        kind = inp.get("kind")
        if kind not in {"secret", "public"}:
            _die(f"input {input_id} has invalid kind: {kind!r}")

        size = inp.get("size")
        if not isinstance(size, (int, str)):
            _die(f"input {input_id} has unsupported size expression: {size!r}")

        constraints = inp.get("constraints", [])
        if constraints is None:
            constraints = []
        if not isinstance(constraints, list):
            _die(f"input {input_id}.constraints must be a list")
        for constraint in constraints:
            if constraint not in {"top_bit_set", "odd"}:
                _die(f"unsupported constraint {constraint!r} on input {input_id}")

        input_specs[input_id] = inp
        input_order.append(input_id)
        input_names.add(input_name)
        if kind == "secret":
            secret_input_ids.append(input_id)
        else:
            public_input_ids.append(input_id)

    abacus_secret_inputs = abacus_policy.get("secret_inputs")
    if not isinstance(abacus_secret_inputs, list):
        _die("mode_policy.abacus.secret_inputs must be a list")
    for input_id in abacus_secret_inputs:
        if input_id not in secret_input_ids:
            _die(f"mode_policy.abacus.secret_inputs contains non-secret input {input_id!r}")
    if set(abacus_secret_inputs) != set(secret_input_ids):
        _die("mode_policy.abacus.secret_inputs must list every secret input exactly once")

    if selected_preset_name is None:
        if len(presets) == 1:
            selected_preset_name = next(iter(presets.keys()))
        else:
            _die("multiple presets exist; select one with --preset")

    if selected_preset_name not in presets:
        available = ", ".join(sorted(presets.keys()))
        _die(f"unknown preset {selected_preset_name!r}; available presets: {available}")

    selected_preset = presets[selected_preset_name]
    if not isinstance(selected_preset, dict):
        _die(f"preset {selected_preset_name} must be a dictionary")

    selected_macros = selected_preset.get("macros", {})
    selected_vars = selected_preset.get("vars", {})
    selected_abacus_secrets = selected_preset.get("abacus_secrets", {})
    if not isinstance(selected_macros, dict):
        _die(f"preset {selected_preset_name}.macros must be a dictionary")
    if not isinstance(selected_vars, dict):
        _die(f"preset {selected_preset_name}.vars must be a dictionary")
    if not isinstance(selected_abacus_secrets, dict):
        _die(f"preset {selected_preset_name}.abacus_secrets must be a dictionary")

    for macro_name, macro_value in selected_macros.items():
        if not isinstance(macro_name, str) or not IDENTIFIER_RE.match(macro_name):
            _die(f"preset {selected_preset_name} has invalid macro name: {macro_name!r}")
        if not isinstance(macro_value, int) or macro_value <= 0:
            _die(f"preset {selected_preset_name}.macros.{macro_name} must be a positive integer")

    resolved_input_sizes: dict[str, int] = {}
    for input_id in input_order:
        size = input_specs[input_id]["size"]
        if isinstance(size, int):
            resolved_size = size
        elif isinstance(size, str) and IDENTIFIER_RE.match(size):
            if size not in selected_macros:
                _die(f"input {input_id} uses macro {size!r}, but preset {selected_preset_name} does not define it")
            resolved_size = selected_macros[size]
        else:
            _die(f"input {input_id} has unsupported size expression: {size!r}")
        if not isinstance(resolved_size, int) or resolved_size <= 0:
            _die(f"input {input_id} resolved to invalid size: {resolved_size!r}")
        resolved_input_sizes[input_id] = resolved_size

    selected_public_arrays: list[tuple[str, list[int]]] = []
    for input_id, value in selected_vars.items():
        if input_id not in public_input_ids:
            _die(f"preset {selected_preset_name}.vars.{input_id} must target a public input")
        byte_values = _normalize_preset_bytes(
            f"preset {selected_preset_name}.vars.{input_id}",
            resolved_input_sizes[input_id],
            value,
        )
        selected_public_arrays.append((input_id, byte_values))

    if set(selected_vars.keys()) != set(public_input_ids):
        _die("preset vars must provide defaults for every public input")

    selected_abacus_arrays: list[tuple[str, list[int]]] = []
    for input_id, value in selected_abacus_secrets.items():
        if input_id not in secret_input_ids:
            _die(f"preset {selected_preset_name}.abacus_secrets.{input_id} must target a secret input")
        byte_values = _normalize_preset_bytes(
            f"preset {selected_preset_name}.abacus_secrets.{input_id}",
            resolved_input_sizes[input_id],
            value,
        )
        selected_abacus_arrays.append((input_id, byte_values))

    if set(selected_abacus_secrets.keys()) != set(abacus_secret_inputs):
        _die("preset abacus_secrets must provide seeds for every ABACUS secret input")

    return {
        "input_specs": input_specs,
        "input_order": input_order,
        "secret_input_ids": secret_input_ids,
        "public_input_ids": public_input_ids,
        "mode_policy": mode_policy,
        "selected_preset_name": selected_preset_name,
        "selected_macros": selected_macros,
        "selected_public_arrays": selected_public_arrays,
        "selected_abacus_arrays": selected_abacus_arrays,
        "preset_symbol": re.sub(r"[^A-Za-z0-9_]", "_", selected_preset_name),
        "abacus_public_fixed": abacus_policy["public_fixed"],
    }


def _render_header(resolved: dict[str, object]) -> list[str]:
    """Render the generated C header consumed by benchmark wrappers."""
    input_specs = resolved["input_specs"]
    input_order = resolved["input_order"]
    secret_input_ids = resolved["secret_input_ids"]
    public_input_ids = resolved["public_input_ids"]
    selected_macros = resolved["selected_macros"]
    selected_public_arrays = resolved["selected_public_arrays"]
    selected_abacus_arrays = resolved["selected_abacus_arrays"]
    selected_preset_name = resolved["selected_preset_name"]
    preset_symbol = resolved["preset_symbol"]
    abacus_public_fixed = resolved["abacus_public_fixed"]

    lines: list[str] = []
    lines.append("#ifndef RUNNER_CONFIG_GENERATED_H")
    lines.append("#define RUNNER_CONFIG_GENERATED_H")
    lines.append("")
    lines.append("#include <stddef.h>")
    lines.append("#include <stdint.h>")
    lines.append("#include <stdio.h>")
    lines.append("")
    lines.append(f'#define RUNNER_SELECTED_PRESET "{selected_preset_name}"')
    lines.append("")

    for macro_name in sorted(selected_macros.keys()):
        lines.append(f"#define {macro_name} {selected_macros[macro_name]}")
    if selected_macros:
        lines.append("")

    lines.append(f"#define RUNNER_ABACUS_PUBLIC_FIXED {1 if abacus_public_fixed else 0}")
    lines.append(f"#define RUNNER_REPLAY_ARGC_CONCRETE {1 + len(secret_input_ids)}")
    lines.append(f"#define RUNNER_REPLAY_ARGC_SYMBOLIC {1 + len(secret_input_ids) + len(public_input_ids)}")
    lines.append("")

    for input_id in input_order:
        size_value = input_specs[input_id]["size"]
        size_expr = str(size_value) if isinstance(size_value, int) else size_value
        lines.append(f"unsigned char {input_id}[{size_expr}];")
        if input_specs[input_id]["kind"] == "secret":
            lines.append(f"unsigned char runner_secret_1_{input_id}[{size_expr}];")
            lines.append(f"unsigned char runner_secret_2_{input_id}[{size_expr}];")
    lines.append("")

    lines.append("#include \"runner.h\"")
    lines.append("")

    for input_id, byte_values in selected_public_arrays:
        initializer = ", ".join(f"0x{byte_value:02x}" for byte_value in byte_values)
        lines.append(f"const unsigned char runner_preset_{preset_symbol}_{input_id}[] = {{ {initializer} }};")
    if selected_public_arrays:
        lines.append("")

    for input_id, byte_values in selected_abacus_arrays:
        initializer = ", ".join(f"0x{byte_value:02x}" for byte_value in byte_values)
        lines.append(f"const unsigned char runner_abacus_seed_{preset_symbol}_{input_id}[] = {{ {initializer} }};")
    if selected_abacus_arrays:
        lines.append("")

    lines.append("int runner_apply_preset(void) {")
    for input_id, _ in selected_public_arrays:
        lines.append(f"    runner_copy_bytes({input_id}, runner_preset_{preset_symbol}_{input_id}, sizeof({input_id}));")
    lines.append("    return 1;")
    lines.append("}")
    lines.append("")

    lines.append("int runner_load_replay_inputs(int argc, char *argv[]) {")
    lines.append("    int arg_index = 1;")
    lines.append("    if (argc != RUNNER_EXPECTED_REPLAY_ARGC) {")
    lines.append("        return 0;")
    lines.append("    }")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "secret":
            lines.append(f"    if (!load_bytes(argv[arg_index++], {input_id}, sizeof({input_id}))) {{")
            lines.append("        return 0;")
            lines.append("    }")
    lines.append("#ifndef CONCRETE_PUBS")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "public":
            lines.append(f"    if (!load_bytes(argv[arg_index++], {input_id}, sizeof({input_id}))) {{")
            lines.append("        return 0;")
            lines.append("    }")
    lines.append("#endif")
    lines.append("    return 1;")
    lines.append("}")
    lines.append("")

    lines.append("#if defined(KLEE_CF) || defined(SELF_COMP)")
    lines.append("void runner_apply_klee_assumptions(void) {")
    for input_id in input_order:
        size_value = input_specs[input_id]["size"]
        size_expr = str(size_value) if isinstance(size_value, int) else size_value
        for constraint in input_specs[input_id].get("constraints", []):
            if constraint == "top_bit_set":
                lines.append(f"    klee_assume({input_id}[0] & 0x80);")
            elif constraint == "odd":
                lines.append(f"    klee_assume({input_id}[{size_expr} - 1] & 1);")
    lines.append("}")
    lines.append("#endif")
    lines.append("")

    lines.append("#ifdef KLEE_CF")
    lines.append("void runner_make_klee_secret_inputs(void) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "secret":
            lines.append(f'    klee_make_symbolic_sc({input_id}, sizeof({input_id}), "{input_specs[input_id]["name"]}", 1);')
    lines.append("}")
    lines.append("")
    lines.append("void runner_make_klee_public_inputs(void) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "public":
            lines.append(f'    klee_make_symbolic_sc({input_id}, sizeof({input_id}), "{input_specs[input_id]["name"]}", 0);')
    lines.append("}")
    lines.append("#endif")
    lines.append("")

    lines.append("#ifdef SELF_COMP")
    lines.append("void runner_make_selfcomp_secret_variants(void) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "secret":
            lines.append(f'    klee_make_symbolic(runner_secret_1_{input_id}, sizeof(runner_secret_1_{input_id}), "{input_specs[input_id]["name"]}_1");')
            lines.append(f'    klee_make_symbolic(runner_secret_2_{input_id}, sizeof(runner_secret_2_{input_id}), "{input_specs[input_id]["name"]}_2");')
    lines.append("}")
    lines.append("")
    lines.append("void runner_copy_secret_input_variant_1(void) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "secret":
            lines.append(f"    runner_copy_bytes({input_id}, runner_secret_1_{input_id}, sizeof({input_id}));")
    lines.append("}")
    lines.append("")
    lines.append("void runner_copy_secret_input_variant_2(void) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "secret":
            lines.append(f"    runner_copy_bytes({input_id}, runner_secret_2_{input_id}, sizeof({input_id}));")
    lines.append("}")
    lines.append("")
    lines.append("void runner_make_selfcomp_public_inputs(void) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "public":
            lines.append(f'    klee_make_symbolic({input_id}, sizeof({input_id}), "{input_specs[input_id]["name"]}");')
    lines.append("}")
    lines.append("")
    lines.append("void runner_dump_counterexample(FILE *stream, int include_public_inputs) {")
    lines.append("    const char runner_hex[] = \"0123456789abcdef\";")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "secret":
            input_name = input_specs[input_id]["name"]
            lines.append(f"    char {input_id}_1_hex[sizeof(runner_secret_1_{input_id}) * 2 + 3];")
            lines.append(f"    char {input_id}_2_hex[sizeof(runner_secret_2_{input_id}) * 2 + 3];")
            for variant in (1, 2):
                buffer_name = f"runner_secret_{variant}_{input_id}"
                hex_name = f"{input_id}_{variant}_hex"
                lines.append(f"    {hex_name}[0] = '0';")
                lines.append(f"    {hex_name}[1] = 'x';")
                lines.append(f"    for (size_t i = 0; i < sizeof({buffer_name}); ++i) {{")
                lines.append(f"        unsigned char value = (unsigned char)klee_get_value_i32((unsigned){buffer_name}[i]);")
                lines.append(f"        {hex_name}[2 + i * 2] = runner_hex[(value >> 4) & 0x0F];")
                lines.append(f"        {hex_name}[2 + i * 2 + 1] = runner_hex[value & 0x0F];")
                lines.append("    }")
                lines.append(f"    {hex_name}[sizeof({buffer_name}) * 2 + 2] = '\\0';")
            lines.append(f'    fprintf(stream, " {input_name}_1=%s {input_name}_2=%s", {input_id}_1_hex, {input_id}_2_hex);')
    lines.append("    if (include_public_inputs) {")
    for input_id in input_order:
        if input_specs[input_id]["kind"] == "public":
            input_name = input_specs[input_id]["name"]
            lines.append(f"        char {input_id}_hex[sizeof({input_id}) * 2 + 3];")
            lines.append(f"        {input_id}_hex[0] = '0';")
            lines.append(f"        {input_id}_hex[1] = 'x';")
            lines.append(f"        for (size_t i = 0; i < sizeof({input_id}); ++i) {{")
            lines.append(f"            unsigned char value = (unsigned char)klee_get_value_i32((unsigned){input_id}[i]);")
            lines.append(f"            {input_id}_hex[2 + i * 2] = runner_hex[(value >> 4) & 0x0F];")
            lines.append(f"            {input_id}_hex[2 + i * 2 + 1] = runner_hex[value & 0x0F];")
            lines.append("        }")
            lines.append(f"        {input_id}_hex[sizeof({input_id}) * 2 + 2] = '\\0';")
            lines.append(f'        fprintf(stream, " {input_name}=%s", {input_id}_hex);')
    lines.append("    }")
    lines.append("}")
    lines.append("#endif")
    lines.append("")

    lines.append("#ifdef ABACUS")
    lines.append("void runner_make_abacus_secret_inputs(void) {")
    for input_id, _ in selected_abacus_arrays:
        lines.append(f"    runner_copy_bytes({input_id}, runner_abacus_seed_{preset_symbol}_{input_id}, sizeof({input_id}));")
        lines.append(f'    abacus_make_symbolic("{input_specs[input_id]["name"]}", {input_id}, sizeof({input_id}));')
    lines.append("}")
    lines.append("#endif")
    lines.append("")
    lines.append("#endif // RUNNER_CONFIG_GENERATED_H")
    lines.append("")
    return lines


def _render_binsec_config(resolved: dict[str, object], base_path: str, mode_name: str) -> list[str]:
    """Render one Binsec cfg file for the requested public-input mode."""
    mode_policy = resolved["mode_policy"]
    secret_input_ids = resolved["secret_input_ids"]
    public_input_ids = resolved["public_input_ids"]

    if mode_name not in {"fix_pub", "var_pub"}:
        _die(f"unsupported Binsec mode: {mode_name}")

    with open(base_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    while lines and lines[-1] == "":
        lines.pop()

    if secret_input_ids:
        lines.append(f"secret global {', '.join(secret_input_ids)}")
    if public_input_ids and mode_policy[mode_name]["public_symbolic"]:
        lines.append(f"public global {', '.join(public_input_ids)}")
    lines.append("")
    lines.append("halt at <exit>")
    lines.append("explore all")
    lines.append("")
    return lines


def _write_lines(out_path: str, lines: list[str]) -> None:
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    """CLI entrypoint used by benchmark build scripts."""
    args = _parse_args()
    resolved = _load_resolved_config(args.config, args.preset)

    if args.header_out:
        _write_lines(args.header_out, _render_header(resolved))

    if args.binsec_fix_pub_out:
        _write_lines(args.binsec_fix_pub_out, _render_binsec_config(resolved, args.binsec_base, "fix_pub"))

    if args.binsec_var_pub_out:
        _write_lines(args.binsec_var_pub_out, _render_binsec_config(resolved, args.binsec_base, "var_pub"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
