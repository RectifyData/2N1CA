#!/usr/bin/env python3
"""Offline tests for 2N1CA S10 framework adaptation contracts."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "internal/s10_framework_audit.py"
SPEC = importlib.util.spec_from_file_location("s10_framework_audit", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
SOURCE = Path(__file__).resolve().parents[2]


class S10FrameworkTests(unittest.TestCase):
    def test_every_s10_target_overlay_and_feature_contract(self):
        for device in AUDIT.TARGETS:
            with self.subTest(device=device):
                self.assertEqual(AUDIT.static_audit(SOURCE, device), [])

    def test_real_target_files_are_required(self):
        with tempfile.TemporaryDirectory() as root:
            errors = AUDIT.static_audit(Path(root), "beyond2lte")
            self.assertTrue(any("E700" in x for x in errors))

    def test_missing_framework_and_hal_documents_detected(self):
        with tempfile.TemporaryDirectory() as root:
            errors = AUDIT.workdir_audit(Path(root), "beyond2lte")
            for code in ("E720", "E722", "E723", "E724", "E725", "E726", "E727", "E728"):
                self.assertTrue(any(code in x for x in errors), (code, errors))

    def test_vendor_donor_identity_is_detected(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            file = work / "vendor/build.prop"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("ro.product.vendor.device=o1s\n")
            errors = AUDIT.workdir_audit(work, "beyond2lte")
            self.assertTrue(any("E722" in x for x in errors))

    def test_system_ui_with_invalid_zip_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            path = work / AUDIT.SYSTEM_UI_PATHS[0]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"not an apk")
            errors = AUDIT.workdir_audit(work, "beyond2lte")
            self.assertTrue(any("E725" in x for x in errors))

    def test_valid_synthetic_archives_do_not_raise_archive_error(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            for p in AUDIT.FRAMEWORK_ARCHIVES:
                dest = work / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(dest, "w") as archive:
                    archive.writestr("classes.dex", b"synthetic")
            errors = AUDIT.workdir_audit(work, "beyond2lte")
            self.assertFalse(any("E724" in x for x in errors))


    def test_missing_target_thermal_policy_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as root:
            work = Path(root)
            health = work / (
                "system/system/priv-app/SamsungDeviceHealthManagerService/"
                "SamsungDeviceHealthManagerService.apk"
            )
            health.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(health, "w") as archive:
                archive.writestr("assets/ssrm_s22.xml", "<resources/>")
            errors = AUDIT.workdir_audit(work, "beyond2lte")
            self.assertTrue(any("E734" in x for x in errors), errors)


    def test_donor_camera_data_cannot_replace_stock_s10_camera_data(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            stock = root_path / "stock"
            work = root_path / "work"
            relative = "system/system/cameradata/camera-feature.xml"
            stock_file = stock / relative
            current = work / relative
            stock_file.parent.mkdir(parents=True, exist_ok=True)
            current.parent.mkdir(parents=True, exist_ok=True)
            stock_file.write_text("<resources><local name='S10' /></resources>")
            current.write_text("<resources><local name='S22' /></resources>")
            errors = AUDIT.workdir_audit(work, "beyond2lte", stock)
            self.assertTrue(any("E736" in x for x in errors), errors)
            current.write_bytes(stock_file.read_bytes())
            errors = AUDIT.workdir_audit(work, "beyond2lte", stock)
            self.assertFalse(any("E735" in x or "E736" in x for x in errors), errors)


if __name__ == "__main__":
    unittest.main()
