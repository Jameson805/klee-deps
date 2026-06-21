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
        variant: str,
        target: str,
        suffix: str = "fix_pub",
    ) -> dict[str, object]:
        return {
            "source_column_suffix": suffix,
            "public_mode": suffix,
            "sliced": False,
            "library_key": library,
            "variant_key": variant,
            "target_key": target,
        }

    def test_repetitions_use_geometric_mean_and_best_table_uses_benchmark_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_metadata(
                root,
                {
                    "klee_fast": self._run_metadata("klee_fast", "klee_cf", searcher="dfs"),
                    "klee_slow": self._run_metadata("klee_slow", "klee_cf"),
                    "binsec_run": self._run_metadata("binsec_run", "binsec"),
                },
            )

            for repetition, elapsed in ((0, 4.0), (1, 9.0)):
                write_verification_timing(
                    root / "klee_fast" / str(repetition),
                    case_id="toy_v1_a_fix_pub",
                    title="toy:v1 a (fix_pub)",
                    metadata=self._case_metadata(library="toy", variant="v1", target="a"),
                    timeout_seconds=7200,
                    elapsed_seconds=elapsed,
                    exit_code=0,
                    status="completed",
                )
            write_verification_timing(
                root / "klee_fast" / "0",
                case_id="toy_v1_b_fix_pub",
                title="toy:v1 b (fix_pub)",
                metadata=self._case_metadata(library="toy", variant="v1", target="b"),
                timeout_seconds=7200,
                elapsed_seconds=25.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_slow" / "0",
                case_id="toy_v1_a_fix_pub",
                title="toy:v1 a (fix_pub)",
                metadata=self._case_metadata(library="toy", variant="v1", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=10.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "klee_slow" / "0",
                case_id="toy_v1_b_fix_pub",
                title="toy:v1 b (fix_pub)",
                metadata=self._case_metadata(library="toy", variant="v1", target="b"),
                timeout_seconds=7200,
                elapsed_seconds=30.0,
                exit_code=0,
                status="completed",
            )
            write_verification_timing(
                root / "binsec_run" / "0",
                case_id="toy_v1_a_fix_pub",
                title="toy:v1 a (fix_pub)",
                metadata=self._case_metadata(library="toy", variant="v1", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=7201.0,
                exit_code=0,
                status="timeout",
            )

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
                {"klee_cf": "klee_fast_fix_pub", "binsec": "binsec_run_fix_pub"},
            )

            fieldnames, table_rows = merge_verification_timings.build_best_table_rows(rows, selected)
            self.assertEqual(fieldnames, ["benchmark", "CT-Witness", "Binsec/Rel 2"])
            self.assertEqual(
                table_rows,
                [
                    {"benchmark": "toy:v1", "CT-Witness": "25.00s", "Binsec/Rel 2": "TO(2h)"},
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
                metadata=self._case_metadata(library="toy", variant="v1", target="a"),
                timeout_seconds=7200,
                elapsed_seconds=1.5,
                exit_code=0,
                status="completed",
            )

            rows = merge_verification_timings.collect_timing_rows(root)
            merge_verification_timings.write_long_csv(rows, output_path)
            lines = output_path.read_text(encoding="utf-8").splitlines()

            self.assertIn("status_counts", lines[0])
            self.assertEqual(json.loads(rows[0]["status_counts"]), {"completed": 1})

    def test_old_timing_payload_infers_variant_from_canonical_case_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_run_metadata(root, {"binsec_run": self._run_metadata("binsec_run", "binsec")})
            write_verification_timing(
                root / "binsec_run" / "0",
                case_id="libsodium_chacha20_chacha20_fix_pub",
                title="libsodium:chacha20 chacha20 (fix_pub)",
                metadata={
                    "source_column_suffix": "fix_pub",
                    "public_mode": "fix_pub",
                    "sliced": False,
                    "library_key": "libsodium",
                },
                timeout_seconds=7200,
                elapsed_seconds=1.5,
                exit_code=0,
                status="completed",
            )

            rows = merge_verification_timings.collect_timing_rows(root)

            self.assertEqual(rows[0]["variant"], "chacha20")
            self.assertEqual(rows[0]["target"], "chacha20")
            self.assertEqual(rows[0]["benchmark"], "libsodium:chacha20")


if __name__ == "__main__":
    unittest.main()