#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.shared.configuration_metadata import write_run_metadata


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_MODULE = "tools.postprocess.summarize_reproduction_status"


class SummarizeReproductionStatusByLibraryTest(unittest.TestCase):
    maxDiff = None

    def _run_metadata(self, tool_name: str) -> dict[str, object]:
        return {
            "source_column_prefix": tool_name,
            "tool_family": tool_name,
            "searcher": "default",
            "sym_size": "all",
            "cv_model": "default",
        }

    def _case_metadata(
        self,
        suffix: str,
        library_key: str,
        *,
        target_key: str | None = None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "source_column_suffix": suffix,
            "public_mode": suffix,
            "sliced": False,
            "library_key": library_key,
        }
        if target_key is not None:
            metadata["target_key"] = target_key
        return metadata

    def _write_json(
        self,
        path: Path,
        rows: list[dict[str, object]],
        *,
        metadata: dict[str, object],
    ) -> None:
        path.write_text(json.dumps({"data": rows, "metadata": metadata}), encoding="utf-8")

    def _write_run_metadata(self, root: Path, run_names: tuple[str, ...]) -> None:
        write_run_metadata(
            root,
            {run_name: self._run_metadata(run_name) for run_name in run_names},
        )

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_grouped_by_library_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            for run_name in ("klee_cf", "binsec", "klee_eager"):
                (root / run_name).mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf", "binsec", "klee_eager"))

            self._write_json(
                root / "klee_cf" / "mbedtls_fix_pub.json",
                [
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 20,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "mbedtls", target_key="aes"),
            )
            self._write_json(
                root / "klee_cf" / "bearssl_fix_pub.json",
                [
                    {
                        "library": "bearssl",
                        "filename": "bearssl.c",
                        "line": 10,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "timeout",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "bearssl", target_key="rsa"),
            )
            self._write_json(
                root / "binsec" / "mbedtls_var_pub.json",
                [
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 20,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "not_reproduced",
                    },
                ],
                metadata=self._case_metadata("var_pub", "mbedtls", target_key="aes"),
            )
            self._write_json(
                root / "binsec" / "bearssl_var_pub.json",
                [
                    {
                        "library": "bearssl",
                        "filename": "bearssl.c",
                        "line": 10,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                    {
                        "library": "bearssl",
                        "filename": "bearssl.c",
                        "line": 20,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("var_pub", "bearssl", target_key="rsa"),
            )
            self._write_json(
                root / "klee_eager" / "mbedtls_fix_pub.json",
                [
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "mbedtls", target_key="aes"),
            )
            self._write_json(
                root / "klee_eager" / "bearssl_fix_pub.json",
                [
                    {
                        "library": "bearssl",
                        "filename": "bearssl.c",
                        "line": 20,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "bearssl", target_key="rsa"),
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
                "binsec,binsec_var_pub,BINSEC,external\n"
                "klee_cf,klee_cf_fix_pub,KLEE-CF,internal|external\n"
                "klee_eager,klee_eager_fix_pub,KLEE-Eager,internal\n",
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
                        "configuration": "binsec_var_pub",
                        "configuration_label": "searcher=default, public_mode=var_pub, cv_model=default",
                        "comparison_tool": "binsec",
                        "tool_family": "binsec",
                        "sliced": "False",
                        "searcher": "default",
                        "sym_size": "all",
                        "public_mode": "var_pub",
                        "cv_model": "default",
                        "success": "3",
                        "timeout": "0",
                        "identical_trace": "0",
                        "location_mismatch": "0",
                        "kind_mismatch": "0",
                        "not_reproduced": "1",
                        "inconsistent_across_repetitions": "0",
                        "total_filtered_positives": "4",
                    },
                    {
                        "configuration": "klee_cf_fix_pub",
                        "configuration_label": "searcher=default, public_mode=fix_pub, cv_model=default",
                        "comparison_tool": "klee_cf",
                        "tool_family": "klee_cf",
                        "sliced": "False",
                        "searcher": "default",
                        "sym_size": "all",
                        "public_mode": "fix_pub",
                        "cv_model": "default",
                        "success": "2",
                        "timeout": "1",
                        "identical_trace": "0",
                        "location_mismatch": "0",
                        "kind_mismatch": "0",
                        "not_reproduced": "0",
                        "inconsistent_across_repetitions": "0",
                        "total_filtered_positives": "3",
                    },
                    {
                        "configuration": "klee_eager_fix_pub",
                        "configuration_label": "searcher=default, public_mode=fix_pub, cv_model=default",
                        "comparison_tool": "klee_eager",
                        "tool_family": "klee_eager",
                        "sliced": "False",
                        "searcher": "default",
                        "sym_size": "all",
                        "public_mode": "fix_pub",
                        "cv_model": "default",
                        "success": "2",
                        "timeout": "0",
                        "identical_trace": "0",
                        "location_mismatch": "0",
                        "kind_mismatch": "0",
                        "not_reproduced": "0",
                        "inconsistent_across_repetitions": "0",
                        "total_filtered_positives": "2",
                    },
                ],
            )

            self.assertEqual(
                self._read_csv(tmp_path / "summary_best_of.csv"),
                [
                    {
                        "configuration": "BINSEC",
                        "success": "3",
                        "timeout": "0",
                        "not_reproduced": "1",
                        "total": "4",
                    },
                    {
                        "configuration": "KLEE-CF",
                        "success": "2",
                        "timeout": "1",
                        "not_reproduced": "0",
                        "total": "3",
                    },
                    {
                        "configuration": "KLEE-Eager",
                        "success": "2",
                        "timeout": "0",
                        "not_reproduced": "0",
                        "total": "2",
                    },
                ],
            )

            selected_latex = (tmp_path / "summary_best_of.tex").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                r"configuration & success & timeout & not\_reproduced & total",
                selected_latex,
            )
            self.assertIn("BINSEC & 3 & 0 & 1 & 4 " + "\\\\", selected_latex)
            self.assertIn("KLEE-CF & 2 & 1 & 0 & 3 " + "\\\\", selected_latex)
            self.assertIn("KLEE-Eager & 2 & 0 & 0 & 2 " + "\\\\", selected_latex)

            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "bearssl",
                        "target": "rsa",
                        "KLEE-CF_control_flow": "0",
                        "KLEE-CF_memory": "0",
                        "KLEE-Eager_control_flow": "0",
                        "KLEE-Eager_memory": "1",
                        "BINSEC_control_flow": "1",
                        "BINSEC_memory": "1",
                    },
                    {
                        "library": "mbedtls",
                        "target": "aes",
                        "KLEE-CF_control_flow": "1",
                        "KLEE-CF_memory": "1",
                        "KLEE-Eager_control_flow": "1",
                        "KLEE-Eager_memory": "0",
                        "BINSEC_control_flow": "1",
                        "BINSEC_memory": "0",
                    },
                ],
            )

            combined_latex = (tmp_path / "by_library.tex").read_text(
                encoding="utf-8"
            )
            self.assertIn(r"\begin{NiceTabular}{lr|r|r}", combined_latex)
            self.assertIn(
                "benchmark & KLEE-CF & KLEE-Eager & BINSEC " + "\\\\",
                combined_latex,
            )
            self.assertIn("mbedtls:aes & 1/1 & 1/0 & 1/0 " + "\\\\", combined_latex)
            self.assertIn("bearssl:rsa & 0/0 & 0/1 & 1/1 " + "\\\\", combined_latex)

    def test_by_library_selection_tables_split_same_library_by_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            (root / "klee_cf").mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf",))

            self._write_json(
                root / "klee_cf" / "openssl_default_aes_fix_pub.json",
                [
                    {
                        "library": "openssl",
                        "filename": "aes.c",
                        "line": 10,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "openssl", target_key="aes"),
            )
            self._write_json(
                root / "klee_cf" / "openssl_default_sha_fix_pub.json",
                [
                    {
                        "library": "openssl",
                        "filename": "sha.c",
                        "line": 20,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "openssl", target_key="sha"),
            )

            filter_csv = tmp_path / "filter.csv"
            filter_csv.write_text(
                "library,file,line_start,line_end\n"
                "openssl,aes.c,10,10\n"
                "openssl,sha.c,20,20\n",
                encoding="utf-8",
            )

            selection_csv = tmp_path / "selection.csv"
            selection_csv.write_text(
                "comparison_tool,source_column,display_label\n"
                "klee_cf,klee_cf_fix_pub,klee_cf\n",
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

            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "openssl",
                        "target": "aes",
                        "klee_cf_control_flow": "1",
                        "klee_cf_memory": "0",
                    },
                    {
                        "library": "openssl",
                        "target": "sha",
                        "klee_cf_control_flow": "0",
                        "klee_cf_memory": "1",
                    },
                ],
            )

    def test_target_specific_filter_and_sliced_map_use_legacy_library_target_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            (root / "klee_cf").mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf",))

            self._write_json(
                root / "klee_cf" / "openssl_sliced_mont_fix_pub.json",
                [
                    {
                        "library": "openssl",
                        "filename": "bn_exp.c",
                        "line": 240,
                        "column": 9,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                ],
                metadata={
                    **self._case_metadata("fix_pub", "openssl", target_key="mont"),
                    "sliced": True,
                },
            )

            filter_csv = tmp_path / "filter.csv"
            filter_csv.write_text(
                "library,file,line_start,line_end\n"
                "openssl_mont,bn_exp.c,364,364\n",
                encoding="utf-8",
            )
            sliced_map_csv = tmp_path / "sliced_map.csv"
            sliced_map_csv.write_text(
                "library,file,line,column,file_sliced,line_sliced,column_sliced\n"
                "openssl_mont,bn_exp.c,364,9,bn_exp.c,240,9\n",
                encoding="utf-8",
            )
            selection_csv = tmp_path / "selection.csv"
            selection_csv.write_text(
                "comparison_tool,source_column,display_label\n"
                "klee_cf_sliced,klee_cf_sliced_fix_pub,klee_cf\n",
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
                "--sliced-map",
                str(sliced_map_csv),
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

            self.assertEqual(self._read_csv(summary_csv)[0]["total_filtered_positives"], "1")
            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "openssl",
                        "target": "mont",
                        "klee_cf_control_flow": "1",
                        "klee_cf_memory": "0",
                    },
                ],
            )

    def test_by_library_selection_tables_include_empty_target_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            (root / "klee_cf").mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf",))

            self._write_json(
                root / "klee_cf" / "appliedcryp_default_3way_var_pub.json",
                [],
                metadata=self._case_metadata("var_pub", "appliedcryp", target_key="3way"),
            )
            self._write_json(
                root / "klee_cf" / "appliedcryp_default_des_var_pub.json",
                [
                    {
                        "library": "appliedcryp",
                        "filename": "des.c",
                        "line": 130,
                        "column": 17,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("var_pub", "appliedcryp", target_key="des"),
            )

            filter_csv = tmp_path / "filter.csv"
            filter_csv.write_text(
                "library,file,line_start,line_end\n"
                "appliedcryp,des.c,130,130\n",
                encoding="utf-8",
            )

            selection_csv = tmp_path / "selection.csv"
            selection_csv.write_text(
                "comparison_tool,source_column,display_label\n"
                "klee_cf,klee_cf_var_pub,klee_cf\n",
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

            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "appliedcryp",
                        "target": "3way",
                        "klee_cf_control_flow": "0",
                        "klee_cf_memory": "0",
                    },
                    {
                        "library": "appliedcryp",
                        "target": "des",
                        "klee_cf_control_flow": "1",
                        "klee_cf_memory": "0",
                    },
                ],
            )

            combined_latex = (tmp_path / "by_library.tex").read_text(
                encoding="utf-8"
            )
            self.assertIn("appliedcryp:3way & 0/0 " + "\\\\", combined_latex)
            self.assertIn("appliedcryp:des & 1/0 " + "\\\\", combined_latex)

    def test_by_library_uses_filename_benchmark_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            (root / "klee_cf").mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf",))

            self._write_json(
                root / "klee_cf" / "appliedcryp_3way_fix_pub.json",
                [
                    {
                        "library": "unknown",
                        "filename": "3way.c",
                        "line": 36,
                        "column": 6,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                    {
                        "library": "unknown",
                        "filename": "3way.c",
                        "line": 201,
                        "column": 21,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "appliedcryp_3way"),
            )

            filter_csv = tmp_path / "filter.csv"
            filter_csv.write_text(
                "library,file,line_start,line_end\n"
                "appliedcryp_3way,3way.c,36,36\n"
                "appliedcryp_3way,3way.c,201,201\n",
                encoding="utf-8",
            )

            selection_csv = tmp_path / "selection.csv"
            selection_csv.write_text(
                "comparison_tool,source_column,display_label\n"
                "klee_cf,klee_cf_fix_pub,klee_cf\n",
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

            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "appliedcryp_3way",
                        "target": "",
                        "klee_cf_control_flow": "1",
                        "klee_cf_memory": "1",
                    },
                ],
            )

    def test_automatic_selection_without_selection_csv_prefers_fastest_tie(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "input"
            for run_name in ("klee_cf", "binsec"):
                (root / run_name).mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf", "binsec"))

            self._write_json(
                root / "klee_cf" / "mbedtls_fix_pub.json",
                [
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 10,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("fix_pub", "mbedtls", target_key="aes"),
            )
            self._write_json(
                root / "klee_cf" / "mbedtls_var_pub.json",
                [
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 11,
                        "column": 1,
                        "kind": "branch",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("var_pub", "mbedtls", target_key="aes"),
            )
            self._write_json(
                root / "binsec" / "mbedtls_var_pub.json",
                [
                    {
                        "library": "mbedtls",
                        "filename": "mbedtls.c",
                        "line": 12,
                        "column": 1,
                        "kind": "memory",
                        "reproduced_status": "success",
                    },
                ],
                metadata=self._case_metadata("var_pub", "mbedtls", target_key="aes"),
            )

            filter_csv = tmp_path / "filter.csv"
            filter_csv.write_text(
                "library,file,line_start,line_end\n"
                "mbedtls,mbedtls.c,10,12\n",
                encoding="utf-8",
            )

            merged_csv = root / "merged_results.csv"
            merged_csv.write_text(
                "library,file,line,column,kind,klee_cf_fix_pub,klee_cf_var_pub,binsec_var_pub\n"
                "mbedtls,mbedtls.c,10,1,memory,9.0,,\n"
                "mbedtls,mbedtls.c,11,1,branch,,4.0,\n"
                "mbedtls,mbedtls.c,12,1,memory,,,3.0\n",
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
                "--selected-output",
                str(tmp_path / "summary_best_of.csv"),
                "--selected-latex-output",
                str(tmp_path / "summary_best_of.tex"),
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
            self.assertIn(
                "No --selection-csv provided; using automatically selected best configuration per comparison tool.",
                result.stdout,
            )

            selected_rows = self._read_csv(tmp_path / "summary_best_of.csv")
            selected_by_name = {
                row["configuration"]: row for row in selected_rows
            }
            self.assertEqual(set(selected_by_name), {"Binsec/Rel 2", "CT-Witness"})
            self.assertEqual(selected_by_name["Binsec/Rel 2"]["success"], "1")
            self.assertEqual(selected_by_name["Binsec/Rel 2"]["total"], "1")
            self.assertEqual(selected_by_name["CT-Witness"]["success"], "1")
            self.assertEqual(selected_by_name["CT-Witness"]["total"], "1")

            self.assertEqual(
                self._read_csv(tmp_path / "by_library.csv"),
                [
                    {
                        "library": "mbedtls",
                        "target": "aes",
                        "CT-Witness_control_flow": "1",
                        "CT-Witness_memory": "0",
                        "Binsec/Rel 2_control_flow": "0",
                        "Binsec/Rel 2_memory": "1",
                    },
                ],
            )


if __name__ == "__main__":
    unittest.main()
