#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from tools.postprocess.merge_csv_by_location import merge_on_location


class MergeCsvByLocationTest(unittest.TestCase):
    def _write_csv(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")

    def test_merge_distinguishes_kind_for_same_source_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left.csv"
            right = root / "right.csv"
            output = root / "merged.csv"

            self._write_csv(
                left,
                "library,file,line,column,kind,left_metric\n"
                "toy,toy.c,10,2,branch,1.0\n"
                "toy,toy.c,10,2,memory,2.0\n",
            )
            self._write_csv(
                right,
                "library,file,line,column,kind,right_metric\n"
                "toy,toy.c,10,2,branch,3.0\n"
                "toy,toy.c,10,2,memory,4.0\n",
            )

            merge_on_location(str(left), str(right), str(output))
            merged = pd.read_csv(output)

            self.assertEqual(merged[["library", "file", "line", "column", "kind"]].to_dict("records"), [
                {"library": "toy", "file": "toy.c", "line": 10, "column": 2, "kind": "branch"},
                {"library": "toy", "file": "toy.c", "line": 10, "column": 2, "kind": "memory"},
            ])

    def test_merge_backfills_missing_kind_column_for_legacy_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "left.csv"
            right = root / "right.csv"
            output = root / "merged.csv"

            self._write_csv(
                left,
                "library,file,line,column,left_metric\n"
                "toy,toy.c,10,2,1.0\n",
            )
            self._write_csv(
                right,
                "library,file,line,column,right_metric\n"
                "toy,toy.c,10,2,3.0\n",
            )

            merge_on_location(str(left), str(right), str(output))
            merged = pd.read_csv(output)

            self.assertIn("kind", merged.columns)
            self.assertEqual(len(merged), 1)
            self.assertTrue(pd.isna(merged.loc[0, "kind"]) or merged.loc[0, "kind"] == "")


if __name__ == "__main__":
    unittest.main()