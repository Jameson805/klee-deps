#!/usr/bin/env python3

from __future__ import annotations

import unittest

import pandas as pd

from tools.postprocess.aggregate_experiment_groups import (
    automatic_selection_summary,
    best_selection_table,
    filter_tool_summary_for_plot,
    select_best_configurations,
    summarize_configurations,
)


class AggregateExperimentGroupsSelectionTest(unittest.TestCase):
    def test_summarize_configurations_derives_suffix_fields_from_config(self) -> None:
        df = pd.DataFrame(
            {
                "library": ["lib"],
                "file": ["f.c"],
                "line": [10],
                "column": [1],
                "kind": ["branch"],
                "klee_cf_default_4_fix_pub": [1.0],
            }
        )

        summary = summarize_configurations(
            df,
            {
                "klee_cf_default_4_fix_pub": {
                    "source_column": "klee_cf_default_4_fix_pub",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "default",
                    "sym_size": "4",
                    "config": "fix_pub",
                    "cv_model": "all",
                    "configuration_label": "searcher=default, sym_size=4, config=fix_pub",
                }
            },
        )

        row = summary.iloc[0]
        self.assertEqual(row["raw_suffix"], "fix_pub")
        self.assertEqual(row["normalized_suffix"], "fix_pub")

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
                "config": "fix_pub",
                "cv_model": "default",
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
                "config": "fix_pub",
                "cv_model": "default",
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
                "config": "var_pub",
                "cv_model": "default",
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
                "config": "fix_pub",
                "cv_model": "default",
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
                    "display_label": "Binsec/Rel 2",
                },
                {
                    "comparison_tool": "klee_cf",
                    "source_column": "klee_cf_default_4_fix_pub",
                    "display_label": "CT-Witness",
                },
            ],
        )

    def test_automatic_selection_marks_grouped_comparison_plots(self) -> None:
        best_summary = pd.DataFrame(
            [
                {
                    "comparison_tool": "abacus",
                    "tool_family": "abacus",
                    "source_column": "abacus_config_fix_pub",
                },
                {
                    "comparison_tool": "klee_cf",
                    "tool_family": "klee_cf",
                    "source_column": "klee_cf_rand_path_dfs_4_var_pub",
                },
                {
                    "comparison_tool": "klee_cf_sliced",
                    "tool_family": "klee_cf",
                    "source_column": "klee_cf_rand_path_dfs_4_sliced_var_pub",
                },
                {
                    "comparison_tool": "klee_eager",
                    "tool_family": "klee_eager",
                    "source_column": "klee_eager_rand_path_dfs_4_var_pub",
                },
            ]
        )

        selected = automatic_selection_summary(best_summary)
        groups_by_tool = {
            row["comparison_tool"]: row["plot_groups"]
            for row in selected.to_dict("records")
        }

        self.assertEqual(groups_by_tool["abacus"], "external")
        self.assertEqual(groups_by_tool["klee_cf"], "internal|external|slicing")
        self.assertEqual(groups_by_tool["klee_cf_sliced"], "internal|slicing")
        self.assertEqual(groups_by_tool["klee_eager"], "internal")

    def test_filter_tool_summary_for_plot_picks_slice_with_best_searcher_comparison(self) -> None:
        tool_summary = pd.DataFrame(
            [
                {
                    "curve_id": "C01",
                    "rank_within_tool": 1,
                    "source_column": "cfg_default_4_fix_pub_all",
                    "configuration_label": "searcher=default, sym_size=4, config=fix_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "default",
                    "sym_size": "4",
                    "config": "fix_pub",
                    "cv_model": "all",
                    "raw_suffix": "fix_pub",
                    "normalized_suffix": "fix_pub",
                    "insecure_locations_found": 5,
                    "min_time": 0.1,
                    "median_time": 0.3,
                    "max_time": 20.0,
                },
                {
                    "curve_id": "C02",
                    "rank_within_tool": 2,
                    "source_column": "cfg_dfs_4_fix_pub_all",
                    "configuration_label": "searcher=dfs, sym_size=4, config=fix_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "dfs",
                    "sym_size": "4",
                    "config": "fix_pub",
                    "cv_model": "all",
                    "raw_suffix": "fix_pub",
                    "normalized_suffix": "fix_pub",
                    "insecure_locations_found": 7,
                    "min_time": 0.1,
                    "median_time": 0.2,
                    "max_time": 12.0,
                },
                {
                    "curve_id": "C03",
                    "rank_within_tool": 3,
                    "source_column": "cfg_default_16_var_pub_all",
                    "configuration_label": "searcher=default, sym_size=16, config=var_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "default",
                    "sym_size": "16",
                    "config": "var_pub",
                    "cv_model": "all",
                    "raw_suffix": "var_pub",
                    "normalized_suffix": "var_pub",
                    "insecure_locations_found": 8,
                    "min_time": 0.1,
                    "median_time": 0.25,
                    "max_time": 18.0,
                },
                {
                    "curve_id": "C04",
                    "rank_within_tool": 4,
                    "source_column": "cfg_rand_path_dfs_16_var_pub_all",
                    "configuration_label": "searcher=random-path,dfs, sym_size=16, config=var_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "random-path,dfs",
                    "sym_size": "16",
                    "config": "var_pub",
                    "cv_model": "all",
                    "raw_suffix": "var_pub",
                    "normalized_suffix": "var_pub",
                    "insecure_locations_found": 8,
                    "min_time": 0.1,
                    "median_time": 0.2,
                    "max_time": 16.0,
                },
                {
                    "curve_id": "C05",
                    "rank_within_tool": 5,
                    "source_column": "cfg_all_4_fix_pub_false",
                    "configuration_label": "searcher=all, sym_size=4, config=fix_pub, cv_model=false",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "all",
                    "sym_size": "4",
                    "config": "fix_pub",
                    "cv_model": "false",
                    "raw_suffix": "fix_pub",
                    "normalized_suffix": "fix_pub",
                    "insecure_locations_found": 10,
                    "min_time": 0.1,
                    "median_time": 0.15,
                    "max_time": 8.0,
                },
            ]
        )

        plot_summary = filter_tool_summary_for_plot(tool_summary, "searcher")

        self.assertEqual(
            plot_summary["source_column"].tolist(),
            [
                "cfg_default_16_var_pub_all",
                "cfg_rand_path_dfs_16_var_pub_all",
            ],
        )

    def test_filter_tool_summary_for_plot_tie_breaks_by_best_max_time(self) -> None:
        tool_summary = pd.DataFrame(
            [
                {
                    "curve_id": "C01",
                    "rank_within_tool": 1,
                    "source_column": "cfg_default_4_fix_pub_all",
                    "configuration_label": "searcher=default, sym_size=4, config=fix_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "default",
                    "sym_size": "4",
                    "config": "fix_pub",
                    "cv_model": "all",
                    "raw_suffix": "fix_pub",
                    "normalized_suffix": "fix_pub",
                    "insecure_locations_found": 8,
                    "min_time": 0.1,
                    "median_time": 0.3,
                    "max_time": 14.0,
                },
                {
                    "curve_id": "C02",
                    "rank_within_tool": 2,
                    "source_column": "cfg_dfs_4_fix_pub_all",
                    "configuration_label": "searcher=dfs, sym_size=4, config=fix_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "dfs",
                    "sym_size": "4",
                    "config": "fix_pub",
                    "cv_model": "all",
                    "raw_suffix": "fix_pub",
                    "normalized_suffix": "fix_pub",
                    "insecure_locations_found": 7,
                    "min_time": 0.1,
                    "median_time": 0.4,
                    "max_time": 18.0,
                },
                {
                    "curve_id": "C03",
                    "rank_within_tool": 3,
                    "source_column": "cfg_default_16_var_pub_all",
                    "configuration_label": "searcher=default, sym_size=16, config=var_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "default",
                    "sym_size": "16",
                    "config": "var_pub",
                    "cv_model": "all",
                    "raw_suffix": "var_pub",
                    "normalized_suffix": "var_pub",
                    "insecure_locations_found": 8,
                    "min_time": 0.1,
                    "median_time": 0.2,
                    "max_time": 11.0,
                },
                {
                    "curve_id": "C04",
                    "rank_within_tool": 4,
                    "source_column": "cfg_dfs_16_var_pub_all",
                    "configuration_label": "searcher=dfs, sym_size=16, config=var_pub, cv_model=all",
                    "tool_family": "klee_cf",
                    "comparison_tool": "klee_cf",
                    "sliced": False,
                    "searcher": "dfs",
                    "sym_size": "16",
                    "config": "var_pub",
                    "cv_model": "all",
                    "raw_suffix": "var_pub",
                    "normalized_suffix": "var_pub",
                    "insecure_locations_found": 6,
                    "min_time": 0.1,
                    "median_time": 0.25,
                    "max_time": 13.0,
                },
            ]
        )

        plot_summary = filter_tool_summary_for_plot(tool_summary, "searcher")

        self.assertEqual(
            plot_summary["source_column"].tolist(),
            [
                "cfg_default_16_var_pub_all",
                "cfg_dfs_16_var_pub_all",
            ],
        )


if __name__ == "__main__":
    unittest.main()