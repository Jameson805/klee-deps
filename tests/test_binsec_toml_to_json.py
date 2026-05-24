#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.converters.binsec_toml_to_json import (
    InputLayout,
    LeakInfo,
    build_rows,
    convert_binsec_toml,
    main,
    parse_output_log,
)


class BinsecTomlToJsonTest(unittest.TestCase):
    def test_parse_output_log_ignores_section_titles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "output.log"
            log_path.write_text(
                "========\n"
                "unrelated title\n"
                "========\n"
                "[checkct:result] Instruction 0x401000 has control flow leak (1.25s)\n"
                "========\n"
                "another title\n"
                "========\n"
                "[checkct:result] Instruction 0x402000 has memory access leak (2.5s)\n",
                encoding="utf-8",
            )

            leaks = parse_output_log(str(log_path))

        self.assertEqual(sorted(leaks), [0x401000, 0x402000])
        self.assertEqual(leaks[0x401000].leak_type, "control flow")
        self.assertEqual(leaks[0x401000].seconds, 1.25)
        self.assertEqual(leaks[0x402000].leak_type, "memory access")
        self.assertEqual(leaks[0x402000].seconds, 2.5)

    def test_build_rows_preserves_kind(self) -> None:
        rows = build_rows(
            insecure_addrs=[0x401000],
            models={},
            leaks={0x401000: LeakInfo(leak_type="control flow", seconds=0.5)},
            addr_executable="/nonexistent",
            code_root=None,
            library="mbedtls",
            secret_inputs=[InputLayout(name="exp", size=4, model_key="exp_buf")],
            public_inputs=[],
            reproduce_module=None,
            replay_executable=None,
            reproduce_timeout_s=60,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "branch")

    def test_convert_binsec_toml_does_not_infer_public_inputs_from_var_pub_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            toml_path = temp_path / "libg_default_des_var_pub.toml"
            toml_path.write_text(
                "[\"CT report\".\"Instructions status\"]\n"
                "insecure = [\"0x401000\"]\n"
                "unknown = []\n",
                encoding="utf-8",
            )
            output_log = temp_path / "output.log"
            output_log.write_text(
                "[checkct:result] Instruction 0x401000 has control flow leak (0.5s)\n",
                encoding="utf-8",
            )

            with patch("tools.converters.binsec_toml_to_json.build_rows", return_value=[]) as build_rows_mock:
                convert_binsec_toml(
                    toml_path=str(toml_path),
                    output_log=str(output_log),
                    executable="/nonexistent",
                    secret_inputs=["key:24:key_buf", "data:64:data_buf"],
                    public_inputs=None,
                    library="libg",
                )

        self.assertEqual(build_rows_mock.call_count, 1)
        self.assertEqual(build_rows_mock.call_args.kwargs["public_inputs"], [])

    def test_convert_binsec_toml_does_not_infer_secret_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            toml_path = temp_path / "sample.toml"
            toml_path.write_text(
                "[\"CT report\".\"Instructions status\"]\n"
                "insecure = [\"0x401000\"]\n"
                "unknown = []\n",
                encoding="utf-8",
            )
            output_log = temp_path / "output.log"
            output_log.write_text(
                "[checkct:result] Instruction 0x401000 has memory access leak (0.5s)\n",
                encoding="utf-8",
            )

            with patch("tools.converters.binsec_toml_to_json.build_rows", return_value=[]) as build_rows_mock:
                convert_binsec_toml(
                    toml_path=str(toml_path),
                    output_log=str(output_log),
                    executable="/nonexistent",
                    secret_inputs=None,
                    public_inputs=None,
                    library="libg",
                )

        self.assertEqual(build_rows_mock.call_count, 1)
        self.assertEqual(build_rows_mock.call_args.kwargs["secret_inputs"], [])

    def test_convert_binsec_toml_requires_secret_inputs_for_reproduction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            toml_path = temp_path / "sample.toml"
            toml_path.write_text(
                "[\"CT report\".\"Instructions status\"]\n"
                "insecure = [\"0x401000\"]\n"
                "unknown = []\n",
                encoding="utf-8",
            )
            output_log = temp_path / "output.log"
            output_log.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                convert_binsec_toml(
                    toml_path=str(toml_path),
                    output_log=str(output_log),
                    executable="/nonexistent",
                    secret_inputs=None,
                    public_inputs=None,
                    replay_executable="/tmp/replay",
                    reproduce=True,
                    library="libg",
                )

        self.assertIn("secret_inputs are required", str(raised.exception))

    def test_main_reports_missing_secret_inputs_for_reproduction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            toml_path = temp_path / "sample.toml"
            toml_path.write_text(
                "[\"CT report\".\"Instructions status\"]\n"
                "insecure = [\"0x401000\"]\n"
                "unknown = []\n",
                encoding="utf-8",
            )
            output_log = temp_path / "output.log"
            output_log.write_text("", encoding="utf-8")
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                rc = main(
                    [
                        "--toml",
                        str(toml_path),
                        "--output-log",
                        str(output_log),
                        "--executable",
                        "/nonexistent",
                        "--out",
                        str(temp_path / "out.json"),
                        "--library",
                        "unknown",
                        "--reproduce",
                        "--replay-executable",
                        "/tmp/replay",
                    ]
                )

        self.assertEqual(rc, 2)
        self.assertIn("secret_inputs are required", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()