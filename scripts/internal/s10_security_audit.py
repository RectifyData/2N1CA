#!/usr/bin/env python3
"""Check Keymaster/Gatekeeper and secure-element HAL preservation from stock S10.

This is a static manifest contract check, not a TEE runtime or key attestation
test. No real hardware was exercised.
"""
from __future__ import annotations
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SECURITY_HALS = (
    "android.hardware.keymaster",
    "android.hardware.security.keymint",
    "android.hardware.gatekeeper",
    "android.hardware.security.secureclock",
    "android.hardware.secure_element",
)


def security_hals(root: Path) -> dict[str, set[str]]:
    found = {}
    for partition in ("vendor", "odm"):
        base = root / partition / "etc/vintf"
        paths = sorted(base.glob("manifest*.xml"))
        paths.extend(sorted((base / "manifest").glob("*.xml")))
        for path in paths:
            try:
                node = ET.parse(path).getroot()
            except (OSError, ET.ParseError) as exc:
                raise ValueError(f"E780: Cannot parse {path}: {exc}") from exc
            for hal in node.findall(".//hal"):
                name = (hal.findtext("name") or "").strip()
                if name not in SECURITY_HALS:
                    continue
                fmt = hal.get("format", "hidl")
                versions = [v.text.strip() for v in hal.findall("version") if v.text]
                fqnames = [v.text.strip() for v in hal.findall("fqname") if v.text]
                for iface in hal.findall("interface"):
                    n = (iface.findtext("name") or "").strip()
                    fqnames.extend(n + "/" + (v.text or "").strip()
                                   for v in iface.findall("instance") if n and v.text)
                entries = {f"{fmt}:{v}" for v in versions} | {f"{fmt}:{v}" for v in fqnames}
                if not entries:
                    raise ValueError(f"E781: Security HAL {name} has no versions or instances")
                found.setdefault(name, set()).update(entries)
    return found


def inspect(stock: Path, result: Path) -> dict:
    errors = []
    try:
        original = security_hals(stock)
        current = security_hals(result)
    except ValueError as exc:
        return {"errors": [str(exc)], "runtime_tee_verified": False,
                "original_hals": {}, "final_hals": {}}
    if not any(n in original for n in ("android.hardware.keymaster",
                                         "android.hardware.security.keymint")):
        errors.append("E782: Stock S10 has no identifiable Keymaster/KeyMint HAL")
    if "android.hardware.gatekeeper" not in original:
        errors.append("E783: Stock S10 Gatekeeper HAL missing")
    for name, declared in original.items():
        if name not in current:
            errors.append(f"E784: Final ROM lost stock security HAL {name}")
        elif declared != current[name]:
            errors.append(f"E785: Final ROM changed {name} without a reviewed bridge: "
                          f"{sorted(declared)} -> {sorted(current[name])}")
    for name in ("android.hardware.keymaster", "android.hardware.security.keymint",
                 "android.hardware.gatekeeper"):
        if name in current and name not in original:
            errors.append(f"E786: New security HAL {name} lacks stock S10 evidence")
    return {
        "errors": errors,
        "original_hals": {k: sorted(v) for k, v in original.items()},
        "final_hals": {k: sorted(v) for k, v in current.items()},
        "runtime_tee_verified": False,
        "runtime_keymaster_verified": False,
        "runtime_secure_element_verified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stock", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    report = inspect(args.stock, args.work)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    for error in report["errors"]:
        print("2N1CA " + error, file=sys.stderr)
    if report["errors"]:
        return 2
    print("2N1CA: Stock security HAL registrations preserved; TEE runtime NOT tested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
