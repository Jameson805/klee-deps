#!/usr/bin/env python3
"""Generate and validate the modular-exponentiation fixed defaults.

The modexp runner config chooses a small prime base, the largest representable
prime modulus, and the second largest representable prime exponent seed for the
active byte widths. This module reads the checked-in TOML and uses SymPy to
verify that shape directly from the active configuration.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib
from typing import Any

from sympy import factorint, isprime, prevprime


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "runner" / "modexp_runner_config.toml"


def _config_int(value: object, *, owner: str) -> int:
    """Convert a runner-config scalar or byte list into one big-endian integer."""

    if isinstance(value, int):
        return value
    if isinstance(value, list) and all(isinstance(item, int) for item in value):
        result = 0
        for byte in value:
            if byte < 0 or byte > 0xFF:
                raise ValueError(f"{owner} contains non-byte value {byte!r}")
            result = (result << 8) | byte
        return result
    raise ValueError(f"{owner} must be an integer or byte list, got {type(value).__name__}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _prove_no_prime_between(lower: int, upper: int, *, owner: str) -> int:
    """Factor every odd candidate in (lower, upper] to witness no missed prime."""

    checked = 0
    first_candidate = upper if upper % 2 else upper - 1
    for candidate in range(first_candidate, lower, -2):
        factors = factorint(candidate)
        if len(factors) == 1 and next(iter(factors.values())) == 1:
            raise ValueError(f"{owner}: unexpected prime candidate 0x{candidate:x}")
        checked += 1
    return checked


def _preset_sym_size(name: str, preset: dict[str, Any]) -> int:
    macros = preset.get("macros")
    if not isinstance(macros, dict):
        raise ValueError(f"{name}: missing macros table")
    sym_size = macros.get("SYM_SIZE")
    if not isinstance(sym_size, int) or sym_size <= 0:
        raise ValueError(f"{name}: SYM_SIZE must be a positive integer")
    return sym_size


def _validate_preset(name: str, preset: dict[str, Any]) -> str:
    macros = preset.get("macros")
    vars_table = preset.get("vars")
    abacus_secrets = preset.get("abacus_secrets")
    _require(isinstance(macros, dict), f"{name}: missing macros table")
    _require(isinstance(vars_table, dict), f"{name}: missing vars table")
    _require(isinstance(abacus_secrets, dict), f"{name}: missing abacus_secrets table")

    sym_size = _preset_sym_size(name, preset)

    base = _config_int(vars_table.get("base_buf"), owner=f"{name}.vars.base_buf")
    modulus = _config_int(vars_table.get("mod_buf"), owner=f"{name}.vars.mod_buf")
    exponent = _config_int(abacus_secrets.get("exp_buf"), owner=f"{name}.abacus_secrets.exp_buf")

    max_value = (1 << (8 * sym_size)) - 1
    _require(0 <= base <= max_value, f"{name}: base_buf does not fit in {sym_size} byte(s)")
    _require(0 <= modulus <= max_value, f"{name}: mod_buf does not fit in {sym_size} byte(s)")
    _require(0 <= exponent <= max_value, f"{name}: exp_buf does not fit in {sym_size} byte(s)")

    _require(isprime(base), f"{name}: base_buf 0x{base:x} is not prime")
    _require(base <= 0xFF, f"{name}: base_buf 0x{base:x} is prime but not a small one-byte prime")
    _require(isprime(modulus), f"{name}: mod_buf 0x{modulus:x} is not prime")
    _require(isprime(exponent), f"{name}: exp_buf 0x{exponent:x} is not prime")

    largest_prime = int(prevprime(max_value + 1))
    second_largest_prime = int(prevprime(largest_prime))
    _require(modulus == largest_prime, f"{name}: mod_buf 0x{modulus:x} is not largest prime 0x{largest_prime:x}")
    _require(
        exponent == second_largest_prime,
        f"{name}: exp_buf 0x{exponent:x} is not second largest prime 0x{second_largest_prime:x}",
    )

    larger_modulus_candidates = _prove_no_prime_between(modulus, max_value, owner=f"{name}.mod_buf")
    larger_exponent_candidates = _prove_no_prime_between(exponent, modulus - 1, owner=f"{name}.exp_buf")

    return (
        f"{name}: base=0x{base:x} prime; "
        f"mod=0x{modulus:x} largest {sym_size}-byte prime; "
        f"exp=0x{exponent:x} second largest {sym_size}-byte prime; "
        f"factored {larger_modulus_candidates + larger_exponent_candidates} intervening odd composite(s)"
    )


def validate_config(config_path: Path) -> list[str]:
    """Validate all modular-exponentiation presets in one runner config."""

    with config_path.open("rb") as handle:
        config = tomllib.load(handle)

    presets = config.get("presets")
    if not isinstance(presets, dict):
        raise ValueError(f"{config_path} is missing a presets table")

    messages: list[str] = []
    preset_items: list[tuple[str, dict[str, Any]]] = []
    for name, preset in presets.items():
        if not isinstance(preset, dict):
            raise ValueError(f"preset {name!r} must be a table")
        preset_items.append((name, preset))

    for name, preset in sorted(
        preset_items,
        key=lambda item: (_preset_sym_size(item[0], item[1]), item[0]),
    ):
        messages.append(_validate_preset(name, preset))
    return messages


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and validate modexp defaults with SymPy.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Runner config to validate. Defaults to {DEFAULT_CONFIG.relative_to(REPO_ROOT)}.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = args.config if args.config.is_absolute() else REPO_ROOT / args.config

    try:
        messages = validate_config(config_path)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    for message in messages:
        print(message)
    print(f"Validated {len(messages)} preset(s) in {_display_path(config_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())