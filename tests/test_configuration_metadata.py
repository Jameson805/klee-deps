#!/usr/bin/env python3

from __future__ import annotations

import unittest

from tools.shared.configuration_metadata import derive_run_configuration


class ConfigurationMetadataTest(unittest.TestCase):
    def test_derive_run_configuration_uses_default_searcher_when_unspecified(self) -> None:
        metadata = derive_run_configuration(
            "klee_cf",
            "klee_cf_default_4",
            ["--sym-size", "4"],
        )

        self.assertEqual(metadata["searcher"], "default")


if __name__ == "__main__":
    unittest.main()