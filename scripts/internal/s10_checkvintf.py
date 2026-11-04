#!/usr/bin/env python3
"""Run Android's checkvintf against the *combined* One UI + Exynos9820 tree.

Source: AOSP build/tools/releasetools/check_target_files_vintf.py.
This does not check a real kernel, runtime SELinux, or hardware operation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PARTITIONS = {
    "/system": ("system/system",),
    "/vendor": ("vendor",),
    "/product": ("product", "system/system/product"),
    "/odm": ("odm", "vendor/odm"),
    "/system_ext": ("system_ext", "system/system/system_ext", "system/system_ext"),
}

def assemble(work: Path, binary: str = "checkvintf") -> list[str]:
    if not work.is_dir():
        raise ValueError(f"Missing ROM work directory: {work}")
    command = [binary, "--check-compat"]
    for partition, alternatives in PARTITIONS.items():
        matches = [work / p for p in alternatives if (work / p).is_dir()]
        if partition in ("/system", "/vendor") and len(matches) != 1:
            raise ValueError(f"Require exactly one {partition} directory, found {len(matches)}")
        if len(matches) > 1:
            raise ValueError(f"Ambiguous {partition} layout: {matches}")
        if matches:
            command.extend(["--dirmap", f"{partition}:{matches[0].resolve()}"])
    # S10 launched with Android 9; stock Android 12 vendor image uses VNDK 31.
    command.extend(["--property", "ro.product.first_api_level=28"])
    return command

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", type=Path, required=True)
    p.add_argument("--tool", default="checkvintf")
    p.add_argument("--require-tool", action="store_true")
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    report = {"tool": args.tool, "checked": False, "compatible": None,
              "device_boot_verified": False, "notes": "No hardware/kernel tests"}
    code = 2
    try:
        command = assemble(args.work_dir, args.tool)
        binary = shutil.which(args.tool)
        if not binary:
            report["error"] = f"checkvintf missing: {args.tool}"
            if args.require_tool:
                print("E760: " + report["error"], file=sys.stderr)
            else:
                print("2N1CA: checkvintf unavailable; runtime VINTF unverified")
                code = 0  # Only for non-flashable development builds.
        else:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=120, check=False)
            report["checked"] = True
            report["compatible"] = process.returncode == 0
            report["stdout"] = process.stdout[-12000:]
            report["stderr"] = process.stderr[-12000:]
            code = 0 if process.returncode == 0 else 2
            if code:
                print("E761: Android 16/S10 VINTF incompatibility:\n" +
                      process.stderr[-4000:], file=sys.stderr)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report["error"] = str(exc)
        print(f"E762: Cannot validate VINTF: {exc}", file=sys.stderr)
    finally:
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
    return code

if __name__ == "__main__":
    raise SystemExit(main())
