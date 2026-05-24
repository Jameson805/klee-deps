#!/usr/bin/env python3

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from tools.converters.abacus_log_to_json import _classify_instruction_text, convert_abacus_log


class AbacusLogToJsonTest(unittest.TestCase):
    def test_classify_instruction_text_branch(self) -> None:
        self.assertEqual(_classify_instruction_text("je 80483fd <foo>"), "branch")

    def test_classify_instruction_text_memory(self) -> None:
        self.assertEqual(_classify_instruction_text("mov -0xc(%ebp),%eax"), "memory")

    def test_convert_abacus_log_requires_runner_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "sample.log"
            log_path.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                convert_abacus_log(
                    log_path=str(log_path),
                    executable_path="/nonexistent",
                    runner_config=None,
                    preset_name=None,
                    library="unknown",
                )

        self.assertIn("runner_config is required", str(raised.exception))

    def test_convert_abacus_log_omits_legacy_reference_secret_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_path = temp_path / "sample.log"
            log_path.write_text("", encoding="utf-8")
            runner_config_path = temp_path / "runner.toml"
            runner_config_path.write_text(
                "[[inputs]]\n"
                "id = \"exp_buf\"\n"
                "name = \"exp\"\n"
                "kind = \"secret\"\n"
                "size = 4\n\n"
                "[mode_policy.abacus]\n"
                "secret_inputs = [\"exp_buf\"]\n\n"
                "[presets.size_4.abacus_secrets]\n"
                "exp_buf = 0\n",
                encoding="utf-8",
            )

            payload = convert_abacus_log(
                log_path=str(log_path),
                executable_path="/nonexistent",
                runner_config=str(runner_config_path),
                preset_name="size_4",
                library="unknown",
            )

        notes = payload.get("notes")
        self.assertIsInstance(notes, dict)
        self.assertIn("abacus_reference_secrets", notes)
        self.assertNotIn("abacus_reference_secret", notes)


if __name__ == "__main__":
    unittest.main()