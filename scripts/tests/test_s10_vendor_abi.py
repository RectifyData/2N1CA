#!/usr/bin/env python3
"""Synthetic fixtures only; no real S10 firmware or hardware claim."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "internal/s10_vendor_abi.py"
spec = importlib.util.spec_from_file_location("s10_vendor_abi", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
HASH = "a" * 64


class VendorABITests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        for name in ("vendor", "system/system"):
            (self.root / name).mkdir(parents=True)
        (self.root / "vendor/build.prop").write_text(
            "ro.product.vendor.device=beyond2lte\n"
            "ro.build.version.sdk=31\nro.vndk.version=31\n"
            "ro.product.first_api_level=28\nro.board.api_level=28\n"
        )

    def test_manifest_is_bound_to_vendor_properties(self):
        result = mod.collect(self.root, HASH)
        self.assertEqual(result["S10_VENDOR_PLATFORM_SDK"], "31")
        self.assertEqual(result["S10_VENDOR_VNDK"], "31")
        self.assertEqual(result["S10_VENDOR_FIRST_API"], "28")
        mod.write_manifest(result, self.root / "out/abi.env")
        self.assertIn('S10_VENDOR_FIRMWARE_SHA256="' + HASH + '"',
                      (self.root / "out/abi.env").read_text())

    def test_missing_board_is_error(self):
        p = self.root / "vendor/build.prop"
        p.write_text(p.read_text().replace("ro.board.api_level=28\n", ""))
        with self.assertRaisesRegex(mod.ABIError, "ro.board.api_level"):
            mod.collect(self.root, HASH)

    def test_conflicting_vndk_blocks(self):
        (self.root / "vendor/default.prop").write_text("ro.vndk.version=30\n")
        with self.assertRaisesRegex(mod.ABIError, "Conflicting"):
            mod.collect(self.root, HASH)

    def test_vendor_not_s10_rejected(self):
        p = self.root / "vendor/build.prop"
        p.write_text(p.read_text().replace("beyond2lte", "r13s"))
        with self.assertRaises(mod.ABIError):
            mod.collect(self.root, HASH)

    def test_no_firmware_hash_rejected(self):
        with self.assertRaises(mod.ABIError):
            mod.collect(self.root, "not-a-hash")


if __name__ == "__main__":
    unittest.main()
