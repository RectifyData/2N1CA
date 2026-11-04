#!/usr/bin/env python3
"""2N1CA Galaxy S10 framework adaptation audit.

Static mode validates per-device feature contracts; --work-dir additionally
checks post-patch framework archives, properties, and VINTF/SELinux files.
This is NOT a replacement for VTS/checkvintf, hardware tests, or boot testing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

TARGETS = {
    "beyond0lte": {"brand": "Galaxy S10e", "model": "SM-G970F", "fp": "side"},
    "beyond1lte": {"brand": "Galaxy S10", "model": "SM-G973F", "fp": "ultrasonic"},
    "beyond2lte": {"brand": "Galaxy S10+", "model": "SM-G975F", "fp": "ultrasonic"},
    "beyondx": {"brand": "Galaxy S10 5G", "model": "SM-G977B", "fp": "ultrasonic"},
}
OVERLAY_FILES = ("arrays.xml", "bools.xml", "dimens.xml", "integers.xml", "strings.xml")
FRAMEWORK_ARCHIVES = (
    "system/system/framework/framework.jar",
    "system/system/framework/framework-res.apk",
    "system/system/framework/services.jar",
    "system/system/framework/telephony-common.jar",
    "system/system/framework/ssrm.jar",
    "system/system/priv-app/SamsungDeviceHealthManagerService/SamsungDeviceHealthManagerService.apk",
    "system/system/priv-app/SecSettings/SecSettings.apk",
    "system/system/priv-app/SamsungCamera/SamsungCamera.apk",
)
SYSTEM_UI_PATHS = (
    "system/system/system_ext/priv-app/SystemUI/SystemUI.apk",
    "system_ext/priv-app/SystemUI/SystemUI.apk",
    "system/system/priv-app/SystemUI/SystemUI.apk",
)
VINTF = (
    "system/system/etc/vintf/compatibility_matrix.device.xml",
    "system/system/etc/vintf/manifest.xml",
    "vendor/etc/vintf/manifest.xml",
)


def properties(path: Path) -> dict[str, str]:
    result = {}
    if path.is_file():
        for line in path.read_text(errors="replace").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip().strip('"')
    return result


def assignment(content: str, key: str) -> str:
    match = re.search(r"^" + re.escape(key) + r'=["\x27]?([^"\x27\n]+)', content, re.M)
    return (match.group(1).strip() if match else "").strip()


def static_audit(source: Path, device: str) -> list[str]:
    errors: list[str] = []
    profile = TARGETS[device]
    shared = source / "platform/exynos9820/config.sh"
    if not shared.is_file() or assignment(shared.read_text(), "TARGET_VNDK_VERSION") != "31":
        errors.append("E713: Exynos9820 must use stock Android 12 VNDK version 31")
    directory = source / "target" / device
    config = directory / "config.sh"
    feature = directory / "sff.sh"
    if not config.is_file():
        return [f"E700: missing {config}"]
    content = config.read_text(errors="replace")
    if assignment(content, "TARGET_PLATFORM") != "exynos9820":
        errors.append(f"E701: {device} not configured for exynos9820")
    if assignment(content, "TARGET_USE_DYNAMIC_PARTITIONS") != "false":
        errors.append(f"E702: {device} must use legacy partitions")
    if assignment(content, "TARGET_OS_FILE_SYSTEM_TYPE") != "ext4":
        errors.append(f"E703: {device} ext4 target missing")
    if assignment(content, "TARGET_OS_SINGLE_SYSTEM_IMAGE") != "essi":
        errors.append(f"E704: {device} unsupported SSI type")
    if profile["model"] not in content:
        errors.append(f"E705: {device} expected model assertion absent")
    if profile["fp"] not in assignment(content, "TARGET_FINGERPRINT_CONFIG_SENSOR"):
        errors.append(f"E706: {device} incorrect fingerprint type")
    if not feature.is_file():
        errors.append(f"E707: {device} missing floating-feature profile")
    else:
        ff = properties(feature)
        brand = ff.get("SEC_FLOATING_FEATURE_SETTINGS_CONFIG_BRAND_NAME", "")
        if brand != profile["brand"]:
            errors.append(f"E708: {device} wrong brand: {brand!r}")
        policy = assignment(content, "TARGET_DVFSAPP_CONFIG_SSRM_POLICY_FILENAME")
        if policy != ff.get("SEC_FLOATING_FEATURE_SYSTEM_CONFIG_SIOP_POLICY_FILENAME", ""):
            errors.append(f"E709: {device} thermal policy mismatch between framework and floating features")
    for name in OVERLAY_FILES:
        xml = directory / "overlay" / "values" / name
        if not xml.is_file():
            errors.append(f"E710: {device} missing overlay {name}")
            continue
        try:
            root = ET.parse(xml).getroot()
            if root.tag != "resources":
                errors.append(f"E711: {device} malformed overlay root {name}")
        except ET.ParseError as exc:
            errors.append(f"E712: {device} invalid overlay {name}: {exc}")
    return errors


def workdir_audit(work: Path, device: str, stock_target: Path | None = None) -> list[str]:
    errors: list[str] = []
    sysprop = properties(work / "system/system/build.prop")
    vendor = properties(work / "vendor/build.prop")
    if stock_target is not None:
        stock_camera = stock_target / "system/system/cameradata/camera-feature.xml"
        compiled_camera = work / "system/system/cameradata/camera-feature.xml"
        if not stock_camera.is_file() or not compiled_camera.is_file():
            errors.append("E735: matching stock S10 camera feature XML is missing")
        elif hashlib.sha256(stock_camera.read_bytes()).digest() != hashlib.sha256(
            compiled_camera.read_bytes()
        ).digest():
            errors.append("E736: final camera capability data differs from stock S10")
    if sysprop.get("ro.product.device") != device:
        errors.append(f"E720: system framework device mismatch: {sysprop.get('ro.product.device')!r}")
    if sysprop.get("ro.product.system.device", device) != device:
        errors.append("E721: ro.product.system.device mismatches target")
    if vendor.get("ro.product.vendor.device") not in {device, device.removesuffix("lte")}:
        errors.append("E722: vendor/device mismatch; donor vendor must not replace S10 vendor")
    if sysprop.get("ro.build.version.sdk") != "36":
        errors.append("E723: Android 16 framework SDK 36 not found")
    if sysprop.get("ro.build.version.oneui") != "80500":
        errors.append("E731: One UI 8.5 framework version 80500 not found")
    vendor_sdk = vendor.get("ro.build.version.sdk", "")
    if vendor_sdk and vendor_sdk != "31":
        errors.append(f"E732: unexpected stock Exynos9820 vendor SDK {vendor_sdk}")
    vendor_vndk = vendor.get("ro.vndk.version", "")
    if vendor_vndk and vendor_vndk != "31":
        errors.append(f"E733: S10 stock vendor requires VNDK 31, found {vendor_vndk}")
    for relative in FRAMEWORK_ARCHIVES:
        p = work / relative
        if not p.is_file() or not zipfile.is_zipfile(p):
            errors.append(f"E724: missing/invalid framework archive {relative}")
    if not any((work / p).is_file() and zipfile.is_zipfile(work / p)
               for p in SYSTEM_UI_PATHS):
        errors.append("E725: system UI APK is missing or corrupt")
    # Thermal policy names must have matching assets in the actual final
    # SamsungDeviceHealthManagerService APK. Never substitute S22 thermal data.
    target_config = (Path(__file__).resolve().parents[2] / "target" / device / "config.sh")
    if target_config.is_file():
        thermal_name = assignment(
            target_config.read_text(errors="replace"),
            "TARGET_DVFSAPP_CONFIG_SSRM_POLICY_FILENAME"
        )
        health_apk = work / (
            "system/system/priv-app/SamsungDeviceHealthManagerService/"
            "SamsungDeviceHealthManagerService.apk"
        )
        if thermal_name and health_apk.is_file() and zipfile.is_zipfile(health_apk):
            with zipfile.ZipFile(health_apk) as z:
                filenames = [Path(item).name for item in z.namelist()]
            if not any(thermal_name in filename for filename in filenames):
                errors.append(f"E734: S10 thermal policy {thermal_name} is missing "
                              "from Samsung Device Health Manager; not safe to build")
    for relative in VINTF:
        p = work / relative
        try:
            if p.stat().st_size == 0:
                raise ValueError("empty file")
            ET.parse(p)
        except (OSError, ValueError, ET.ParseError) as ex:
            errors.append(f"E726: invalid framework/vendor VINTF {relative}: {ex}")
    mapping = work / "vendor/etc/selinux/plat_sepolicy_vers.txt"
    if not mapping.is_file() or not mapping.read_text().strip():
        errors.append("E727: missing vendor SELinux policy version")
    ff = work / "system/system/etc/floating_feature.xml"
    if not ff.is_file():
        errors.append("E728: missing framework floating_feature.xml")
    else:
        try:
            parsed = ET.parse(ff).getroot()
            expected = TARGETS[device]["brand"]
            values = [node.text for node in parsed.iter()
                      if node.tag == "SEC_FLOATING_FEATURE_SETTINGS_CONFIG_BRAND_NAME"]
            if expected not in values:
                errors.append(f"E729: framework floating feature brand is not {expected}")
        except ET.ParseError as ex:
            errors.append(f"E730: invalid framework floating feature XML: {ex}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--device", choices=TARGETS, required=True)
    parser.add_argument("--work-dir", type=Path, help="post-patch ROM work_dir")
    parser.add_argument("--stock-target", type=Path, help="matching extracted S10 stock firmware")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    errors = static_audit(args.source, args.device)
    if args.work_dir:
        errors.extend(workdir_audit(args.work_dir, args.device, args.stock_target))
    report = {
        "device": args.device, "errors": errors,
        "static_target_and_framework_contract_checked": True,
        "post_patch_framework_files_checked": bool(args.work_dir),
        "vintf_runtime_compatibility_verified": False,
        "bootability_verified": False,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2) + "\n")
    for err in errors:
        print("2N1CA FRAMEWORK ERROR: " + err, file=sys.stderr)
    print(f"2N1CA S10 framework audit: {len(errors)} errors for {args.device}")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
