#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.experiments.common import REPO_ROOT
from scripts.experiments.run_experiments import resolve_campaign_path
from scripts.experiments.run_experiments_abacus import resolve_host_path


class RunExperimentsPathResolutionTest(unittest.TestCase):
    def test_resolve_campaign_path_expands_environment_variables(self) -> None:
        with patch.dict(os.environ, {"SLURM_JOB_ID": "11658"}, clear=False):
            resolved = resolve_campaign_path("/lstor/slurmjobs/$SLURM_JOB_ID")

        self.assertEqual(resolved, Path("/lstor/slurmjobs/11658"))

    def test_resolve_campaign_path_keeps_repo_relative_behavior(self) -> None:
        with patch.dict(os.environ, {"SLURM_JOB_ID": "11658"}, clear=False):
            resolved = resolve_campaign_path("results/$SLURM_JOB_ID")

        self.assertEqual(resolved, (REPO_ROOT / "results" / "11658").resolve())

    def test_resolve_host_path_expands_environment_variables(self) -> None:
        with patch.dict(os.environ, {"SLURM_JOB_ID": "11658"}, clear=False):
            resolved = resolve_host_path("/lstor/slurmjobs/$SLURM_JOB_ID")

        self.assertEqual(resolved, Path("/lstor/slurmjobs/11658"))

    def test_resolve_host_path_keeps_repo_relative_behavior(self) -> None:
        with patch.dict(os.environ, {"SLURM_JOB_ID": "11658"}, clear=False):
            resolved = resolve_host_path("results/$SLURM_JOB_ID")

        self.assertEqual(resolved, (REPO_ROOT / "results" / "11658").resolve())


if __name__ == "__main__":
    unittest.main()