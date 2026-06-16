#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest

from tools.postprocess.reproduce_positives import build_value_input_bytes, parse_secret_input_spec


class ReproducePositivesTest(unittest.TestCase):
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
