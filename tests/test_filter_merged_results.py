#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.postprocess.filter_merged_results import load_filters, location_matches


class FilterMergedResultsTest(unittest.TestCase):
    def _write_filter_csv(self, path: Path, rows: list[str]) -> None:
        path.write_text(
            "library,file,line_start,line_end\n" + "".join(rows),
            encoding="utf-8",
        )

    def test_unlisted_library_passes_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            filter_path = Path(tmp) / "filters.csv"
            self._write_filter_csv(filter_path, ["mbedtls,mbedtls.c,10,20\n", "bearssl,bearssl.c,5,7\n"])

            filters = load_filters(filter_path)

            self.assertTrue(
                location_matches(filters, library="libg", file="des.c", line=99)
            )
            self.assertTrue(
                location_matches(filters, library="mbedtls", file="mbedtls.c", line=15)
            )
            self.assertFalse(
                location_matches(filters, library="mbedtls", file="mbedtls.c", line=25)
            )

    def test_empty_filter_keeps_everything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            filter_path = Path(tmp) / "filters.csv"
            self._write_filter_csv(filter_path, [])

            filters = load_filters(filter_path)

            self.assertTrue(
                location_matches(filters, library="mbedtls", file="mbedtls.c", line=10)
            )
            self.assertTrue(
                location_matches(filters, library="bearssl", file="bearssl.c", line=20)
            )


if __name__ == "__main__":
    unittest.main()