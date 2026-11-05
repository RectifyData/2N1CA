#!/usr/bin/env python3
"""Inspect extracted S10 vendor HAL/init/VINTF baseline before One UI porting.

This is a source completeness audit, NOT proof of Android 16 HAL compatibility.
"""
from __future__ import annotations
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED_DIRS = ("vendor", "vendor/etc", "vendor/etc/init", "vendor/lib64")
REQUIRED_MOUNTS = ("/system", "/vendor", "/product", "/odm")
CANDIDATE_HAL = {
    "graphics": ("lib64/hw/gralloc.exynos9820.so", "lib64/hw/hwcomposer.exynos9820.so"),
    "radio": ("bin/hw/rild", "lib64/libsec-ril.so", "lib64/libril_sem.so"),
    "audio": ("lib64/hw/audio.primary.exynos9820.so", "lib64/libaudioproxy.so"),
    "bluetooth": ("lib64/hw/audio.bluetooth.default.so", "lib64/vendor.samsung.hardware.bluetooth.audio@2.1.so"),
    "wifi": ("bin/hw/wpa_supplicant", "etc/wifi/wpa_supplicant.conf"),
}


def inspect(root: Path) -> dict:
    vendor = root / "vendor"
    errors: list[str] = []
    warnings: list[str] = []
    for directory in REQUIRED_DIRS:
        if not (root / directory).is_dir():
            errors.append(f"E640 missing required directory: {directory}")
    fstab = vendor / "etc/fstab.exynos9820"
    if not fstab.is_file():
        errors.append("E641 missing vendor/etc/fstab.exynos9820")
    else:
        lines = [line.split() for line in fstab.read_text(errors="replace").splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        mounts = {words[1]: words for words in lines if len(words) >= 3}
        for mount in REQUIRED_MOUNTS:
            if mount not in mounts:
                errors.append(f"E642 missing required legacy fstab mount: {mount}")
            elif mounts[mount][2] != "ext4":
                errors.append(f"E643 unexpected filesystem for {mount}: {mounts[mount][2]}")
        if "/super" in mounts or any("logical" in " ".join(words) for words in lines):
            errors.append("E644 dynamic/logical partitions referenced by S10 fstab")
    vintf = vendor / "etc/vintf/manifest.xml"
    fragments = sorted((vendor / "etc/vintf/manifest").glob("*.xml"))
    if not vintf.is_file() and not fragments:
        errors.append("E645 missing vendor VINTF manifest")
    for doc in ([vintf] if vintf.is_file() else []) + fragments:
        try:
            ET.parse(doc)
        except (ET.ParseError, OSError) as exc:
            errors.append(f"E646 invalid VINTF XML {doc.relative_to(root)}: {exc}")
    for category, options in CANDIDATE_HAL.items():
        found = [opt for opt in options if (vendor / opt).exists()]
        if not found:
            # Do not silently release without basic hardware components.
            # Alternative firmware layouts can be added only with stock evidence.
            errors.append(f"E650 missing {category} HAL baseline; checked: {', '.join(options)}")
    if not (vendor / "etc/selinux").is_dir():
        errors.append("E651 vendor SELinux policy path missing")
    return {"errors": errors, "warnings": warnings, "checked": str(root),
            "hardware_compatibility_verified": False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("firmware_root", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = inspect(args.firmware_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    for issue in report["errors"] + report["warnings"]:
        print("2N1CA", issue, file=sys.stderr)
    if report["errors"]:
        print("2N1CA: vendor baseline incomplete; do not package a ROM.", file=sys.stderr)
        return 2
    print("2N1CA vendor baseline inspected; Android 16 HAL integration remains unverified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
