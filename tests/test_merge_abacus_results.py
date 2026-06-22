#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.postprocess import merge_abacus_results
from tools.shared.configuration_metadata import load_run_metadata, write_run_metadata


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


class MergeAbacusResultsTest(unittest.TestCase):
    def _case_payload(
        self,
        *,
        non_ct_time: float = 3.0,
        reproduced_status: str = "success",
    ) -> dict[str, object]:
        return {
            "data": [
                {
                    "filename": "toy.c",
                    "line": 10,
                    "column": 2,
                    "kind": "branch",
                    "non_ct_time": non_ct_time,
                    "reproduced_status": reproduced_status,
                }
            ],
            "metadata": {
                "config": "fix_pub",
                "sliced": False,
                "library": "toy",
                "target": "default",
            },
        }

    def _write_filter_csv(self, path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["library", "file", "line_start", "line_end"])
            writer.writerow(["toy", "toy.c", "1", "20"])

    def test_resolves_default_abacus_config_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            expected = source / "abacus_config"
            expected.mkdir()

            self.assertEqual(
                merge_abacus_results.resolve_abacus_bucket(source, None), expected
            )

    def test_stage_registers_abacus_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_bucket = root / "source" / "abacus_config"
            target = root / "target"
            target.mkdir()
            write_run_metadata(
                target,
                {
                    "klee_cf": {
                        "source_column_prefix": "klee_cf",
                        "tool_family": "klee_cf",
                        "searcher": "default",
                        "sym_size": "4",
                        "cv_model": "all",
                    }
                },
            )
            write_json(source_bucket / "0" / "toy_fix_pub.json", self._case_payload())

            staged = merge_abacus_results.stage_abacus_bucket(
                source_bucket=source_bucket,
                target_root=target,
                run_name="abacus_config",
                replace=False,
            )
            merge_abacus_results.update_target_run_metadata(
                target_root=target,
                run_name="abacus_config",
                run_metadata=merge_abacus_results.abacus_run_metadata("abacus_config"),
                replace=False,
            )

            self.assertTrue((staged / "toy_fix_pub.json").is_file())
            metadata = load_run_metadata(target)
            self.assertEqual(metadata["abacus_config"]["tool_family"], "abacus")
            self.assertEqual(
                metadata["abacus_config"]["source_column_prefix"], "abacus_config"
            )

    def test_stage_preserves_validated_top_level_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_bucket = root / "source" / "abacus_config"
            target = root / "target"
            target.mkdir()
            write_json(
                source_bucket / "toy_fix_pub.json",
                self._case_payload(reproduced_status="success"),
            )
            write_json(
                source_bucket / "0" / "toy_fix_pub.json",
                self._case_payload(reproduced_status="not_reproduced"),
            )

            staged = merge_abacus_results.stage_abacus_bucket(
                source_bucket=source_bucket,
                target_root=target,
                run_name="abacus_config",
                replace=False,
            )

            payload = json.loads((staged / "toy_fix_pub.json").read_text())
            self.assertEqual(payload["data"][0]["reproduced_status"], "success")

    def test_main_stage_only_accepts_campaign_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            target.mkdir()
            filter_csv = root / "filtered_locations.csv"
            sliced_map_csv = root / "sliced_map.csv"
            self._write_filter_csv(filter_csv)
            sliced_map_csv.write_text(
                "library,file,line,column,target_file,target_line,target_column\n",
                encoding="utf-8",
            )
            write_json(
                source / "abacus_config" / "0" / "toy_fix_pub.json",
                self._case_payload(),
            )

            rc = merge_abacus_results.main(
                [
                    str(source),
                    str(target),
                    "--filter",
                    str(filter_csv),
                    "--sliced-map",
                    str(sliced_map_csv),
                    "--stage-only",
                ]
            )

            self.assertEqual(rc, 0)
            self.assertTrue((target / "abacus_config" / "toy_fix_pub.json").is_file())
            self.assertIn("abacus_config", load_run_metadata(target))

    def test_regenerate_outputs_adds_abacus_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "abacus_config"
            target = root / "target"
            target.mkdir()
            filter_csv = root / "filtered_locations.csv"
            sliced_map_csv = root / "sliced_map.csv"
            self._write_filter_csv(filter_csv)
            sliced_map_csv.write_text(
                "library,file,line,column,target_file,target_line,target_column\n",
                encoding="utf-8",
            )
            write_json(
                source / "0" / "toy_fix_pub.json",
                self._case_payload(non_ct_time=5.0),
            )

            merge_abacus_results.stage_abacus_bucket(
                source_bucket=source,
                target_root=target,
                run_name="abacus_config",
                replace=False,
            )
            merge_abacus_results.update_target_run_metadata(
                target_root=target,
                run_name="abacus_config",
                run_metadata=merge_abacus_results.abacus_run_metadata("abacus_config"),
                replace=False,
            )
            merge_abacus_results.regenerate_merged_outputs(
                target_root=target,
                filter_csv=filter_csv,
                sliced_map_csv=sliced_map_csv,
                aggregate_output_prefix="aggregated",
                by_library_output_prefix="filtered_reproduction_status_by_library",
                selection_csv=None,
                all_positives=False,
                skip_aggregate=True,
                skip_summary=True,
            )

            merged_text = (target / "filtered_merged_results.csv").read_text(
                encoding="utf-8"
            )
            self.assertIn("abacus_config_fix_pub", merged_text)
            self.assertIn("5.00", merged_text)


if __name__ == "__main__":
    unittest.main()