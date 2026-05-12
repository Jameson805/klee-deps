#!/usr/bin/env python3

from __future__ import annotations

import unittest

from tools.converters.abacus_log_to_json import _classify_instruction_text


class AbacusLogToJsonTest(unittest.TestCase):
    def test_classify_instruction_text_branch(self) -> None:
        self.assertEqual(_classify_instruction_text("je 80483fd <foo>"), "branch")

    def test_classify_instruction_text_memory(self) -> None:
        self.assertEqual(_classify_instruction_text("mov -0xc(%ebp),%eax"), "memory")


if __name__ == "__main__":
    unittest.main()