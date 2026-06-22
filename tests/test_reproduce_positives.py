#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.postprocess.reproduce_positives import (
    ReplayResult,
    build_value_input_bytes,
    parse_secret_input_spec,
    reproduce_abacus_json_positives,
    reproduce_input_values,
)


class ReproducePositivesTest(unittest.TestCase):
    def test_reproduce_abacus_json_positives_forwards_pin_root(self) -> None:
        with patch("tools.postprocess.reproduce_positives.mode_abacus_json", return_value=0) as mode_mock:
            rc = reproduce_abacus_json_positives(
                input_json="/tmp/input.json",
                executable="/tmp/replay",
                sym_size=8,
                timeout=123,
                output="/tmp/output.json",
                library="bearssl",
                pin_root="/tmp/pin",
            )

        self.assertEqual(rc, 0)
        self.assertEqual(mode_mock.call_args.kwargs["pin_root"], "/tmp/pin")

    def test_reproduce_input_values_forwards_pin_root(self) -> None:
        with patch("tools.postprocess.reproduce_positives.mode_input_values", return_value=0) as mode_mock:
            rc = reproduce_input_values(
                executable="/tmp/replay",
                secret_spec="secret:4:key=1/2",
                public_spec="public:4:iv=3",
                timeout=123,
                pin_root="/tmp/pin",
            )

        self.assertEqual(rc, 0)
        self.assertEqual(mode_mock.call_args.kwargs["pin_root"], "/tmp/pin")

    def test_abacus_json_ignores_source_column_and_writes_reproduced_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_json = temp_path / "input.json"
            output_json = temp_path / "output.json"
            notes = {
                "secret_layout": [{"name": "skey", "size": 4}],
                "public_layout": [],
            }
            input_json.write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "library": "bearssl",
                                "filename": "aes_big_enc.c",
                                "line": 108,
                                "column": 999,
                                "kind": "memory",
                                "non_ct_time": 1.0,
                                "counterexamples": {"skey": 1, "skey__prime": 2},
                                "reproduced_status": "not_reproduced",
                            }
                        ],
                        "dtypes": {
                            "library": "object",
                            "filename": "object",
                            "line": "Int64",
                            "column": "Int64",
                            "kind": "object",
                            "non_ct_time": "float64",
                            "counterexamples": "object",
                            "reproduced_status": "object",
                        },
                        "notes": notes,
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "tools.postprocess.reproduce_positives.analyze_input_bytes",
                return_value=ReplayResult(
                    culprit_ip=0x1000,
                    resolved_ip=0x1000,
                    location=("/tmp/aes_big_enc.c", 108, 12),
                    divergence_kind="memory",
                ),
            ):
                rc = reproduce_abacus_json_positives(
                    input_json=str(input_json),
                    executable="/tmp/replay",
                    sym_size=4,
                    timeout=123,
                    output=str(output_json),
                    library="bearssl",
                    pin_root="/tmp/pin",
                )

            self.assertEqual(rc, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            row = payload["data"][0]
            self.assertEqual(row["reproduced_status"], "success")
            self.assertEqual(row["column"], 12)
            self.assertEqual(payload["dtypes"]["column"], "Int64")
            self.assertEqual(payload["notes"], notes)

    def test_large_decimal_input_value_exceeds_python_digit_guard(self) -> None:
        set_digit_limit = getattr(sys, "set_int_max_str_digits", None)
        get_digit_limit = getattr(sys, "get_int_max_str_digits", None)
        old_limit = get_digit_limit() if get_digit_limit is not None else None
        if set_digit_limit is not None:
            set_digit_limit(sys.int_info.default_max_str_digits)

        try:
            large_decimal = "1" + ("0" * sys.int_info.default_max_str_digits)
            secrets = parse_secret_input_spec(f"data:2000={large_decimal}/0")
            secret_orig, secret_prime, public_values = build_value_input_bytes(secrets, {})
            expected_orig = int(large_decimal).to_bytes(2000, byteorder="big", signed=False)
        finally:
            if set_digit_limit is not None and old_limit is not None:
                set_digit_limit(old_limit)

        self.assertEqual(secret_orig["data"], expected_orig)
        self.assertEqual(secret_prime["data"], b"\x00" * 2000)
        self.assertEqual(public_values, {})


if __name__ == "__main__":
    unittest.main()
