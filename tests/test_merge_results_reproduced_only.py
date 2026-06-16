#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from tools.postprocess import merge_json_runs_by_experiment, merge_results
from tools.shared.configuration_metadata import write_run_metadata


class MergeResultsReproducedOnlyTest(unittest.TestCase):
    def _run_metadata(self, tool_name: str) -> dict[str, object]:
        return {
            "source_column_prefix": tool_name,
            "tool_family": tool_name,
            "searcher": "default",
            "sym_size": "all",
            "cv_model": "default",
        }

    def _case_metadata(self, suffix: str, library_key: str) -> dict[str, object]:
        return {
            "source_column_suffix": suffix,
            "public_mode": suffix,
            "sliced": False,
            "library_key": library_key,
        }

    def _write_run_metadata(self, root: Path, run_names: tuple[str, ...]) -> None:
        write_run_metadata(
            root,
            {run_name: self._run_metadata(run_name) for run_name in run_names},
        )

    def _write_json(
        self,
        path: Path,
        rows: list[dict[str, object]],
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {"data": rows}
        if metadata is not None:
            payload["metadata"] = metadata
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _read_json_rows(self, path: Path) -> list[dict[str, object]]:
        return json.loads(path.read_text(encoding="utf-8"))["data"]

    def test_merge_json_runs_keeps_all_positives_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(
                root / "0" / "toy_fix_pub.json",
                [
                    {
                        "library": "toy",
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "non_ct_time": 4.0,
                        "reproduced_status": "success",
                    }
                ],
            )
            self._write_json(
                root / "1" / "toy_fix_pub.json",
                [
                    {
                        "library": "toy",
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "non_ct_time": 100.0,
                        "reproduced_status": "not_reproduced",
                    }
                ],
            )

            merge_json_runs_by_experiment.main([str(root)])
            merged_rows = self._read_json_rows(root / "toy_fix_pub.json")

            self.assertEqual(len(merged_rows), 1)
            self.assertEqual(merged_rows[0]["reproduced_status"], {"not_reproduced": 1, "success": 1})
            self.assertTrue(math.isclose(merged_rows[0]["non_ct_time"], 20.0, rel_tol=1e-9))

    def test_merge_json_runs_preserves_kind_and_keeps_kinds_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_json(
                root / "0" / "toy_fix_pub.json",
                [
                    {
                        "library": "toy",
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "kind": "branch",
                        "non_ct_time": 4.0,
                        "reproduced_status": "success",
                    },
                    {
                        "library": "toy",
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "kind": "memory",
                        "non_ct_time": 6.0,
                        "reproduced_status": "success",
                    },
                ],
            )

            merge_json_runs_by_experiment.main([str(root)])
            merged_rows = self._read_json_rows(root / "toy_fix_pub.json")

            self.assertEqual(
                merged_rows,
                [
                    {
                        "library": "toy",
                        "filename": "toy.c",
                        "line": 10,
                        "non_ct_time": 4.0,
                        "code": None,
                        "counterexamples": None,
                        "reproduced_status": {"success": 1},
                        "column": 2,
                        "kind": "branch",
                    },
                    {
                        "library": "toy",
                        "filename": "toy.c",
                        "line": 10,
                        "non_ct_time": 6.0,
                        "code": None,
                        "counterexamples": None,
                        "reproduced_status": {"success": 1},
                        "column": 2,
                        "kind": "memory",
                    },
                ],
            )

    def test_merge_results_requires_reproduced_success_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_run_metadata(root, ("klee_cf",))
            self._write_json(
                root / "klee_cf" / "toy_fix_pub.json",
                [
                    {
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "non_ct_time": 4.0,
                        "reproduced_status": {"success": 1, "not_reproduced": 1},
                    },
                    {
                        "filename": "toy.c",
                        "line": 20,
                        "column": 4,
                        "non_ct_time": 7.0,
                        "reproduced_status": {"not_reproduced": 2},
                    },
                ],
                metadata=self._case_metadata("fix_pub", "toy"),
            )

            _, by_col, _ = merge_results.merge_runs(str(root))
            self.assertEqual(
                by_col,
                {
                    "klee_cf_fix_pub": {
                        ("toy", "toy.c", 10, 2, None): 4.0,
                    }
                },
            )

    def test_merge_results_can_keep_all_positives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_run_metadata(root, ("klee_cf",))
            self._write_json(
                root / "klee_cf" / "toy_fix_pub.json",
                [
                    {
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "non_ct_time": 4.0,
                        "reproduced_status": {"success": 1, "not_reproduced": 1},
                    },
                    {
                        "filename": "toy.c",
                        "line": 20,
                        "column": 4,
                        "non_ct_time": 7.0,
                        "reproduced_status": {"not_reproduced": 2},
                    },
                ],
                metadata=self._case_metadata("fix_pub", "toy"),
            )

            _, by_col, _ = merge_results.merge_runs(str(root), all_positives=True)
            self.assertEqual(
                by_col,
                {
                    "klee_cf_fix_pub": {
                        ("toy", "toy.c", 10, 2, None): 4.0,
                        ("toy", "toy.c", 20, 4, None): 7.0,
                    }
                },
            )

    def test_merge_results_keeps_branch_and_memory_rows_distinct_in_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_path = root / "merged.csv"
            self._write_run_metadata(root, ("klee_cf",))
            self._write_json(
                root / "klee_cf" / "toy_fix_pub.json",
                [
                    {
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "kind": "branch",
                        "non_ct_time": 4.0,
                        "reproduced_status": {"success": 1},
                    },
                    {
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "kind": "memory",
                        "non_ct_time": 6.0,
                        "reproduced_status": {"success": 1},
                    },
                ],
                metadata=self._case_metadata("fix_pub", "toy"),
            )

            ordered_columns, by_col, column_metadata = merge_results.merge_runs(str(root))
            row_count = merge_results.write_csv(
                str(output_path),
                ordered_columns,
                by_col,
                column_metadata,
            )

            self.assertEqual(row_count, 2)
            self.assertEqual(
                output_path.read_text(encoding="utf-8").splitlines(),
                [
                    "library,file,line,column,kind,klee_cf_fix_pub",
                    "toy,toy.c,10,2,branch,4.00",
                    "toy,toy.c,10,2,memory,6.00",
                ],
            )

    def test_merge_results_ignores_non_run_subdirectories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "aggregated_exploration").mkdir(parents=True, exist_ok=True)
            self._write_run_metadata(root, ("klee_cf",))
            self._write_json(
                root / "klee_cf" / "toy_fix_pub.json",
                [
                    {
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "non_ct_time": 4.0,
                        "reproduced_status": {"success": 1},
                    },
                ],
                metadata=self._case_metadata("fix_pub", "toy"),
            )

            ordered_columns, by_col, _ = merge_results.merge_runs(str(root))

            self.assertEqual(ordered_columns, ["klee_cf_fix_pub"])
            self.assertEqual(
                by_col,
                {
                    "klee_cf_fix_pub": {
                        ("toy", "toy.c", 10, 2, None): 4.0,
                    }
                },
            )

    def test_merge_results_reports_stale_outputs_when_payload_metadata_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_run_metadata(root, ("klee_cf",))
            self._write_json(
                root / "klee_cf" / "toy_fix_pub.json",
                [
                    {
                        "filename": "toy.c",
                        "line": 10,
                        "column": 2,
                        "non_ct_time": 4.0,
                        "reproduced_status": {"success": 1},
                    },
                ],
            )

            with self.assertRaises(SystemExit) as raised:
                merge_results.merge_runs(str(root))

            self.assertIn("payload metadata is missing", str(raised.exception))
            self.assertIn("predates the metadata-aware experiment runners", str(raised.exception))



if __name__ == "__main__":
    unittest.main()