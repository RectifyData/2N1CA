#!/usr/bin/env python3
"""Synthetic-only tests: no extracted Samsung firmware is included."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "internal/s10_donor_thermal.py"
spec = importlib.util.spec_from_file_location("s10_donor_thermal", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ThermalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        feature = self.root / "system/system/etc/floating_feature.xml"
        feature.parent.mkdir(parents=True, exist_ok=True)
        feature.write_text("<features><SEC_FLOATING_FEATURE_SYSTEM_CONFIG_SIOP_POLICY_FILENAME>"
                           "siop_r13s</SEC_FLOATING_FEATURE_SYSTEM_CONFIG_SIOP_POLICY_FILENAME></features>")
        self.app = self.root / ("system/system/priv-app/SamsungDeviceHealthManagerService/"
                                "SamsungDeviceHealthManagerService.apk")
        self.app.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.app, "w") as z:
            z.writestr("assets/siop_r13s.xml", "<policy/>")
            z.writestr("assets/dvfs_policy_default.xml", "<policy/>")

    def test_firmware_assets_define_both_policies(self):
        data = mod.inspect(self.root)
        self.assertEqual(data["S10_DONOR_SSRM_POLICY"], "siop_r13s")
        self.assertEqual(data["S10_DONOR_DVFS_POLICY"], "dvfs_policy_default")

    def test_foreign_exynos2200_policy_is_rejected(self):
        feature = self.root / "system/system/etc/floating_feature.xml"
        feature.write_text(feature.read_text().replace("siop_r13s", "siop_r0s_exynos2200"))
        with self.assertRaises(mod.ThermalError):
            mod.inspect(self.root)

    def test_missing_policy_asset_is_not_accepted(self):
        with zipfile.ZipFile(self.app, "w") as z:
            z.writestr("assets/dvfs_policy_default.xml", "<policy/>")
        with self.assertRaises(mod.ThermalError):
            mod.inspect(self.root)

    def test_missing_dvfs_is_rejected(self):
        with zipfile.ZipFile(self.app, "w") as z:
            z.writestr("assets/siop_r13s.xml", "<policy/>")
        with self.assertRaises(mod.ThermalError):
            mod.inspect(self.root)


if __name__ == "__main__":
    unittest.main()
