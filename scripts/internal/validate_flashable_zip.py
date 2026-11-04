#!/usr/bin/env python3
"""Reject malformed or dangerous recovery ZIPs before distribution."""
import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath

S10 = {"beyond0lte", "beyond1lte", "beyond2lte", "beyondx"}
S10_SYSTEM = {"system", "vendor", "product", "odm"}
S10_IMAGES = S10_SYSTEM | {"boot", "dt", "dtbo"}
REQUIRED = ("build_info.txt", "META-INF/com/android/metadata",
            "META-INF/com/google/android/update-binary",
            "META-INF/com/google/android/updater-script")
EXTRACT = re.compile(r'package_extract_file\(\s*"([^"]+)"')
BLOCK = re.compile(r'block_image_update\(\s*[^,]+,\s*package_extract_file\(\s*"([^"]+)"\s*\),\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)')
WRITE = re.compile(r'package_extract_file\(\s*"([^"]+)"\s*,\s*"(/dev/block/[^"]+)"\s*\)')


def properties(raw):
    return dict(line.split("=", 1) for line in raw.splitlines()
                if "=" in line and not line.startswith("#"))


def parse_layout(path):
    """Load sizes from the PIT-generated allowlist, never execute a shell file."""
    sizes = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        found = re.fullmatch(r"TARGET_(SYSTEM|VENDOR|PRODUCT|ODM|BOOT)_PARTITION_SIZE=([0-9]+)", line)
        if found:
            name, raw = found.groups()
            if name in sizes:
                raise ValueError(f"Duplicate partition capacity: {name}")
            size = int(raw)
            if size <= 0 or size % 4096 != 0:
                raise ValueError(f"Unaligned or invalid partition capacity: {name}={size}")
            sizes[name] = size
        elif not re.fullmatch(r'S10_(SOURCE_PIT|TARGET_FIRMWARE)_SHA256="[0-9a-f]{64}"', line):
            raise ValueError(f"Unknown field in stock PIT layout: {line[:64]}")
    if set(sizes) != {"SYSTEM", "VENDOR", "PRODUCT", "ODM", "BOOT"}:
        raise ValueError("Stock PIT layout must contain all five allowed partitions")
    return sizes


def parse_ranges(text, capacity_blocks=None):
    """Parse Android sdat range set, first token gives number of endpoints."""
    try:
        values = [int(v) for v in text.split(",")]
        if len(values) < 3 or values[0] == 0 or values[0] != len(values) - 1 or values[0] % 2:
            raise ValueError("invalid number of range endpoints")
        previous = 0
        total = 0
        for start, end in zip(values[1::2], values[2::2]):
            if start < previous or end <= start or start < 0:
                raise ValueError("unordered/empty transfer range")
            if capacity_blocks is not None and end > capacity_blocks:
                raise ValueError(f"transfer exceeds partition capacity ({end} > {capacity_blocks})")
            total += end - start
            previous = end
        return total
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid transfer range set: {exc}") from exc


def inspect_transfers(archive, filenames, capacities, error):
    for partition in sorted({f[:-len(".transfer.list")] for f in filenames
                             if f.endswith(".transfer.list")}):
        name = f"{partition}.transfer.list"
        try:
            lines = [line.strip() for line in archive.read(name).decode("ascii").splitlines()
                     if line.strip()]
            if len(lines) < 4 or not all(v.isdecimal() for v in lines[:4]):
                raise ValueError("missing or corrupt sdat header")
            version, total_blocks, _, _ = map(int, lines[:4])
            if version not in (3, 4):
                raise ValueError(f"unsupported sdat version {version}")
            if total_blocks < 0:
                raise ValueError("negative block count")
            limit = None if capacities is None else capacities[partition.upper()] // 4096
            new_blocks = 0
            for command in lines[4:]:
                opcode, *arguments = command.split()
                if opcode not in ("new", "zero", "erase"):
                    raise ValueError(f"unsupported full-OTA transfer operation {opcode!r}")
                if len(arguments) != 1:
                    raise ValueError(f"invalid operand count for {opcode}")
                count = parse_ranges(arguments[0], limit)
                if opcode == "new":
                    new_blocks += count
            if new_blocks > total_blocks:
                raise ValueError(f"new blocks exceed header count {total_blocks}")
            raw = f"{partition}.new.dat"
            # For an uncompressed payload the declared new ranges must exactly
            # match bytes to be written. Empty headers are used in synthetic tests.
            if raw in filenames and new_blocks:
                length = archive.getinfo(raw).file_size
                if length != new_blocks * 4096:
                    raise ValueError(f"uncompressed payload bytes {length} != {new_blocks * 4096}")
        except (ValueError, UnicodeError, KeyError) as exc:
            error("E540", f"{partition} transfer validation: {exc}")


def validate(path, expected=None, deep=False, layout=None):
    problems = []
    def error(code, message):
        problems.append(f"{code}: {message}")

    try:
        with zipfile.ZipFile(path) as z:
            files = set()
            for entry in z.infolist():
                name = entry.filename
                if name.startswith("/") or "\\" in name or ".." in PurePosixPath(name).parts or "//" in name:
                    error("E500", f"Unsafe ZIP path: {name}")
                if not entry.is_dir():
                    if name in files:
                        error("E501", f"Duplicate ZIP entry: {name}")
                    files.add(name)
            for required in REQUIRED:
                if required not in files:
                    error("E502", f"Missing {required}")
                elif z.getinfo(required).file_size == 0:
                    error("E503", f"Empty {required}")
            if any(p not in files for p in REQUIRED):
                return problems
            info = properties(z.read("build_info.txt").decode("utf-8"))
            meta = properties(z.read("META-INF/com/android/metadata").decode("utf-8"))
            script = z.read("META-INF/com/google/android/updater-script").decode("utf-8")
            device = info.get("device", "")
            if not re.fullmatch("[A-Za-z0-9_-]+", device):
                error("E504", "Invalid or missing target device")
            if expected and device != expected:
                error("E505", f"Package targets {device}, expected {expected}")
            if meta.get("pre-device") != device:
                error("E506", "OTA metadata device does not match")
            if meta.get("ota-type") != "BLOCK":
                error("E507", "Missing BLOCK OTA type")
            if not info.get("version"):
                error("E508", "Missing ROM version")

            for filename in EXTRACT.findall(script):
                if filename not in files:
                    error("E509", f"Updater references absent {filename}")
            partitions = {name[:-len(".transfer.list")] for name in files
                          if name.endswith(".transfer.list")}
            for partition in partitions:
                options = {f"{partition}.new.dat", f"{partition}.new.dat.br"} & files
                if len(options) != 1:
                    error("E510", f"{partition} must contain one new.dat payload")
                if f"{partition}.patch.dat" not in files:
                    error("E511", f"{partition} missing patch.dat")
                if f'"{partition}.transfer.list"' not in script:
                    error("E512", f"{partition} not referenced by updater")
            for transfer, data, patch in BLOCK.findall(script):
                for value in (transfer, data, patch):
                    if value not in files:
                        error("E513", f"Block update references missing {value}")
            if partitions and not BLOCK.search(script):
                error("E514", "ZIP contains block payloads without a block updater")

            if device in S10:
                capacities = None
                if layout is not None:
                    try:
                        capacities = parse_layout(Path(layout))
                    except (OSError, ValueError) as exc:
                        error("E541", f"Invalid or missing source PIT capacity manifest: {exc}")
                if capacities is not None:
                    for name in files:
                        if name.endswith(".img") and "/" not in name:
                            partition = name[:-4].upper()
                            if partition in capacities and z.getinfo(name).file_size > capacities[partition]:
                                error("E542", f"{name} larger than PIT partition capacity")
                inspect_transfers(z, files, capacities, error)
                if ("dynamic_partitions_op_list" in files
                        or "update_dynamic_partitions(" in script
                        or "super.img" in files):
                    error("E520", "S10 legacy layout cannot use dynamic partitions")
                for partition in partitions - S10_SYSTEM:
                    error("E521", f"Unsupported S10 partition: {partition}")
                for file in files:
                    if file.endswith(".img") and "/" not in file:
                        if file[:-4] not in S10_IMAGES:
                            error("E522", f"Unsupported S10 image: {file}")
                for payload, destination in WRITE.findall(script):
                    if destination.rstrip("/").split("/")[-1] not in S10_IMAGES:
                        error("E523", f"Unsafe write: {payload} to {destination}")
                if "ro.product.device" not in script and "ro.boot.em.model" not in script:
                    error("E524", "S10 installer has no device assertion")
                for operation in ("mark_header_bt(", "write_data_bt(", "format(\"/data",
                                  "format(\"/efs", "delete_recursive(\"/data"):
                    if operation in script:
                        error("E525", f"Unsafe S10 operation: {operation}")
            if deep:
                bad = z.testzip()
                if bad:
                    error("E530", f"ZIP CRC failure: {bad}")
    except (OSError, ValueError, UnicodeError, EOFError, zipfile.BadZipFile) as ex:
        error("E531", f"Could not validate ZIP: {ex}")
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("zip", type=Path)
    p.add_argument("--expected-device")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--layout", type=Path, help="PIT-generated partition size manifest")
    args = p.parse_args()
    problems = validate(args.zip, args.expected_device, args.deep, args.layout)
    for problem in problems:
        print(f"2N1CA installer validation failed [{problem}]", file=sys.stderr)
    if problems:
        return 2
    print(f"2N1CA installer validation passed: {args.zip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
