#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest

from scripts.experiments.common import execute_output_captured_worker


class _FakeOutputQueue:
    def __init__(self) -> None:
        self.messages: list[object] = []
        self.stderr_at_close = None

    def send(self, value: object) -> None:
        self.messages.append(value)

    def close(self) -> None:
        self.stderr_at_close = sys.stderr


class CommonOutputCaptureShutdownTest(unittest.TestCase):
    def test_execute_output_captured_worker_restores_stderr_before_queue_close(self) -> None:
        original_stderr = sys.stderr
        output_queue = _FakeOutputQueue()

        with self.assertRaises(SystemExit) as raised:
            execute_output_captured_worker(output_queue, lambda: 0)

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output_queue.messages, [None])
        self.assertIs(output_queue.stderr_at_close, original_stderr)

    def test_execute_output_captured_worker_maps_keyboard_interrupt_to_130(self) -> None:
        output_queue = _FakeOutputQueue()

        def _raise_keyboard_interrupt() -> None:
            raise KeyboardInterrupt()

        with self.assertRaises(SystemExit) as raised:
            execute_output_captured_worker(output_queue, _raise_keyboard_interrupt)

        self.assertEqual(raised.exception.code, 130)
        self.assertEqual(output_queue.messages, [None])


if __name__ == "__main__":
    unittest.main()