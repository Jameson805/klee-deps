#!/usr/bin/env python3

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.validation.validate_abacus import _build_case_index


class ValidateAbacusTest(unittest.TestCase):
    def test_build_case_index_uses_artifact_config_for_replay_path(self) -> None:
        benchmark_definition = SimpleNamespace(
            library_id="openssl",
            target_id="recp_sliced",
            code_path="benchmarks/openssl-1.1.1q",
        )
        build = SimpleNamespace(preset="size_{sym_size}")
        expanded_case = SimpleNamespace(
            output_target="recp_sliced",
            config_id="var_pub_lim_loop_break",
            artifact_config="var_pub",
        )

        with (
            patch("scripts.validation.validate_abacus.selected_benchmarks", return_value=[("openssl", "recp_sliced")]),
            patch("scripts.validation.validate_abacus.definition", return_value=benchmark_definition),
            patch("scripts.validation.validate_abacus.build_for_tool", return_value=build),
            patch("scripts.validation.validate_abacus.expand_benchmark_cases", return_value=[expanded_case]),
        ):
            case_index = _build_case_index()

        case = case_index["openssl_recp_sliced_var_pub_lim_loop_break"]
        self.assertEqual(
            case.replay_executable,
            "benchmarks/openssl-1.1.1q/artifacts/klee/recp_sliced/var_pub_replay",
        )


if __name__ == "__main__":
    unittest.main()
