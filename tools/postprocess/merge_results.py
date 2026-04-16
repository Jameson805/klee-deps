#!/usr/bin/env python3

import argparse
import csv
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Set, Tuple


Location = Tuple[str, str, int, Optional[int]]  # (library, file, line, column)


def column_and_library_from_json_filename(name: str, run_name: str, sliced_only: bool) -> Optional[Tuple[str, str]]:
	"""Return (column_name, library) for one top-level JSON file, or None if filtered out."""
	lower = name.lower()
	if not lower.endswith(".json"):
		return None

	stem = os.path.splitext(lower)[0]
	is_sliced = "_sliced" in stem
	if sliced_only != is_sliced:
		return None

	if stem.endswith("_branch"):
		stem = stem[: -len("_branch")]
	elif stem.endswith("_memory"):
		stem = stem[: -len("_memory")]

	if stem.endswith("_sliced"):
		stem = stem[: -len("_sliced")]

	if stem.startswith("openssl_"):
		rest = stem[len("openssl_") :]
		algos = ["mont_consttime", "mont_word", "recp", "mont"]
		library = "openssl"
		for algo in algos:
			if rest == algo or rest.startswith(algo + "_"):
				library = f"openssl_{algo}"
				break
	else:
		library = stem.split("_", 1)[0]

	if stem == library:
		option = "all"
	elif stem.startswith(library + "_"):
		option = stem[len(library) + 1 :] or "all"
	else:
		parts = stem.split("_", 1)
		option = parts[1] if len(parts) == 2 and parts[1] else "all"

	prefix = f"{run_name}_sliced" if sliced_only else run_name
	return f"{prefix}_{option}", library


_column_and_library_from_json_filename = column_and_library_from_json_filename


def _to_float(value) -> Optional[float]:
	if value is None:
		return None
	try:
		f = float(value)
	except (TypeError, ValueError):
		return None
	if not math.isfinite(f):
		return None
	return f


def _basename_only(path_value: str) -> str:
	# Normalize both Unix and Windows-style separators, then keep only the last path part.
	return os.path.basename(path_value.replace("\\", "/"))


def _load_violations_from_json(path: str, library: str) -> Dict[Location, float]:
	"""Return mapping (library,file,line,column) -> non_ct_time.

	If the same location appears multiple times in the file, keeps the maximum non_ct_time.
	"""
	with open(path, "r", encoding="utf-8") as f:
		payload = json.load(f)
	rows = payload.get("data")
	if not isinstance(rows, list):
		return {}

	out: Dict[Location, float] = {}
	for row in rows:
		if not isinstance(row, dict):
			continue
		non_ct_time = _to_float(row.get("non_ct_time"))
		if non_ct_time is None:
			continue

		filename = row.get("filename")
		line = row.get("line")
		column = row.get("column")
		if not isinstance(filename, str) or filename == "":
			continue
		filename = _basename_only(filename)
		if filename == "":
			continue
		try:
			line_i = int(line)
		except (TypeError, ValueError):
			continue

		col_i: Optional[int]
		try:
			col_i = int(column)
		except (TypeError, ValueError):
			# Missing/invalid column is treated as wildcard for this line.
			col_i = None
		key: Location = (library, filename, line_i, col_i)
		prev = out.get(key)
		out[key] = non_ct_time if prev is None else max(prev, non_ct_time)
	return out


def merge_runs(root_dir: str, *, sliced_only: bool = False) -> Tuple[List[str], Dict[str, Dict[Location, float]]]:
	"""Scan root_dir/* runs and return (ordered_columns, data_by_column).

	If sliced_only is False (default), only non-sliced JSON files are considered.
	If sliced_only is True, only sliced JSON files are considered.

	Each selected JSON file contributes to a separate CSV column named:
	- non-sliced:  <run>_<option>
	- sliced:      <run>_sliced_<option>
	where <option> is derived from the JSON filename stem.
	"""
	if not os.path.isdir(root_dir):
		raise SystemExit(f"Input '{root_dir}' is not a directory")

	run_names = sorted(
		[d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
	)

	ordered_columns: List[str] = []
	by_col: Dict[str, Dict[Location, float]] = {}

	for run_name in run_names:
		run_dir = os.path.join(root_dir, run_name)
		for file in sorted(os.listdir(run_dir)):
			path = os.path.join(run_dir, file)
			if not os.path.isfile(path):
				continue

			resolved = column_and_library_from_json_filename(file, run_name, sliced_only)
			if resolved is None:
				continue
			col_name, library = resolved

			if col_name not in by_col:
				ordered_columns.append(col_name)
				by_col[col_name] = {}

			violations = _load_violations_from_json(path, library)
			if not violations:
				continue
			col_map = by_col[col_name]
			for loc, t in violations.items():
				prev = col_map.get(loc)
				col_map[loc] = t if prev is None else max(prev, t)

	return ordered_columns, by_col


def write_csv(
	output_path: str,
	ordered_columns: Sequence[str],
	by_col: Dict[str, Dict[Location, float]],
) -> int:
	all_locations: Set[Location] = set()
	wildcard_locations: Set[Tuple[str, str, int]] = set()

	for col in ordered_columns:
		for library, filename, line, col_i in by_col.get(col, {}).keys():
			if col_i is None:
				wildcard_locations.add((library, filename, line))
			else:
				all_locations.add((library, filename, line, col_i))

	# If a line has only wildcard entries across all experiments, emit one synthetic row with column 0.
	concrete_lines = {(lib, file, line) for lib, file, line, _ in all_locations}
	for lib, file, line in wildcard_locations:
		if (lib, file, line) not in concrete_lines:
			all_locations.add((lib, file, line, 0))

	rows = sorted(all_locations, key=lambda x: (x[0], x[1], x[2], x[3] if x[3] is not None else -1))

	os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
	with open(output_path, "w", newline="", encoding="utf-8") as f:
		w = csv.writer(f)
		w.writerow(["library", "file", "line", "column", *ordered_columns])
		for library, filename, line, col in rows:
			row_out: List[str] = [library, filename, str(line), str(col if col is not None else "")]
			for exp in ordered_columns:
				exp_map = by_col.get(exp, {})
				val = exp_map.get((library, filename, line, col))
				if val is None:
					# Fallback to wildcard (missing-column) value for same line.
					val = exp_map.get((library, filename, line, None))
				row_out.append("" if val is None else f"{val:.2f}")
			w.writerow(row_out)
	return len(rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
	p = argparse.ArgumentParser(
		description=(
			"Merge per-run top-level JSON results into a single CSV keyed by (library,file,line,column). "
			"A row is included iff at least one experiment reports non_ct_time != null."
		)
	)
	p.add_argument(
		"root_dir",
		help=(
			"Directory containing run subdirectories (e.g. all/a, all/b, ...). "
			"Each run subdirectory should be a copied klee_*_results folder." 
		),
	)
	p.add_argument(
		"-o",
		"--output",
		default="merged_results.csv",
		help="Output CSV path (default: merged_results.csv)",
	)
	p.add_argument(
		"--sliced",
		action="store_true",
		help=(
			"If set, merge ONLY sliced results (columns named <run>_sliced). "
			"If not set, merge ONLY non-sliced results (columns named <run>)."
		),
	)
	args = p.parse_args(argv)

	ordered_columns, by_col = merge_runs(args.root_dir, sliced_only=args.sliced)
	if not ordered_columns:
		mode = "sliced" if args.sliced else "non-sliced"
		raise SystemExit(f"No {mode} top-level result JSON files found under '{args.root_dir}'")

	row_count = write_csv(args.output, ordered_columns, by_col)
	print(f"Wrote {row_count} rows to {args.output}")
	print(f"Experiments: {', '.join(ordered_columns)}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
