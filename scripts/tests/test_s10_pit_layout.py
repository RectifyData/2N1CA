#!/usr/bin/env python3
"""Unit tests using synthetic Samsung PIT files; never touch real partitions."""
import importlib.util
import io
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "internal/s10_pit_layout.py"
SPEC = importlib.util.spec_from_file_location("s10_pit_layout", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
SIZES = {
    "BOOT": 131072, "SYSTEM": 4194304, "VENDOR": 2097152,
    "PRODUCT": 262144, "ODM": 65536,
}


def make_pit(sizes=None, magic=mod.MAGIC):
    sizes = sizes or SIZES
    header = bytearray(28)
    struct.pack_into("<II", header, 0, magic, len(sizes))
    records = bytearray()
    cursor = 2048
    for idx, (name, blocks) in enumerate(sizes.items()):
        record = bytearray(mod.ENTRY)
        struct.pack_into("<9I", record, 0, 0, 2, idx, 1, 1, cursor, blocks, 0, 0)
        record[36:36 + len(name)] = name.encode("ascii")
        records += record
        cursor += blocks
    return bytes(header + records)


class PitLayoutTests(unittest.TestCase):
    def test_parse_layout(self):
        result = mod.parse_pit(make_pit())
        self.assertEqual(result["BOOT"], 131072 * 512)
        self.assertIn("SYSTEM", result)
        self.assertNotIn("SUPER", result)

    def test_reject_bad_magic(self):
        with self.assertRaises(mod.LayoutError):
            mod.parse_pit(make_pit(magic=12))

    def test_reject_truncated_data(self):
        with self.assertRaises(mod.LayoutError):
            mod.parse_pit(make_pit()[:-1])

    def test_reject_duplicate_name(self):
        data = bytearray(make_pit())
        data[28 + 132 + 36:28 + 132 + 36 + 6] = b"BOOT\0\0"
        with self.assertRaises(mod.LayoutError):
            mod.parse_pit(data)

    def test_reject_unexpected_super(self):
        with self.assertRaises(mod.LayoutError):
            mod.validate_s10_layout(mod.parse_pit(make_pit({
                **SIZES, "SUPER": 10240
            })))

    def test_validate_expected_sizes(self):
        result = mod.validate_s10_layout(mod.parse_pit(make_pit()))
        self.assertEqual(result["SYSTEM"], SIZES["SYSTEM"] * 512)
        self.assertEqual(len(result), 5)

    def test_roundtrip_from_csc_tar(self):
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "CSC_SM-G975F.tar.md5"
            payload = make_pit()
            with tarfile.open(archive_path, "w") as archive:
                info = tarfile.TarInfo("S10_CONFIG.pit")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            actual, name = mod.read_pit_from_source(archive_path)
            self.assertEqual(actual, payload)
            self.assertEqual(name, "S10_CONFIG.pit")

    def test_missing_product_rejected(self):
        with self.assertRaises(mod.LayoutError):
            mod.validate_s10_layout(mod.parse_pit(make_pit({
                k: v for k, v in SIZES.items() if k != "PRODUCT"
            })))


if __name__ == "__main__":
    unittest.main()
