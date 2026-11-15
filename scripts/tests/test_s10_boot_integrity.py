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
            "hardware_verified": True, "synthetic_fixture": False,
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

    def make_experimental_manifest(self):
        path = self.root / "kernel-build-provenance.json"
        path.write_text(json.dumps({
            "target": self.device,
            "boot_sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
            "kernel_commit": "a" * 40,
            "workflow_run_id": 9876,
            "kernel_source_version": "4.14.333",
            "boot_header_version": 1,
            "boot_file_size": self.image.stat().st_size,
            "compilation_verified": True,
            "hardware_boot_verified": False,
            "device_verified": False,
            "is_flash_safe": False,
        }))
        return path

    def test_compiled_boot_accepted_without_previous_boot_report(self):
        manifest = self.make_experimental_manifest()
        result = boot.verify_experimental_boot(self.image, manifest, self.device)
        self.assertTrue(result["compilation_verified"])
        self.assertFalse(result["hardware_boot_verified"])

    def test_changed_compiled_boot_bytes_rejected(self):
        manifest = self.make_experimental_manifest()
        data = bytearray(self.image.read_bytes())
        data[-1] ^= 0xff
        self.image.write_bytes(data)
        with self.assertRaisesRegex(boot.BootError, "E653"):
            boot.verify_experimental_boot(self.image, manifest, self.device)

    def test_compiled_boot_wrong_device_rejected(self):
        manifest = self.make_experimental_manifest()
        with self.assertRaisesRegex(boot.BootError, "E643"):
            boot.verify_experimental_boot(self.image, manifest, "beyond1lte")

    def test_compiled_boot_needs_compilation_proof(self):
        manifest = self.make_experimental_manifest()
        payload = json.loads(manifest.read_text())
        payload["compilation_verified"] = False
        manifest.write_text(json.dumps(payload))
        with self.assertRaisesRegex(boot.BootError, "E648"):
            boot.verify_experimental_boot(self.image, manifest, self.device)

    def test_tester_manifest_cannot_claim_safety(self):
        manifest = self.make_experimental_manifest()
        payload = json.loads(manifest.read_text())
        payload["is_flash_safe"] = True
        manifest.write_text(json.dumps(payload))
        with self.assertRaisesRegex(boot.BootError, "E648"):
            boot.verify_experimental_boot(self.image, manifest, self.device)

    def test_correct_hash_and_provenance(self):
        result = boot.verify_boot(self.image, self.manifest, self.device, self.report)
        self.assertTrue(result["hash_matched"])
        self.assertFalse(result["on_device_boot_verified_by_this_tool"])

    def test_synthetic_report_cannot_authorize_flashable_build(self):
        self.report.write_text(json.dumps({
            "device": self.device, "boot_completed": True,
            "hardware_verified": True, "synthetic_fixture": True,
        }))
        self.entry["test_report_sha256"] = hashlib.sha256(self.report.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaisesRegex(boot.BootError, "E637"):
            boot.load_evidence(self.manifest, self.device, self.report)

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
