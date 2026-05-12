#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.experiments.common import ExperimentContext


class _InterruptingStdout:
    def __iter__(self) -> _InterruptingStdout:
        return self

    def __next__(self) -> str:
        raise KeyboardInterrupt()


class _FakePopen:
    def __init__(self) -> None:
        self.stdout = _InterruptingStdout()
        self.terminated = False
        self.killed = False
        self.wait_calls: list[int | None] = []

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: int | None = None) -> int:
        self.wait_calls.append(timeout)
        return 0


class CommonExperimentContextInterruptTest(unittest.TestCase):
    def test_run_terminates_subprocess_on_keyboard_interrupt(self) -> None:
        fake_process = _FakePopen()

        with patch("scripts.experiments.common.subprocess.Popen", return_value=fake_process):
            with self.assertRaises(KeyboardInterrupt):
                ExperimentContext().run(["echo", "ignored"])

        self.assertTrue(fake_process.terminated)
        self.assertFalse(fake_process.killed)
        self.assertEqual(fake_process.wait_calls, [2])


if __name__ == "__main__":
    unittest.main()