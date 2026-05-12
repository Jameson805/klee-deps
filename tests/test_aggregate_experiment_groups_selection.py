#!/usr/bin/env python3

from __future__ import annotations

import unittest

import pandas as pd

from tools.postprocess.aggregate_experiment_groups import (
    best_selection_table,
    select_best_configurations,
    summarize_configurations,
)


class AggregateExperimentGroupsSelectionTest(unittest.TestCase):
    def test_select_best_configurations_prefers_more_true_positives_then_lower_max_time(self) -> None:
        df = pd.DataFrame(
            {
                "library": ["lib", "lib", "lib"],
                "file": ["f.c", "f.c", "f.c"],
                "line": [10, 20, 30],
                "column": [1, 1, 1],
                "kind": ["branch", "branch", "branch"],
                "klee_cf_default_4_fix_pub": [1.0, 2.0, None],
                "klee_cf_dfs_4_fix_pub": [1.0, 3.5, None],
                "binsec_16_var_pub": [2.0, None, None],
                "binsec_8_fix_pub": [2.0, 4.0, 6.0],
            }
        )

        column_metadata_by_source = {
            "klee_cf_default_4_fix_pub": {
                "source_column": "klee_cf_default_4_fix_pub",
                "tool_family": "klee_cf",
                "comparison_tool": "klee_cf",
                "sliced": False,
                "searcher": "default",
                "sym_size": "4",
                "public_mode": "fix_pub",
                "concretization_policy": "default",
                "raw_suffix": "fix_pub",
                "normalized_suffix": "fix_pub",
                "configuration_label": "search=default, sym=4, mode=fix_pub",
            },
            "klee_cf_dfs_4_fix_pub": {
                "source_column": "klee_cf_dfs_4_fix_pub",
                "tool_family": "klee_cf",
                "comparison_tool": "klee_cf",
                "sliced": False,
                "searcher": "dfs",
                "sym_size": "4",
                "public_mode": "fix_pub",
                "concretization_policy": "default",
                "raw_suffix": "fix_pub",
                "normalized_suffix": "fix_pub",
                "configuration_label": "search=dfs, sym=4, mode=fix_pub",
            },
            "binsec_16_var_pub": {
                "source_column": "binsec_16_var_pub",
                "tool_family": "binsec",
                "comparison_tool": "binsec",
                "sliced": False,
                "searcher": "default",
                "sym_size": "16",
                "public_mode": "var_pub",
                "concretization_policy": "default",
                "raw_suffix": "var_pub",
                "normalized_suffix": "var_pub",
                "configuration_label": "sym=16, mode=var_pub",
            },
            "binsec_8_fix_pub": {
                "source_column": "binsec_8_fix_pub",
                "tool_family": "binsec",
                "comparison_tool": "binsec",
                "sliced": False,
                "searcher": "default",
                "sym_size": "8",
                "public_mode": "fix_pub",
                "concretization_policy": "default",
                "raw_suffix": "fix_pub",
                "normalized_suffix": "fix_pub",
                "configuration_label": "sym=8, mode=fix_pub",
            },
        }

        summary = summarize_configurations(df, column_metadata_by_source)
        best_summary = select_best_configurations(summary)
        best_by_tool = {
            row["comparison_tool"]: row for row in best_summary.to_dict("records")
        }

        self.assertEqual(
            best_by_tool["klee_cf"]["source_column"],
            "klee_cf_default_4_fix_pub",
        )
        self.assertEqual(best_by_tool["klee_cf"]["insecure_locations_found"], 2)
        self.assertEqual(best_by_tool["klee_cf"]["max_time"], 2.0)

        self.assertEqual(
            best_by_tool["binsec"]["source_column"],
            "binsec_8_fix_pub",
        )
        self.assertEqual(best_by_tool["binsec"]["insecure_locations_found"], 3)

        selection_rows = best_selection_table(best_summary).to_dict("records")
        self.assertEqual(
            selection_rows,
            [
                {
                    "comparison_tool": "binsec",
                    "source_column": "binsec_8_fix_pub",
                    "display_label": "binsec",
                },
                {
                    "comparison_tool": "klee_cf",
                    "source_column": "klee_cf_default_4_fix_pub",
                    "display_label": "klee_cf",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()