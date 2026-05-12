#!/usr/bin/env python3

from __future__ import annotations

import unittest

from tools.converters.binsec_toml_to_json import InputLayout, LeakInfo, build_rows


class BinsecTomlToJsonTest(unittest.TestCase):
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
            pin_root=None,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "branch")


if __name__ == "__main__":
    unittest.main()