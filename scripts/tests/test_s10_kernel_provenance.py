#!/usr/bin/env python3
"""Offline boot build provenance tests; all images are synthetic fixtures."""
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

modpath = Path(__file__).resolve().parents[1] / "internal/s10_kernel_provenance.py"
spec = importlib.util.spec_from_file_location("s10_kernel_provenance", modpath)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class KernelProvenanceTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = Path(t.name)
        data = bytearray(8192)
        data[:8] = b"ANDROID!"
        struct.pack_into("<I", data, 8, 1024)
        struct.pack_into("<I", data, 40, 1)
        self.boot = self.base / "boot.img"
        self.boot.write_bytes(data)
        self.makefile = self.base / "Makefile"
        self.makefile.write_text("VERSION = 4\nPATCHLEVEL = 14\nSUBLEVEL = 333\n")
        self.kwargs = {
            "boot": self.boot, "target": "beyond2lte",
            "commit": "a" * 40, "run_id": 123,
            "makefile": self.makefile,
        }

    def test_records_actual_digest_without_approval(self):
        result = m.record(**self.kwargs)
        self.assertFalse(result["hardware_boot_verified"])
        self.assertFalse(result["is_flash_safe"])
        self.assertEqual(result["kernel_source_version"], "4.14.333")

    def test_rejects_wrong_header(self):
        self.boot.write_bytes(b"INVALID!" + self.boot.read_bytes()[8:])
        with self.assertRaises(ValueError):
            m.record(**self.kwargs)

    def test_rejects_unpinned_commit(self):
        self.kwargs["commit"] = "unverified"
        with self.assertRaises(ValueError):
            m.record(**self.kwargs)

    def test_rejects_missing_kernel_makefile(self):
        self.makefile.unlink()
        with self.assertRaises(ValueError):
            m.record(**self.kwargs)


if __name__ == "__main__":
    unittest.main()
