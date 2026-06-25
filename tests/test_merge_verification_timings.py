#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from tools.postprocess import merge_verification_timings
from tools.shared.configuration_metadata import write_run_metadata
from tools.shared.verification_timing import write_verification_timing


class MergeVerificationTimingsTest(unittest.TestCase):
    def _run_metadata(self, destination: str, tool: str, *, searcher: str = "default") -> dict[str, object]:
        return {
            "source_column_prefix": destination,
            "tool_family": tool,
            "searcher": searcher,
            "sym_size": "4",
            "cv_model": "all",
        }

    def _case_metadata(
        self,
        *,
        library: str,
        target: str,
        suffix: str = "fix_pub",
    ) -> dict[str, object]:
        return {
            "sliced": False,
            "library": library,
            "target": target,
            "config": suffix,
        }

    def _write_klee_info(self, root: Path, run_name: str, case_id: str, partially_completed_paths: int) -> None:
        output_dir = root / run_name / "0" / case_id
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "info").write_text(
            "KLEE: done: completed paths = 1\n"
            f"KLEE: done: partially completed paths = {partially_completed_paths}\n"
            "KLEE: done: generated tests = 1\n",
            encoding="utf-8",
        )

    def _write_binsec_status(self, root: Path, run_name: str, case_id: str, program_status: str) -> None:
        log_dir = root / run_name / "0" / "_worker_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{case_id}.log").write_text(
            f"[checkct:result] Program status is : {program_status} (1.0)\n",
            encoding="utf-8",
        )

    def test_repetitions_use_geometric_mean_and_best_table_uses_var_pub_benchmark_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_metadata(
                root,
                {
                    "klee_fast": self._run_metadata("klee_fast", "klee_cf", searcher="dfs"),
                    "klee_slow": self._run_metadata("klee_slow", "klee_cf"),
                    "abacus_run": self._run_metadata("abacus_run", "abacus"),
                    "binsec_run": self._run_metadata("binsec_run", "binsec"),
                },
            )

            for repetition, elapsed in ((0, 4.0), (1, 9.0)):
                write_verification_timing(
                    root / "klee_fast" / str(repetition),
                    case_id="toy_v1_a_fix_pub",
                    title="toy:v1 a (fix_pub)",
                    metadata=self._case_metadata(library="toy", target="a"),
                    timeout_seconds=7200,
                    elapsed_seconds=elapsed,
                    exit_code=0,
                    status="completed",
                )
            write_verification_timing(
                root / "klee_fast" / "0",
                case_id="toy_v1_b_fix_pub",
                title="toy:v1 b (fix_pub)",
                metadata=self._case_metadata(library="toy", target="b"),
                timeout_seconds=7200,
                elapsed_seconds=25.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_fast" / "0",
                case_id="toy_v1_a_var_pub",
                title="toy:v1 a (var_pub)",
                metadata=self._case_metadata(library="toy", target="a", suffix="var_pub"),
                timeout_seconds=7200,
                elapsed_seconds=11.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_fast" / "0",
                case_id="toy_v1_b_var_pub",
                title="toy:v1 b (var_pub)",
                metadata=self._case_metadata(
                    library="toy",
                    target="b",
                    suffix="var_pub",
                ),
                timeout_seconds=7200,
                elapsed_seconds=20.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_slow" / "0",
                case_id="toy_v1_a_fix_pub",
                title="toy:v1 a (fix_pub)",
                metadata=self._case_metadata(library="toy", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=10.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_slow" / "0",
                case_id="toy_v1_a_var_pub",
                title="toy:v1 a (var_pub)",
                metadata=self._case_metadata(library="toy", target="a", suffix="var_pub"),
                timeout_seconds=7200,
                elapsed_seconds=40.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_slow" / "0",
                case_id="toy_v1_b_var_pub",
                title="toy:v1 b (var_pub)",
                metadata=self._case_metadata(library="toy", target="b", suffix="var_pub"),
                timeout_seconds=7200,
                elapsed_seconds=50.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_slow" / "0",
                case_id="toy_v1_b_fix_pub",
                title="toy:v1 b (fix_pub)",
                metadata=self._case_metadata(library="toy", target="b"),
                timeout_seconds=7200,
                elapsed_seconds=30.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "binsec_run" / "0",
                case_id="toy_v1_a_fix_pub",
                title="toy:v1 a (fix_pub)",
                metadata=self._case_metadata(library="toy", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=7201.0,
                exit_code=0,
                status="timeout",
            )
            write_verification_timing(
                root / "binsec_run" / "0",
                case_id="toy_v1_a_var_pub",
                title="toy:v1 a (var_pub)",
                metadata=self._case_metadata(library="toy", target="a", suffix="var_pub"),
                timeout_seconds=7200,
                elapsed_seconds=33.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "abacus_run" / "0",
                case_id="toy_v1_a_fix_pub",
                title="toy:v1 a (fix_pub)",
                metadata=self._case_metadata(library="toy", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=2.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "abacus_run" / "0",
                case_id="toy_v1_a_var_pub",
                title="toy:v1 a (var_pub)",
                metadata=self._case_metadata(library="toy", target="a", suffix="var_pub"),
                timeout_seconds=7200,
                elapsed_seconds=44.0,
                exit_code=0,
                status="completed",
            )
            self._write_klee_info(root, "klee_fast", "toy_v1_a_var_pub", 0)
            self._write_klee_info(root, "klee_fast", "toy_v1_b_var_pub", 0)
            self._write_klee_info(root, "klee_slow", "toy_v1_a_var_pub", 0)
            self._write_klee_info(root, "klee_slow", "toy_v1_b_var_pub", 0)
            self._write_binsec_status(root, "binsec_run", "toy_v1_a_var_pub", "secure")

            rows = merge_verification_timings.collect_timing_rows(root)
            by_source_and_target = {
                (row["source_column"], row["target"]): row
                for row in rows
            }
            self.assertTrue(
                math.isclose(
                    float(by_source_and_target[("klee_fast_fix_pub", "a")]["verification_time_seconds"]),
                    6.0,
                    rel_tol=1e-9,
                )
            )

            selected = merge_verification_timings.select_best_configurations(rows)
            self.assertEqual(
                {row["comparison_tool"]: row["source_column"] for row in selected},
                {
                    "abacus": "abacus_run_var_pub",
                    "klee_cf": "klee_fast_var_pub",
                    "binsec": "binsec_run_var_pub",
                },
            )

            fieldnames, table_rows = merge_verification_timings.build_best_table_rows(rows, selected)
            self.assertEqual(
                fieldnames,
                [
                    "benchmark",
                    "CT-Witness",
                    "CT-Witness status",
                    "Abacus",
                    "Abacus status",
                    "Binsec/Rel 2",
                    "Binsec/Rel 2 status",
                ],
            )
            self.assertEqual(
                table_rows,
                [
                    {
                        "benchmark": "toy:a",
                        "CT-Witness": "11.00s",
                        "CT-Witness status": "secure",
                        "Abacus": "44.00s",
                        "Abacus status": "unknown",
                        "Binsec/Rel 2": "33.00s",
                        "Binsec/Rel 2 status": "secure",
                    },
                    {
                        "benchmark": "toy:b",
                        "CT-Witness": "20.00s",
                        "CT-Witness status": "secure",
                        "Abacus": "-",
                        "Abacus status": "-",
                        "Binsec/Rel 2": "-",
                        "Binsec/Rel 2 status": "-",
                    },
                ],
            )

    def test_long_csv_writes_status_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_path = root / "verification_times.csv"
            write_run_metadata(root, {"binsec_run": self._run_metadata("binsec_run", "binsec")})
            write_verification_timing(
                root / "binsec_run" / "0",
                case_id="toy_v1_a_fix_pub",
                title="toy:v1 a (fix_pub)",
                metadata=self._case_metadata(library="toy", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=1.5,
                exit_code=0,
                status="completed",
            )

            rows = merge_verification_timings.collect_timing_rows(root)
            merge_verification_timings.write_long_csv(rows, output_path)
            lines = output_path.read_text(encoding="utf-8").splitlines()

            self.assertIn("status_counts", lines[0])
            self.assertIn("program_status", lines[0])
            self.assertEqual(json.loads(rows[0]["status_counts"]), {"completed": 1})
            self.assertEqual(rows[0]["program_status"], "unknown")

    def test_klee_program_status_uses_positives_and_partially_completed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_metadata(root, {"klee_run": self._run_metadata("klee_run", "klee_cf")})
            for case_id, target, partially_completed_paths in (
                ("toy_secure_var_pub", "secure", 0),
                ("toy_unknown_var_pub", "unknown", 1),
                ("toy_insecure_var_pub", "insecure", 1),
            ):
                write_verification_timing(
                    root / "klee_run" / "0",
                    case_id=case_id,
                    title=f"toy:{target} (var_pub)",
                    metadata=self._case_metadata(library="toy", target=target, suffix="var_pub"),
                    timeout_seconds=7200,
                    elapsed_seconds=1.5,
                    exit_code=0,
                    status="completed",
                )
                self._write_klee_info(root, "klee_run", case_id, partially_completed_paths)

            (root / "klee_run" / "0" / "toy_insecure_var_pub.json").write_text(
                json.dumps({"data": [{"kind": "branch"}], "metadata": {}}) + "\n",
                encoding="utf-8",
            )

            rows = merge_verification_timings.collect_timing_rows(root)

            self.assertEqual(
                {row["target"]: row["program_status"] for row in rows},
                {"secure": "secure", "unknown": "unknown", "insecure": "insecure"},
            )

    def test_old_timing_payload_infers_variant_from_canonical_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_metadata(root, {"binsec_run": self._run_metadata("binsec_run", "binsec")})
            timing_dir = root / "binsec_run" / "0" / "_timings"
            timing_dir.mkdir(parents=True)
            (timing_dir / "libsodium_chacha20_fix_pub.json").write_text(
                json.dumps(
                    {
                        "data": [
                            {
                                "case_id": "libsodium_chacha20_fix_pub",
                                "title": "libsodium:chacha20 chacha20 (fix_pub)",
                                "library": "libsodium",
                                "timeout_seconds": 7200,
                                "elapsed_seconds": 1.5,
                                "verification_time_seconds": 1.5,
                                "status": "completed",
                                "exit_code": 0,
                            }
                        ],
                        "metadata": {
                            "config": "fix_pub",
                            "sliced": False,
                            "library": "libsodium",
                        },
                    }
                ),
                encoding="utf-8",
            )

            rows = merge_verification_timings.collect_timing_rows(root)

            self.assertEqual(rows[0]["variant"], "chacha20")
            self.assertEqual(rows[0]["target"], "chacha20")
            self.assertEqual(rows[0]["benchmark"], "libsodium:chacha20")

    def test_writer_uses_flattened_identity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_path = write_verification_timing(
                root / "binsec_run" / "0",
                case_id="toy_a_fix_pub",
                title="toy:a (fix_pub)",
                metadata={
                    "library": "toy",
                    "target": "a",
                    "config": "fix_pub",
                    "sliced": False,
                },
                timeout_seconds=60,
                elapsed_seconds=1.5,
                exit_code=0,
                status="completed",
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            row = payload["data"][0]
            self.assertEqual(row["library"], "toy")
            self.assertEqual(row["target"], "a")
            self.assertEqual(row["config"], "fix_pub")
            self.assertNotIn("variant", row)


if __name__ == "__main__":
    unittest.main()