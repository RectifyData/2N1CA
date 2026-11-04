#!/usr/bin/env python3
"""Synthetic installer tests. Nothing is flashed."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "internal/validate_flashable_zip.py"
SPEC = importlib.util.spec_from_file_location("validator", PATH)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

INSTALLER = (
    'getprop("ro.product.device") == "beyond2lte" || abort("Wrong model");\n'
    'block_image_update("/dev/block/by-name/system", '
    'package_extract_file("system.transfer.list"), '
    '"system.new.dat", "system.patch.dat") || abort("Write failed");\n'
)
VALID = {
    "build_info.txt": b"device=beyond2lte\nversion=2N1CA-test\n",
    "META-INF/com/android/metadata": b"pre-device=beyond2lte\nota-type=BLOCK\n",
    "META-INF/com/google/android/update-binary": b"synthetic-updater",
    "META-INF/com/google/android/updater-script": INSTALLER.encode(),
    "system.transfer.list": b"4\n0\n0\n0\n",
    "system.new.dat": b"synthetic-payload",
    "system.patch.dat": b"",
}


class InstallerZipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.zip_path = Path(self.tmp.name) / "synthetic.zip"

    def check(self, remove=(), extras=None, expected="beyond2lte"):
        entries = {k: v for k, v in VALID.items() if k not in remove}
        entries.update(extras or {})
        with zipfile.ZipFile(self.zip_path, "w") as z:
            for name, data in entries.items():
                z.writestr(name, data)
        return " ".join(validator.validate(self.zip_path, expected, deep=True))

    def test_good_legacy_s10_zip(self):
        self.assertEqual(self.check(), "")

    def test_wrong_device_rejected(self):
        self.assertIn("E505", self.check(expected="beyond0lte"))

    def test_missing_updater_rejected(self):
        self.assertIn("E502", self.check(remove=["META-INF/com/google/android/update-binary"]))

    def test_missing_new_data_rejected(self):
        self.assertIn("E510", self.check(remove=["system.new.dat"]))

    def test_missing_patch_data_rejected(self):
        self.assertIn("E511", self.check(remove=["system.patch.dat"]))

    def test_invalid_metadata_rejected(self):
        self.assertIn("E506", self.check(extras={
            "META-INF/com/android/metadata": b"pre-device=beyond1lte\nota-type=BLOCK\n"
        }))

    def test_dynamic_partition_rejected(self):
        self.assertIn("E520", self.check(extras={
            "dynamic_partitions_op_list": b"remove_all_groups\n"
        }))

    def test_protected_efs_write_rejected(self):
        self.assertIn("E523", self.check(extras={
            "META-INF/com/google/android/updater-script": (
                INSTALLER + 'package_extract_file("efs.img", "/dev/block/by-name/efs");'
            ).encode(), "efs.img": b"danger"
        }))

    def test_missing_block_reference_rejected(self):
        self.assertIn("E513", self.check(extras={
            "META-INF/com/google/android/updater-script":
                INSTALLER.replace('"system.patch.dat"', '"missing.patch.dat"').encode()
        }))

    def test_path_traversal_rejected(self):
        self.assertIn("E500", self.check(extras={"../unsafe-file": b"unsafe"}))


if __name__ == "__main__":
    unittest.main()
