#!/usr/bin/env python3
"""Synthetic-only Keymaster/Gatekeeper VINTF regression tests."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "internal/s10_security_audit.py"
spec = importlib.util.spec_from_file_location("s10_security_audit", MOD)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def create(root: Path, names: list[tuple[str, str]]):
    file = root / "vendor/etc/vintf/manifest.xml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("<manifest version='2.0' type='device'>"
                    + "".join(
                        f"<hal format='hidl'><name>{name}</name>"
                        f"<version>{version}</version></hal>"
                        for name, version in names
                    ) + "</manifest>")


class SecurityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.stock = self.root / "stock"
        self.work = self.root / "work"
        self.hals = [("android.hardware.keymaster", "4.0"),
                     ("android.hardware.gatekeeper", "1.0")]
        create(self.stock, self.hals)
        create(self.work, self.hals)

    def test_preserved_security_hals_are_only_static_evidence(self):
        result = audit.inspect(self.stock, self.work)
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["runtime_tee_verified"])

    def test_missing_keymaster_rejected(self):
        create(self.work, self.hals[1:])
        self.assertTrue(any("E784" in x for x in audit.inspect(self.stock, self.work)["errors"]))

    def test_missing_stock_gatekeeper_rejected(self):
        create(self.stock, self.hals[:1])
        self.assertTrue(any("E783" in x for x in audit.inspect(self.stock, self.work)["errors"]))

    def test_changed_keymaster_version_rejected(self):
        create(self.work, [("android.hardware.keymaster", "4.1"), self.hals[1]])
        self.assertTrue(any("E785" in x for x in audit.inspect(self.stock, self.work)["errors"]))

    def test_secure_element_cannot_disappear(self):
        e = ("android.hardware.secure_element", "1.2")
        create(self.stock, self.hals + [e])
        self.assertTrue(any("E784" in x for x in audit.inspect(self.stock, self.work)["errors"]))


if __name__ == "__main__":
    unittest.main()
