#!/usr/bin/env python3

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.experiments.common import launch_output_captured_process, wait_for_processes


def _write_env_value(output_path: str, output_queue: object | None = None) -> None:
    Path(output_path).write_text(os.environ.get("TEST_OUTPUT_CAPTURED_ENV", ""), encoding="utf-8")


def _write_which_value(command_name: str, output_path: str, output_queue: object | None = None) -> None:
    Path(output_path).write_text(shutil.which(command_name) or "", encoding="utf-8")


class CommonOutputCapturedEnvTest(unittest.TestCase):
    def test_launch_output_captured_process_inherits_current_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_path = root / "env.txt"
            log_path = root / "worker.log"
            previous = os.environ.get("TEST_OUTPUT_CAPTURED_ENV")
            os.environ["TEST_OUTPUT_CAPTURED_ENV"] = "expected-value"

            try:
                launched = launch_output_captured_process(
                    "env test",
                    _write_env_value,
                    (str(output_path),),
                    log_path=log_path,
                )
                self.assertEqual(wait_for_processes([launched]), 0)
            finally:
                if previous is None:
                    os.environ.pop("TEST_OUTPUT_CAPTURED_ENV", None)
                else:
                    os.environ["TEST_OUTPUT_CAPTURED_ENV"] = previous

            self.assertEqual(output_path.read_text(encoding="utf-8"), "expected-value")

    def test_launch_output_captured_process_inherits_current_path_for_command_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_binsec = bin_dir / "binsec"
            fake_binsec.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_binsec.chmod(0o755)

            output_path = root / "which.txt"
            log_path = root / "worker.log"
            previous = os.environ.get("PATH")
            os.environ["PATH"] = str(bin_dir)

            try:
                launched = launch_output_captured_process(
                    "path test",
                    _write_which_value,
                    ("binsec", str(output_path)),
                    log_path=log_path,
                )
                self.assertEqual(wait_for_processes([launched]), 0)
            finally:
                if previous is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = previous

            self.assertEqual(output_path.read_text(encoding="utf-8"), str(fake_binsec))


if __name__ == "__main__":
    unittest.main()