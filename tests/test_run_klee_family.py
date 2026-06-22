#!/usr/bin/env python3

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.experiments.run_klee_family import _load_klee_cases, _load_klee_preprocess_profiles
from tools.shared.experiment_registry import BenchmarkDefinition


class RunKleeFamilyTest(unittest.TestCase):
    def test_load_klee_cases_uses_target_config_and_artifact_config(self) -> None:
        benchmark_definition = BenchmarkDefinition(
            config_location="configs/benchmarks/example.toml",
            library_id="example",
            target_id="demo_sliced",
            code_path="benchmarks/example",
            tools=frozenset({"klee_cf"}),
            runner_profiles={},
            extra_config={
                "tool_defaults": {
                    "klee": {
                        "secret_inputs": ["secret"],
                        "public_inputs": ["public"],
                    }
                }
            },
        )
        expanded_case = SimpleNamespace(
            config_table={},
            config_location="configs/benchmarks/example.toml.targets.demo_sliced.configs[0]",
            target_table={},
            target_location="configs/benchmarks/example.toml.targets.demo_sliced",
            target_id="demo_sliced",
            config_id="var_pub_lim_loop_break",
            config="var_pub_lim_loop_break",
            artifact_config="var_pub",
            output_target="demo_sliced",
        )

        with patch("scripts.experiments.run_klee_family.expand_benchmark_cases", return_value=[expanded_case]):
            [case] = _load_klee_cases(benchmark_definition, "klee_cf")

        self.assertEqual(case["title"], "example:demo_sliced (var_pub_lim_loop_break)")
        self.assertEqual(case["result_name"], "example_demo_sliced_var_pub_lim_loop_break")
        self.assertEqual(
            case["bitcode"],
            "benchmarks/example/artifacts/klee/demo_sliced/var_pub_lim_loop_break.bc",
        )
        self.assertEqual(
            case["replay_script"],
            "benchmarks/example/artifacts/klee/demo_sliced/var_pub_replay",
        )
        self.assertEqual(case["config"], "var_pub_lim_loop_break")
        self.assertTrue(case["sliced"])
        self.assertEqual(case["secret_inputs"], ["secret"])
        self.assertEqual(case["public_inputs"], ["public"])
        self.assertEqual(case["replay_opts"], "--secret secret --public public")
        self.assertNotIn("variant_key", case)
        self.assertNotIn("target_key", case)
        self.assertNotIn("public_mode", case)

    def test_load_klee_cases_omits_public_inputs_for_fix_pub_artifacts(self) -> None:
        benchmark_definition = BenchmarkDefinition(
            config_location="configs/benchmarks/example.toml",
            library_id="example",
            target_id="demo",
            code_path="benchmarks/example",
            tools=frozenset({"klee_cf"}),
            runner_profiles={},
            extra_config={
                "tool_defaults": {
                    "klee": {
                        "secret_inputs": ["secret"],
                        "public_inputs": ["public"],
                    }
                }
            },
        )
        expanded_case = SimpleNamespace(
            config_table={},
            config_location="configs/benchmarks/example.toml.targets.demo.configs[0]",
            target_table={},
            target_location="configs/benchmarks/example.toml.targets.demo",
            target_id="demo",
            config_id="fix_pub",
            config="fix_pub",
            artifact_config="fix_pub",
            output_target="demo",
        )

        with patch("scripts.experiments.run_klee_family.expand_benchmark_cases", return_value=[expanded_case]):
            [case] = _load_klee_cases(benchmark_definition, "klee_cf")

        self.assertEqual(case["secret_inputs"], ["secret"])
        self.assertNotIn("public_inputs", case)
        self.assertEqual(case["replay_opts"], "--secret secret")

    def test_load_klee_preprocess_profiles_uses_artifact_input_and_config_output(self) -> None:
        benchmark_definition = BenchmarkDefinition(
            config_location="configs/benchmarks/example.toml",
            library_id="example",
            target_id="demo_sliced",
            code_path="benchmarks/example",
            tools=frozenset({"klee_cf"}),
            runner_profiles={},
            extra_config={
                "tool_defaults": {
                    "klee": {
                        "preprocess_profiles": {
                            "lim_loop_break": {
                                "arguments": ["--input={input}", "--output={output}"],
                            }
                        }
                    }
                }
            },
        )
        expanded_case = SimpleNamespace(
            config_table={"preprocess": "lim_loop_break"},
            config_location="configs/benchmarks/example.toml.targets.demo_sliced.configs[0]",
            target_table={},
            target_location="configs/benchmarks/example.toml.targets.demo_sliced",
            target_id="demo_sliced",
            config_id="var_pub_lim_loop_break",
            config="var_pub_lim_loop_break",
            artifact_config="var_pub",
            output_target="demo_sliced",
        )

        with patch("scripts.experiments.run_klee_family.expand_benchmark_cases", return_value=[expanded_case]):
            [profile] = _load_klee_preprocess_profiles(benchmark_definition, "klee_cf")

        self.assertEqual(
            profile["arguments"],
            [
                "--input=benchmarks/example/artifacts/klee/demo_sliced/var_pub.bc",
                "--output=benchmarks/example/artifacts/klee/demo_sliced/var_pub_lim_loop_break.bc",
            ],
        )


if __name__ == "__main__":
    unittest.main()
