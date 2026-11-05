#!/usr/bin/env python3
"""Capture *actual* stock S10 vendor ABI properties (not guessed Android levels).

This does not prove Android 16/VINTF compatibility or the active device PIT.
Source path is an extracted authorized S10 stock firmware directory.
"""
from __future__ import annotations
import argparse
import hashlib
import re
import sys
from pathlib import Path


class ABIError(ValueError):
    pass


def read_prop(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, val = line.split("=", 1)
            result[key.strip()] = val.strip()
    return result


def required_level(name: str, sources: list[dict[str, str]], lo: int, hi: int) -> int:
    values = [data[name] for data in sources if data.get(name)]
    if not values:
        raise ABIError(f"{name} missing from extracted stock properties")
    if any(not re.fullmatch(r"[0-9]{1,4}", value) for value in values):
        raise ABIError(f"{name} is not a valid integer")
    versions = {int(value) for value in values}
    if len(versions) != 1:
        raise ABIError(f"Conflicting {name} values in stock properties: {sorted(versions)}")
    value = versions.pop()
    if not lo <= value <= hi:
        raise ABIError(f"Unexpected {name}={value}; expected [{lo}, {hi}]")
    return value


def collect(root: Path, firmware_hash: str) -> dict[str, str]:
    if not re.fullmatch(r"[a-f0-9]{64}", firmware_hash):
        raise ABIError("Firmware ID hash must be an exact SHA256")
    vendor_file = root / "vendor/build.prop"
    if not vendor_file.is_file():
        raise ABIError("Missing S10 vendor/build.prop")
    vendor = read_prop(vendor_file)
    default = read_prop(root / "vendor/default.prop")
    system = read_prop(root / "system/system/build.prop")
    target = vendor.get("ro.product.vendor.device", "")
    if not target.startswith(("beyond0", "beyond1", "beyond2", "beyondx")):
        raise ABIError(f"Unexpected stock S10 vendor device: {target!r}")
    vendor_sdk = required_level("ro.build.version.sdk", [vendor, default], 28, 36)
    vndk = required_level("ro.vndk.version", [vendor, default], 28, 36)
    first = required_level("ro.product.first_api_level", [vendor, default, system], 28, 36)
    board = required_level("ro.board.api_level", [vendor, default], 28, 36)
    return {
        "S10_VENDOR_PLATFORM_SDK": str(vendor_sdk),
        "S10_VENDOR_VNDK": str(vndk),
        "S10_VENDOR_FIRST_API": str(first),
        "S10_VENDOR_BOARD_API": str(board),
        "S10_VENDOR_BUILD_PROP_SHA256": hashlib.sha256(vendor_file.read_bytes()).hexdigest(),
        "S10_VENDOR_FIRMWARE_SHA256": firmware_hash,
    }


def write_manifest(fields: dict[str, str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    output = "# Verified from extracted stock vendor properties; NOT proof of bootability\n"
    output += "".join(f'{key}="{val}"\n' for key, val in fields.items())
    temp = dest.with_suffix(".tmp")
    temp.write_text(output)
    temp.chmod(0o600)
    temp.replace(dest)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("firmware_root", type=Path)
    p.add_argument("--firmware-hash", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    try:
        fields = collect(args.firmware_root, args.firmware_hash)
        write_manifest(fields, args.output)
    except (OSError, ABIError) as exc:
        print(f"2N1CA E746: Stock vendor ABI not verified: {exc}", file=sys.stderr)
        return 2
    print("2N1CA: stock vendor API/VNDK values recorded; VINTF/hardware untested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
