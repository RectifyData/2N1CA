#!/usr/bin/env python3
"""Parse Samsung PIT partition capacities without writing to a device.

Reference: Heimdall libpit (28-byte header; 132-byte entries; LE integers).
Outputs a shell fragment only after validating a matching stock firmware PIT.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import struct
import sys
import tarfile
from pathlib import Path

MAGIC = 0x12349876
HEADER = 28
ENTRY = 132
# Samsung PIT partition block-count units depend on device type.
# Heimdall: MMC (2) = 512 bytes, UFS (8) = 4096 bytes.
# Using MMC units for UFS silently underestimates partition capacity 8x.
DEVICE_BLOCK_BYTES = {2: 512, 8: 4096}
REQUIRED = ("SYSTEM", "VENDOR", "PRODUCT", "ODM", "BOOT")
LIMIT = 64 * 1024 * 1024


class LayoutError(ValueError):
    pass


def read_pit_from_source(path: Path) -> tuple[bytes, str]:
    if path.suffix.lower() == ".pit":
        data = path.read_bytes()
        return data, path.name
    with tarfile.open(path, mode="r:*") as archive:
        entries = [e for e in archive if e.isfile() and e.name.lower().endswith(".pit")]
        if len(entries) != 1:
            raise LayoutError(f"Expected exactly one PIT in {path.name}; got {len(entries)}")
        entry = entries[0]
        if entry.size > LIMIT:
            raise LayoutError("PIT entry exceeds size limit")
        content = archive.extractfile(entry)
        if content is None:
            raise LayoutError("Unable to read PIT entry")
        return content.read(), entry.name


def read_pit_from_sources(sources: list[Path]) -> tuple[bytes, str]:
    """Cross-check CSC and BL PITs if both exist; refuse conflicting layouts."""
    found: list[tuple[bytes, str]] = []
    for path in sources:
        try:
            found.append(read_pit_from_source(path))
        except LayoutError as exc:
            if "Expected exactly one PIT" not in str(exc):
                raise
    if not found:
        raise LayoutError("No PIT found in supplied stock CSC or BL archives")
    digests = {hashlib.sha256(data).digest() for data, _ in found}
    if len(digests) != 1:
        raise LayoutError("Conflicting PIT files between CSC and BL; refusing sizes")
    return found[0]


def parse_pit(data: bytes) -> dict[str, int]:
    if len(data) < HEADER:
        raise LayoutError("Truncated PIT header")
    magic, count = struct.unpack_from("<II", data)
    if magic != MAGIC:
        raise LayoutError("Invalid Samsung PIT magic")
    if not 1 <= count <= 256 or HEADER + count * ENTRY > len(data):
        raise LayoutError("Unreasonable/truncated PIT entry count")
    partitions: dict[str, int] = {}
    for index in range(count):
        offset = HEADER + ENTRY * index
        # BinaryType, DeviceType, Id, Attributes, UpdateAttributes,
        # BlockSizeOrOffset, BlockCount, FileOffset, FileSize.
        values = struct.unpack_from("<9I", data, offset)
        device_type = values[1]
        start, blocks = values[5], values[6]
        rawname = data[offset + 36:offset + 68]
        name = rawname.split(b"\0", 1)[0].decode("ascii", errors="strict").upper()
        if not name or not re.fullmatch(r"[A-Z0-9_]+", name):
            raise LayoutError(f"Invalid PIT partition name at entry {index}")
        if name in partitions:
            raise LayoutError(f"Duplicate PIT partition {name}")
        if blocks == 0 or start + blocks > 2**32:
            raise LayoutError(f"Invalid PIT block range for {name}")
        if device_type not in DEVICE_BLOCK_BYTES:
            if name in REQUIRED or name == "SUPER":
                raise LayoutError(f"Unsupported PIT device type {device_type} for {name}")
            # Ignore non-OS entries with proprietary encoding.
            continue
        partitions[name] = blocks * DEVICE_BLOCK_BYTES[device_type]
    return partitions


def validate_s10_layout(partitions: dict[str, int]) -> dict[str, int]:
    missing = set(REQUIRED).difference(partitions)
    if missing:
        raise LayoutError("Missing S10 legacy partitions: " + ", ".join(sorted(missing)))
    if "SUPER" in partitions:
        raise LayoutError("Unexpected SUPER partition in stock S10 PIT")
    # Sanity bounds only. These are not a substitute for on-device PIT verification.
    if not 256 * 1024**2 <= partitions["SYSTEM"] <= 16 * 1024**3:
        raise LayoutError("Unexpected system partition size")
    if not 128 * 1024**2 <= partitions["VENDOR"] <= 8 * 1024**3:
        raise LayoutError("Unexpected vendor partition size")
    if not 16 * 1024**2 <= partitions["BOOT"] <= 256 * 1024**2:
        raise LayoutError("Unexpected boot partition size")
    for name in ("PRODUCT", "ODM"):
        if not 4 * 1024**2 <= partitions[name] <= 8 * 1024**3:
            raise LayoutError(f"Unexpected {name.lower()} partition size")
    return {name: partitions[name] for name in REQUIRED}


def make_env(layout: dict[str, int], data: bytes, name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", Path(name).name):
        raise LayoutError("Unsafe PIT filename")
    lines = [
        "# Generated from stock Samsung PIT; verify PIT matches actual device.",
        f'S10_SOURCE_PIT_SHA256="{hashlib.sha256(data).hexdigest()}"',
    ]
    for part in REQUIRED:
        lines.append(f"TARGET_{part}_PARTITION_SIZE={layout[part]}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, nargs="+", help="Stock Samsung PIT, CSC or BL tar.md5 archives")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--firmware-id", help="Private target firmware ID; only its SHA256 is stored")
    args = parser.parse_args()
    try:
        data, name = read_pit_from_sources(args.sources)
        layout = validate_s10_layout(parse_pit(data))
        content = make_env(layout, data, name)
        if args.firmware_id:
            content += f'S10_TARGET_FIRMWARE_SHA256="{hashlib.sha256(args.firmware_id.encode()).hexdigest()}"\n'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    except (LayoutError, UnicodeError, OSError, tarfile.TarError, ValueError) as exc:
        print(f"2N1CA E610: PIT extraction/validation failed: {exc}", file=sys.stderr)
        return 2
    print(f"2N1CA: partition sizes derived from {name}; verify against the actual device PIT")
    for partition, capacity in layout.items():
        print(f"  {partition}: {capacity} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
