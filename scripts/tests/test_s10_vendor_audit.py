#!/usr/bin/env python3
"""Vendor baseline tests: no real hardware accessed."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "internal/s10_vendor_audit.py"
spec = importlib.util.spec_from_file_location("vendor_audit", path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

FSTAB = """
/dev/block/by-name/system /system ext4 ro wait
/dev/block/by-name/vendor /vendor ext4 ro wait
/dev/block/by-name/product /product ext4 ro wait
/dev/block/by-name/odm /odm ext4 ro wait
"""


class VendorAuditTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        for folder in audit.REQUIRED_DIRS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        (self.root / "vendor/etc/vintf").mkdir()
        (self.root / "vendor/etc/fstab.exynos9820").write_text(FSTAB)
        (self.root / "vendor/etc/vintf/manifest.xml").write_text("<manifest/>")
        (self.root / "vendor/etc/selinux").mkdir()
        for options in audit.CANDIDATE_HAL.values():
            file = self.root / "vendor" / options[0]
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"synthetic HAL fixture")

    def test_legacy_vendor_structure(self):
        self.assertEqual(audit.inspect(self.root)["errors"], [])

    def test_missing_required_hal_is_blocking(self):
        (self.root / "vendor/lib64/hw/gralloc.exynos9820.so").unlink()
        self.assertIn("E650", " ".join(audit.inspect(self.root)["errors"]))

    def test_missing_selinux_is_blocking(self):
        (self.root / "vendor/etc/selinux").rmdir()
        self.assertIn("E651", " ".join(audit.inspect(self.root)["errors"]))

    def test_missing_fstab_fails(self):
        (self.root / "vendor/etc/fstab.exynos9820").unlink()
        self.assertTrue(audit.inspect(self.root)["errors"])

    def test_dynamic_partitions_fail(self):
        path = self.root / "vendor/etc/fstab.exynos9820"
        path.write_text(FSTAB + "/dev/block/by-name/super /super ext4 ro logical\n")
        self.assertIn("E644", " ".join(audit.inspect(self.root)["errors"]))

    def test_invalid_vintf_fails(self):
        (self.root / "vendor/etc/vintf/manifest.xml").write_text("<bad")
        self.assertIn("E646", " ".join(audit.inspect(self.root)["errors"]))

    def test_missing_product_fails(self):
        (self.root / "vendor/etc/fstab.exynos9820").write_text(
            FSTAB.replace("/dev/block/by-name/product /product ext4 ro wait\n", ""))
        self.assertIn("E642", " ".join(audit.inspect(self.root)["errors"]))


if __name__ == "__main__":
    unittest.main()
