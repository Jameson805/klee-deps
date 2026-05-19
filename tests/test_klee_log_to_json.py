#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.converters.klee_log_to_json import load_preaggregated_from_messages


class KleeLogToJsonTest(unittest.TestCase):
    def test_duplicate_inst_id_uses_later_aggregated_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            messages_path = Path(tmp) / "messages.txt"
            messages_path.write_text(
                "\n".join(
                    [
                        'KLEE: [BRANCH] {"col":11,"filename":"mpi-pow.c","inst_id":52047,"line":617,"non_ct":true,"time":0.830025479}',
                        'KLEE: [BRANCH] {"col":11,"filename":"mpi-pow.c","inst_id":52047,"line":617,"non_ct_count":4,"non_ct_time":0.830025479,"visit_count":4,"visit_time":0.830025479}',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            rows = load_preaggregated_from_messages(str(messages_path), "BRANCH")

            self.assertEqual(
                rows,
                [
                    {
                        "filename": "mpi-pow.c",
                        "line": 617,
                        "column": 11,
                        "inst_id": 52047,
                        "visit_count": 4,
                        "non_ct_count": 4,
                        "visit_time": 0.830025479,
                        "non_ct_time": 0.830025479,
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()