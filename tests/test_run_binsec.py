#!/usr/bin/env python3

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.experiments.run_binsec import resolve_binsec_executable, run_case


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


if __name__ == "__main__":
    unittest.main()