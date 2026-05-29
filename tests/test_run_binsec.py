#!/usr/bin/env python3

from __future__ import annotations

from types import SimpleNamespace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.experiments.run_binsec import (
    _load_binsec_cases,
    _resolve_input_specs,
    resolve_binsec_executable,
    run_case,
)
from tools.shared.experiment_registry import BenchmarkDefinition, BenchmarkRunnerProfile


class RunBinsecTest(unittest.TestCase):
    def test_resolve_binsec_executable_uses_path_lookup(self) -> None:
        with patch("scripts.experiments.run_binsec.resolve_executable_path", return_value=Path("/tmp/binsec")):
            self.assertEqual(resolve_binsec_executable(), "/tmp/binsec")

    def test_resolve_binsec_executable_raises_clear_error_when_missing(self) -> None:
        with patch("scripts.experiments.run_binsec.resolve_executable_path", side_effect=SystemExit("missing binsec")):
            with self.assertRaises(SystemExit) as raised:
                resolve_binsec_executable()

        self.assertIn("missing binsec", str(raised.exception))

    def test_run_case_invokes_converter_without_title_filter(self) -> None:
        class DummyContext:
            def log(self, _message: str) -> None:
                return

            def run(self, _argv: list[str], cwd: Path | None = None) -> None:
                return

        class DummyWorkspace:
            def __init__(self, root: Path) -> None:
                self.root = root

            def resolve_repo_path(self, path: str) -> Path:
                return self.root / path

            def resolve_code_path(self, path: str) -> Path:
                return self.root / path

        class DummyBenchmarkDefinition:
            code_path = "benchmarks/openssl_almeida"
            library_id = "openssl_almeida"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            results_dir = root / "results"
            results_dir.mkdir()
            (results_dir / "_worker_logs").mkdir()
            (results_dir / "sample_case.toml").write_text("[Exploration]\ntime = 1.0\n", encoding="utf-8")

            executable = root / "artifacts" / "fix_pub"
            executable.parent.mkdir(parents=True)
            executable.write_text("", encoding="utf-8")
            executable.chmod(0o755)
            replay = executable.with_name("fix_pub_replay")
            replay.write_text("", encoding="utf-8")
            replay.chmod(0o755)

            args = type(
                "Args",
                (),
                {
                    "fml_solver": "z3",
                    "smt_solver": "z3",
                    "max_time_seconds": 300,
                    "jump_enum": 10,
                    "sse_depth": 100,
                    "sym_size": 4,
                },
            )()

            with (
                patch("scripts.experiments.run_binsec.definition_for_path", return_value=DummyBenchmarkDefinition()),
                patch("scripts.experiments.run_binsec.convert_binsec_toml") as convert_mock,
            ):
                run_case(
                    DummyContext(),
                    DummyWorkspace(root),
                    results_dir,
                    args,
                    "/tmp/binsec",
                    "openssl_almeida:default tls_rempad_luk13 (fix_pub)",
                    "configs/sample.cfg",
                    "sample_case.toml",
                    "artifacts/fix_pub",
                    {},
                )

            self.assertEqual(convert_mock.call_count, 1)
            self.assertNotIn("title", convert_mock.call_args.kwargs)

    def test_resolve_input_specs_uses_runner_preset_macros(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner_config = root / "runner.toml"
            runner_config.write_text(
                """
[presets.size_4.macros]
SYM_SIZE = 4
SECRET_BYTES = 32
PUBLIC_BYTES = 16
""".strip()
                + "\n",
                encoding="utf-8",
            )

            benchmark_definition = BenchmarkDefinition(
                config_location="configs/benchmarks/example.toml",
                library_id="example",
                variant_id="default",
                code_path="benchmarks/example",
                tools=frozenset({"binsec"}),
                runner_profiles={
                    "default": BenchmarkRunnerProfile(
                        config=str(runner_config),
                        preset="size_{sym_size}",
                    )
                },
                extra_config={},
            )
            case_table = {
                "runner_profile": "default",
                "secret_inputs": ["secret:{SECRET_BYTES}:secret_buf"],
                "public_inputs": ["public:{PUBLIC_BYTES}:public_buf"],
            }

            with patch("scripts.experiments.run_binsec.resolve_repo_path", side_effect=lambda path: Path(path)):
                self.assertEqual(
                    _resolve_input_specs(
                        benchmark_definition,
                        case_table,
                        "configs/benchmarks/example.toml.binsec_cases[0]",
                        "size_4",
                        "secret_inputs",
                        sym_size=99,
                    ),
                    ["secret:32:secret_buf"],
                )
                self.assertEqual(
                    _resolve_input_specs(
                        benchmark_definition,
                        case_table,
                        "configs/benchmarks/example.toml.binsec_cases[0]",
                        "size_4",
                        "public_inputs",
                        sym_size=99,
                    ),
                    ["public:16:public_buf"],
                )

    def test_load_binsec_cases_keeps_target_runner_profile_for_replay_resolution(self) -> None:
        benchmark_definition = BenchmarkDefinition(
            config_location="configs/benchmarks/example.toml",
            library_id="example",
            variant_id="default",
            code_path="benchmarks/example",
            tools=frozenset({"binsec"}),
            runner_profiles={
                "default": BenchmarkRunnerProfile(
                    config="configs/runner/example.toml",
                    preset="size_{sym_size}",
                )
            },
            extra_config={},
        )
        expanded_case = SimpleNamespace(
            config_table={"use_public_inputs": True},
            config_location="configs/benchmarks/example.toml.variants.default.configs.default",
            target_table={
                "runner_profile": "default",
                "secret_inputs": ["secret:{sym_size}:secret_buf"],
                "public_inputs": ["public:{sym_size}:public_buf"],
            },
            target_location="configs/benchmarks/example.toml.variants.default.targets[0]",
            target_id="demo",
            config_id="default",
            output_target="demo_default",
            public_mode="var_pub",
            variant_id="default",
        )

        with patch("scripts.experiments.run_binsec.expand_benchmark_cases", return_value=[expanded_case]):
            [case] = _load_binsec_cases(benchmark_definition)

        self.assertEqual(case["runner_profile"], "default")
        self.assertEqual(case["secret_inputs"], ["secret:{sym_size}:secret_buf"])
        self.assertEqual(case["public_inputs"], ["public:{sym_size}:public_buf"])
        self.assertEqual(case["public_mode"], "var_pub")


if __name__ == "__main__":
    unittest.main()