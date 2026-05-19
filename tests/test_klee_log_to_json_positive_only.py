#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.converters.klee_log_to_json import convert_klee_output


class KleeLogToJsonPositiveOnlyTest(unittest.TestCase):
    def test_convert_keeps_only_positive_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            messages_path = root / "messages.txt"
            messages_path.write_text(
                "\n".join(
                    [
                        'KLEE: [BRANCH] {"col":11,"filename":"mpi-pow.c","inst_id":52047,"line":617,"non_ct_count":4,"non_ct_time":0.830025479,"visit_count":4,"visit_time":0.830025479}',
                        'KLEE: [BRANCH] {"col":5,"filename":"mpi-pow.c","inst_id":52200,"line":567,"non_ct_count":0,"non_ct_time":null,"visit_count":2,"visit_time":0.592257991}',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            payload = convert_klee_output(
                kind="branch",
                klee_output=str(root),
                library="libgcrypt",
            )

            self.assertEqual(len(payload["data"]), 1)
            self.assertEqual(payload["data"][0]["inst_id"], 52047)
            self.assertEqual(payload["data"][0]["non_ct_count"], 4)


if __name__ == "__main__":
    unittest.main()