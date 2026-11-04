#!/usr/bin/env python3
"""Safety regression tests for Exynos S10 donor version selection."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "internal/validate_oneui_donor.py"
spec = importlib.util.spec_from_file_location("donor", path)
donor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(donor)


class DonorTests(unittest.TestCase):
    def test_android_16_one_ui_85(self):
        donor.validate({"ro.build.version.sdk": "36", "ro.build.version.oneui": "80500"})

    def test_one_ui_80_fails(self):
        with self.assertRaises(donor.DonorError):
            donor.validate({"ro.build.version.sdk": "36", "ro.build.version.oneui": "80000"})

    def test_one_ui_9_fails(self):
        with self.assertRaises(donor.DonorError):
            donor.validate({"ro.build.version.sdk": "37", "ro.build.version.oneui": "90000"})

    def test_missing_value_fails(self):
        with self.assertRaises(donor.DonorError):
            donor.validate({"ro.build.version.sdk": "36"})

    def test_patch_level_80501_allowed(self):
        donor.validate({"ro.build.version.sdk": "36", "ro.build.version.oneui": "80501"})


if __name__ == "__main__":
    unittest.main()
