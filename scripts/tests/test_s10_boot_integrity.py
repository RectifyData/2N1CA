#!/usr/bin/env python3
"""Synthetic boot integrity fixtures. No real device or hardware verification."""
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "internal/s10_boot_integrity.py"
spec = importlib.util.spec_from_file_location("s10_boot_integrity", MODULE)
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class BootEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.device = "beyond2lte"
        self.image = self.root / "boot.img"
        header = bytearray(4096)
        header[:8] = b"ANDROID!"
        struct.pack_into("<I", header, 8, 1024)
        struct.pack_into("<I", header, 40, 1)
        self.image.write_bytes(bytes(header) + b"k" * 4096)
        self.report = self.root / "device-test.json"
        self.report.write_text(json.dumps({
            "device": self.device, "boot_completed": True,
            "hardware_verified": True, "synthetic_fixture": True,
        }))
        self.manifest = self.root / "boot-approval.json"
        self.entry = {
            "target": self.device,
            "boot_sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
            "kernel_commit": "a" * 40,
            "workflow_run_id": 123456,
            "kernel_version": "4.14.333",
            "test_report_sha256": hashlib.sha256(self.report.read_bytes()).hexdigest(),
        }
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.entry))

    def test_correct_hash_and_provenance(self):
        result = boot.verify_boot(self.image, self.manifest, self.device, self.report)
        self.assertTrue(result["hash_matched"])
        self.assertFalse(result["on_device_boot_verified_by_this_tool"])

    def test_mutation_of_one_boot_byte_is_rejected(self):
        raw = bytearray(self.image.read_bytes())
        raw[-1] ^= 1
        self.image.write_bytes(raw)
        with self.assertRaisesRegex(boot.BootError, "E636"):
            boot.verify_boot(self.image, self.manifest, self.device, self.report)

    def test_missing_manifest_rejected(self):
        self.manifest.unlink()
        with self.assertRaisesRegex(boot.BootError, "E620"):
            boot.verify_boot(self.image, self.manifest, self.device, self.report)

    def test_wrong_target_rejected(self):
        with self.assertRaisesRegex(boot.BootError, "E622"):
            boot.verify_boot(self.image, self.manifest, "beyond1lte", self.report)

    def test_report_mutation_rejected(self):
        self.report.write_text(self.report.read_text() + "\n")
        with self.assertRaisesRegex(boot.BootError, "E628"):
            boot.verify_boot(self.image, self.manifest, self.device, self.report)

    def test_report_without_hardware_evidence_rejected(self):
        self.report.write_text(json.dumps({
            "device": self.device, "boot_completed": True,
            "hardware_verified": False,
        }))
        self.entry["test_report_sha256"] = hashlib.sha256(self.report.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaisesRegex(boot.BootError, "E631"):
            boot.verify_boot(self.image, self.manifest, self.device, self.report)

    def test_missing_workflow_run_id_rejected(self):
        self.entry["workflow_run_id"] = 0
        self.write_manifest()
        with self.assertRaisesRegex(boot.BootError, "E625"):
            boot.load_evidence(self.manifest, self.device, self.report)


if __name__ == "__main__":
    unittest.main()
