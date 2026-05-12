#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.shared.common import load_combined_json, save_combined_json


class CommonCombinedJsonTest(unittest.TestCase):
    def test_round_trip_preserves_top_level_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            output_path = root / "output.json"
            input_path.write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "library": "toy",
                                "filename": "toy.c",
                                "line": 10,
                                "non_ct_time": 1.0,
                                "reproduced_status": "not_reproduced",
                            }
                        ],
                        "dtypes": {
                            "library": "object",
                            "filename": "object",
                            "line": "int64",
                            "non_ct_time": "float64",
                            "reproduced_status": "object",
                        },
                        "metadata": {
                            "library_key": "toy",
                            "public_mode": "fix_pub",
                            "source_column_suffix": "fix_pub",
                            "sliced": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            dataframe = load_combined_json(str(input_path))
            save_combined_json(dataframe, str(output_path))

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["metadata"],
                {
                    "library_key": "toy",
                    "public_mode": "fix_pub",
                    "source_column_suffix": "fix_pub",
                    "sliced": False,
                },
            )


if __name__ == "__main__":
    unittest.main()