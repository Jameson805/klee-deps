#!/usr/bin/env python3

import argparse
import bisect
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    from elftools.elf.elffile import ELFFile
except ImportError:  # pragma: no cover - runtime dependency may be optional in some flows
    ELFFile = None

# Per-executable cache: exe -> preprocessed DWARF lookup data
_ADDR_CACHE: Dict[str, Dict[str, Any]] = {}

AddrInfo = Tuple[str, int, int]
AddrInfoContext = Tuple[str, int, int, Optional[int], Optional[int]]


def _decode_dwarf_str(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _resolve_line_program_path(comp_dir: str, line_prog: Any, file_index: int) -> Optional[str]:
    if file_index < 0:
        return None

    file_entries = line_prog.header["file_entry"]
    entry_index = file_index - 1
    if file_index == 0:
        entry_index = 0
    if entry_index >= len(file_entries):
        return None

    file_entry = file_entries[entry_index]
    name = _decode_dwarf_str(file_entry.name)
    if os.path.isabs(name):
        return os.path.normpath(name)

    dir_index = file_entry.dir_index or 0
    if dir_index > 0:
        include_dirs = line_prog.header.get("include_directory", ())
        include_index = dir_index - 1
        if include_index < len(include_dirs):
            directory = _decode_dwarf_str(include_dirs[include_index])
            if os.path.isabs(directory):
                return os.path.normpath(os.path.join(directory, name))
            return os.path.normpath(os.path.join(comp_dir, directory, name))

    return os.path.normpath(os.path.join(comp_dir, name))


def _ensure_addr_cache(exe: str) -> None:
    # Build cache on first use
    if exe in _ADDR_CACHE:
        return

    with open(exe, "rb") as stream:
        elffile = ELFFile(stream)
        if not elffile.has_dwarf_info():
            _ADDR_CACHE[exe] = {"has_dwarf": False}
            return
        dwarfinfo = elffile.get_dwarf_info()

        # addr -> (path, line, col)
        addr_map: Dict[int, AddrInfo] = {}
        line_columns: Dict[Tuple[str, int], set[int]] = {}

        for cu in dwarfinfo.iter_CUs():
            top = cu.get_top_DIE()
            comp_dir_attr = top.attributes.get("DW_AT_comp_dir")
            comp_dir = _decode_dwarf_str(comp_dir_attr.value) if comp_dir_attr else ""
            line_prog = dwarfinfo.line_program_for_CU(cu)
            if line_prog is None:
                continue
            for entry in line_prog.get_entries():
                state = entry.state
                if state is None:
                    continue
                if state.end_sequence or not state.line:
                    continue
                path = _resolve_line_program_path(comp_dir, line_prog, state.file)
                if path is None:
                    continue
                line = int(state.line)
                column = int(state.column or 0)
                addr_map[state.address] = (path, line, column)
                key = (path, line)
                if key not in line_columns:
                    line_columns[key] = set()
                line_columns[key].add(column)

        addrs = sorted(addr_map.keys())

        _ADDR_CACHE[exe] = {
            "has_dwarf": True,
            "addr_map": addr_map,
            "addrs": addrs,
            "line_columns": {
                key: sorted(columns)
                for key, columns in line_columns.items()
            },
        }


def get_addr_info_context(exe: str, address: int) -> Optional[AddrInfoContext]:
    """Resolve an address to a source location plus neighboring DWARF columns."""
    if ELFFile is None:
        return None

    _ensure_addr_cache(exe)

    cache = _ADDR_CACHE[exe]
    if not cache.get("has_dwarf"):
        return None

    addr_map: Dict[int, AddrInfo] = cache["addr_map"]
    if not addr_map:
        return None

    # Nearest-previous address (addr2line behavior)
    addrs = cache["addrs"]
    idx = bisect.bisect_right(addrs, address) - 1
    if idx < 0:
        return None

    path, line, column = addr_map[addrs[idx]]
    columns: List[int] = cache["line_columns"].get((path, line), [])
    col_idx = bisect.bisect_left(columns, column)

    previous_column = None
    next_column = None
    if col_idx < len(columns) and columns[col_idx] == column:
        if col_idx > 0:
            previous_column = columns[col_idx - 1]
        if col_idx + 1 < len(columns):
            next_column = columns[col_idx + 1]
    else:
        if col_idx > 0:
            previous_column = columns[col_idx - 1]
        if col_idx < len(columns):
            next_column = columns[col_idx]

    return path, line, column, previous_column, next_column


def get_addr_info(exe: str, address: int) -> Optional[AddrInfo]:
    """Resolve an address to a source location using cached DWARF line data."""
    info = get_addr_info_context(exe, address)
    if info is None:
        return None
    return info[:3]


if __name__ == '__main__':
    if ELFFile is None:
        print("Error: pyelftools is required for addrinfo CLI usage. Install with: pip install pyelftools")
        exit(2)

    parser = argparse.ArgumentParser(
        description="Find the source file, line, and column for a given instruction address."
    )
    parser.add_argument(
        'executable_path',
        help="The path to the ELF executable file."
    )
    parser.add_argument(
        'address',
        help="The instruction address in hexadecimal format (e.g., 0x40114b)."
    )

    args = parser.parse_args()

    try:
        # Convert the hex string from the command line to an integer.
        address_int = int(args.address, 16)
    except ValueError:
        print(f"Error: Invalid address format. Please use a hexadecimal string like '0x123abc'.")
        exit(1)

    info = get_addr_info(args.executable_path, address_int)

    if info:
        filename, line, column = info
        print(f"{filename}:{line}:{column}")
    else:
        print(f"Could not find debug info for address {args.address} in '{args.executable_path}'.")
        exit(1)
