#!/usr/bin/env python3
"""Synthetic-only S10 vendor/ODM init dependency tests."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "internal/s10_init_audit.py"
spec = importlib.util.spec_from_file_location("s10_init_audit", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class S10InitAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "vendor/etc/init").mkdir(parents=True)

    def test_valid_vendor_hal_executable(self):
        executable = self.root / "vendor/bin/hw/android.hardware.test-service"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"synthetic")
        (self.root / "vendor/etc/init/test.rc").write_text(
            "service fake /vendor/bin/hw/android.hardware.test-service\n"
            "    class hal\n"
            "    user system\n"
        )
        report = module.inspect(self.root)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["services_checked"], 1)

    def test_missing_hal_executable_rejected(self):
        (self.root / "vendor/etc/init/test.rc").write_text(
            "service fake /vendor/bin/hw/nonexistent-service\n"
        )
        result = module.inspect(self.root)
        self.assertTrue(any("E782" in x for x in result["errors"]))

    def test_missing_vendor_init_directory_rejected(self):
        (self.root / "vendor/etc/init").rmdir()
        self.assertTrue(any("E780" in x for x in module.inspect(self.root)["errors"]))

    def test_unresolved_odm_import_is_warning(self):
        (self.root / "vendor/etc/init/test.rc").write_text(
            "import /odm/etc/init/vendor.secret.rc\n"
        )
        result = module.inspect(self.root)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("W787" in x for x in result["warnings"]))

    def test_model_specific_dynamic_binary_not_assumed_present(self):
        (self.root / "vendor/etc/init/test.rc").write_text(
            "service fake /vendor/bin/hw/vendor.${ro.boot.hardware}.service\n"
        )
        result = module.inspect(self.root)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("W785" in x for x in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
