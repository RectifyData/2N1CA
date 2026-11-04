#!/usr/bin/env python3
"""Offline checkvintf integration tests; mock binaries never modify devices."""
import importlib.util
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "internal/s10_checkvintf.py"
spec = importlib.util.spec_from_file_location("s10_checkvintf", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class S10VintfTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for name in ("system/system", "vendor", "product", "odm"):
            (self.root / name).mkdir(parents=True)

    def test_dirmap_targets_real_legacy_partitions(self):
        args = mod.assemble(self.root, "checkvintf")
        self.assertIn("--check-compat", args)
        self.assertIn(f"/vendor:{(self.root / 'vendor').resolve()}", args)
        self.assertIn(f"/system:{(self.root / 'system/system').resolve()}", args)
        self.assertNotIn("/super:", " ".join(args))
        self.assertIn("ro.product.first_api_level=28", args)

    def test_must_have_vendor_for_real_check(self):
        (self.root / "vendor").rmdir()
        with self.assertRaises(ValueError):
            mod.assemble(self.root)

    def test_duplicate_product_paths_rejected(self):
        (self.root / "system/system/product").mkdir(parents=True)
        with self.assertRaises(ValueError):
            mod.assemble(self.root)

    def test_missing_checker_is_hard_failure_when_required(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--work-dir", str(self.root),
             "--tool", "missing-s10-vintf-test-command", "--require-tool"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("E760", result.stderr)

    def test_checker_rejection_blocks_candidate(self):
        executable = self.root / "fake-checkvintf"
        executable.write_text("#!/bin/sh\necho INCOMPATIBLE >&2\nexit 1\n")
        executable.chmod(0o755)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--work-dir", str(self.root),
             "--tool", str(executable), "--require-tool"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("E761", result.stderr)

    def test_checker_success_is_not_boot_certification(self):
        executable = self.root / "fake-checkvintf-ok"
        executable.write_text("#!/bin/sh\necho COMPATIBLE\nexit 0\n")
        executable.chmod(0o755)
        report = self.root / "report.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--work-dir", str(self.root),
             "--tool", str(executable), "--require-tool", "--report", str(report)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"device_boot_verified": false', report.read_text())


if __name__ == "__main__":
    unittest.main()
