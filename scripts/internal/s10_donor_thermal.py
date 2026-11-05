#!/usr/bin/env python3
"""Extract S25 FE thermal policy identity from real donor APK and floating_feature.xml.

Never substitute Galaxy S22/exynos2200 SSRM/thermal files for the S25 FE.
Does not establish runtime thermals or validate the device-specific target policy.
"""
from __future__ import annotations
import argparse
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


class ThermalError(ValueError):
    pass


POLICY = "SEC_FLOATING_FEATURE_SYSTEM_CONFIG_SIOP_POLICY_FILENAME"


def inspect(fw: Path, preferred_dvfs: str = "") -> dict[str, str]:
    feature = fw / "system/system/etc/floating_feature.xml"
    app = fw / ("system/system/priv-app/SamsungDeviceHealthManagerService/"
                "SamsungDeviceHealthManagerService.apk")
    if not feature.is_file() or not app.is_file() or not zipfile.is_zipfile(app):
        raise ThermalError("Matching S25 FE floating features or Device Health Manager APK missing")
    try:
        root = ET.parse(feature).getroot()
    except ET.ParseError as exc:
        raise ThermalError(f"Malformed donor floating features: {exc}") from exc
    values = [e.text.strip() for e in root.iter(POLICY) if e.text and e.text.strip()]
    if len(set(values)) != 1:
        raise ThermalError(f"Expected one donor SIOP policy, got {values!r}")
    ssrm = values[0]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", ssrm) or "exynos2200" in ssrm:
        raise ThermalError(f"Unverified or foreign S25 FE SSRM policy {ssrm!r}")
    with zipfile.ZipFile(app) as archive:
        assets = {Path(entry.filename).name for entry in archive.infolist()
                  if not entry.is_dir()}
    if not any(name.startswith(ssrm + ".") for name in assets):
        raise ThermalError(f"Donor Device Health Manager lacks SSRM policy {ssrm!r}")
    candidates = sorted({name[:-4] for name in assets
                         if name.startswith("dvfs_policy") and name.endswith(".xml")})
    if preferred_dvfs:
        if preferred_dvfs not in candidates:
            raise ThermalError(f"Requested DVFS {preferred_dvfs!r} not found in donor APK")
        dvfs = preferred_dvfs
    elif len(candidates) == 1:
        dvfs = candidates[0]
    else:
        raise ThermalError(f"Ambiguous/missing donor DVFS policies {candidates!r}; "
                           "set S10_DONOR_DVFS_POLICY to a confirmed value")
    return {
        "S10_DONOR_SSRM_POLICY": ssrm,
        "S10_DONOR_DVFS_POLICY": dvfs,
        "S10_DONOR_FLOATING_FEATURE_SHA256": hashlib.sha256(feature.read_bytes()).hexdigest(),
        "S10_DONOR_HEALTH_APK_SHA256": hashlib.sha256(app.read_bytes()).hexdigest(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("donor_root", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--dvfs-policy", default="")
    args = p.parse_args()
    try:
        data = inspect(args.donor_root, args.dvfs_policy)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Derived from extracted S25 FE firmware; not runtime validation"]
        lines.extend(f'{key}="{val}"' for key, val in data.items())
        temp = args.output.with_suffix(".tmp")
        temp.write_text("\n".join(lines) + "\n")
        temp.chmod(0o600)
        temp.replace(args.output)
    except (OSError, ThermalError, zipfile.BadZipFile) as exc:
        print(f"2N1CA E754: Donor thermal assets unverified: {exc}", file=sys.stderr)
        return 2
    print("2N1CA: donor thermal assets identified from firmware; runtime unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
