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
    def good_props(self):
        return {"ro.build.version.sdk": "36", "ro.build.version.oneui": "80500",
                "ro.product.model": "Galaxy S25 FE"}

    def good_vendor(self):
        return {"ro.board.platform": "s5e9945",
                "ro.product.vendor.model": "SM-S731B"}

    def test_android_16_one_ui_85(self):
        donor.validate(self.good_props(), self.good_vendor())

    def test_missing_vendor_properties_are_rejected(self):
        with self.assertRaises(donor.DonorError):
            donor.validate(self.good_props())

    def test_missing_board_property_is_rejected(self):
        with self.assertRaisesRegex(donor.DonorError, "ro.board.platform"):
            donor.validate(self.good_props(), {"ro.product.vendor.model": "SM-S731B"})

    def test_wrong_board_property_is_rejected(self):
        with self.assertRaises(donor.DonorError):
            donor.validate(self.good_props(), {"ro.board.platform": "exynos9820"})

    def test_conflicting_system_and_vendor_board_rejected(self):
        props = self.good_props()
        props["ro.board.platform"] = "wrong-board"
        with self.assertRaises(donor.DonorError):
            donor.validate(props, self.good_vendor())

    def test_missing_model_is_rejected(self):
        props = self.good_props()
        del props["ro.product.model"]
        with self.assertRaises(donor.DonorError):
            donor.validate(props, {"ro.board.platform": "s5e9945"})

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
        donor.validate({**self.good_props(), "ro.build.version.oneui": "80501"}, self.good_vendor())


if __name__ == "__main__":
    unittest.main()
