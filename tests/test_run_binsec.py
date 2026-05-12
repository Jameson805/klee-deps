#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.experiments.run_binsec import resolve_binsec_executable


class RunBinsecTest(unittest.TestCase):
    def test_resolve_binsec_executable_uses_path_lookup(self) -> None:
        with patch("scripts.experiments.run_binsec.shutil.which", return_value="/tmp/binsec"):
            self.assertEqual(resolve_binsec_executable(), "/tmp/binsec")

    def test_resolve_binsec_executable_raises_clear_error_when_missing(self) -> None:
        with patch("scripts.experiments.run_binsec.shutil.which", return_value=None):
            with self.assertRaises(SystemExit) as raised:
                resolve_binsec_executable()

        self.assertIn("could not find 'binsec' on PATH", str(raised.exception))


if __name__ == "__main__":
    unittest.main()