#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_MODULE = "tools.postprocess.summarize_reproduction_status"


class SummarizeReproductionStatusByLibraryTest(unittest.TestCase):
    maxDiff = None

    def _write_json(self, path: Path, rows: list[dict[str, object]]) -> None:
        path.write_text(json.dumps({"data": rows}), encoding="utf-8")

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_grouped_by_library_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            for run_name in ("klee_cf", "binsec", "klee_eager"):
                (root / run_name).mkdir(parents=True, exist_ok=True)

            self._write_json(
                root / "klee_cf" / "mbedtls_rand_path_dfs_4_fix_pub.json",
                [
                    {
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                    {
                        "filename": "mbedtls.c",
                        "line": 20,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                ],
            )
            self._write_json(
                root / "klee_cf" / "bearssl_rand_path_dfs_4_fix_pub.json",
                [
                    {
                        "filename": "bearssl.c",
                        "line": 10,
                        "column": 1,
                        "reproduced_status": "timeout",
                    },
                ],
            )
            self._write_json(
                root / "binsec" / "mbedtls_16_var_pub.json",
                [
                    {
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                    {
                        "filename": "mbedtls.c",
                        "line": 20,
                        "column": 1,
                        "reproduced_status": "not_reproduced",
                    },
                ],
            )
            self._write_json(
                root / "binsec" / "bearssl_16_var_pub.json",
                [
                    {
                        "filename": "bearssl.c",
                        "line": 10,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                    {
                        "filename": "bearssl.c",
                        "line": 20,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                ],
            )
            self._write_json(
                root / "klee_eager" / "mbedtls_rand_path_dfs_4_fix_pub.json",
                [
                    {
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                ],
            )
            self._write_json(
                root / "klee_eager" / "bearssl_rand_path_dfs_4_fix_pub.json",
                [
                    {
                        "filename": "bearssl.c",
                        "line": 20,
                        "column": 1,
                        "reproduced_status": "success",
                    },
                ],
            )

            filter_csv = tmp_path / "filter.csv"
            filter_csv.write_text(
                "library,file,line_start,line_end\n"
                "mbedtls,mbedtls.c,10,20\n"
                "bearssl,bearssl.c,10,20\n",
                encoding="utf-8",
            )

            selection_csv = tmp_path / "selection.csv"
            selection_csv.write_text(
                "comparison_tool,source_column,display_label,plot_groups\n"
                "binsec,binsec_16_var_pub,BINSEC,external\n"
                "klee_cf,klee_cf_rand_path_dfs_4_fix_pub,KLEE-CF,internal|external\n"
                "klee_eager,klee_eager_rand_path_dfs_4_fix_pub,KLEE-Eager,internal\n",
                encoding="utf-8",
            )

            summary_csv = tmp_path / "summary.csv"
            by_library_prefix = tmp_path / "by_library"
            command = [
                sys.executable,
                "-m",
                SCRIPT_MODULE,
                str(root),
                "-f",
                str(filter_csv),
                "-o",
                str(summary_csv),
                "--selection-csv",
                str(selection_csv),
                "--by-library-selection-tables",
                "--by-library-output-prefix",
                str(by_library_prefix),
            ]
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}",
            )

            summary_rows = self._read_csv(summary_csv)
            self.assertEqual(
                summary_rows,
                [
                    {
                        "configuration": "binsec_16_var_pub",
                        "configuration_label": "sym=16, mode=var_pub",
                        "comparison_tool": "binsec",
                        "tool_family": "binsec",
                        "sliced": "False",
                        "searcher": "default",
                        "sym_size": "16",
                        "public_mode": "var_pub",
                        "concretization_policy": "default",
                        "success": "3",
                        "timeout": "0",
                        "identical_trace": "0",
                        "location_mismatch": "0",
                        "not_reproduced": "1",
                        "inconsistent_across_repetitions": "0",
                        "total_filtered_positives": "4",
                    },
                    {
                        "configuration": "klee_cf_rand_path_dfs_4_fix_pub",
                        "configuration_label": "search=rand_path_dfs, sym=4, mode=fix_pub",
                        "comparison_tool": "klee_cf",
                        "tool_family": "klee_cf",
                        "sliced": "False",
                        "searcher": "rand_path_dfs",
                        "sym_size": "4",
                        "public_mode": "fix_pub",
                        "concretization_policy": "default",
                        "success": "2",
                        "timeout": "1",
                        "identical_trace": "0",
                        "location_mismatch": "0",
                        "not_reproduced": "0",
                        "inconsistent_across_repetitions": "0",
                        "total_filtered_positives": "3",
                    },
                    {
                        "configuration": "klee_eager_rand_path_dfs_4_fix_pub",
                        "configuration_label": "search=rand_path_dfs, sym=4, mode=fix_pub",
                        "comparison_tool": "klee_eager",
                        "tool_family": "klee_eager",
                        "sliced": "False",
                        "searcher": "rand_path_dfs",
                        "sym_size": "4",
                        "public_mode": "fix_pub",
                        "concretization_policy": "default",
                        "success": "2",
                        "timeout": "0",
                        "identical_trace": "0",
                        "location_mismatch": "0",
                        "not_reproduced": "0",
                        "inconsistent_across_repetitions": "0",
                        "total_filtered_positives": "2",
                    },
                ],
            )

            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "bearssl",
                        "KLEE-CF": "0",
                        "KLEE-Eager": "1",
                        "BINSEC": "2",
                    },
                    {
                        "library": "mbedtls",
                        "KLEE-CF": "2",
                        "KLEE-Eager": "1",
                        "BINSEC": "1",
                    },
                ],
            )

            combined_latex = (tmp_path / "by_library.tex").read_text(
                encoding="utf-8"
            )
            self.assertIn(r"\begin{NiceTabular}{lr|r|r}", combined_latex)
            self.assertIn("library & KLEE-CF & KLEE-Eager & BINSEC \\\\", combined_latex)
            self.assertIn("mbedtls & 2 & 1 & 1 \\\\", combined_latex)


if __name__ == "__main__":
    unittest.main()