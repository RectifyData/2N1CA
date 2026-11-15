#!/usr/bin/env python3
"""Validate Exynos9820 vendor/ODM init service binaries after ROM patching.

Checks declared vendor and ODM service executable paths, not their ABI or
runtime behavior. Builds must still undergo real HAL, SELinux and boot tests.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SERVICE = re.compile(r"^\s*service\s+(\S+)\s+(/(?:vendor|odm)/\S+)")
IMPORT = re.compile(r"^\s*import\s+(/(?:vendor|odm)/\S+)")
ALLOWED = ("/vendor/", "/odm/")


def inspect(root: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    declared: dict[str, str] = {}
    inspected = 0
    for partition in ("vendor", "odm"):
        init_dir = root / partition / "etc/init"
        if not init_dir.is_dir():
            if partition == "vendor":
                errors.append("E780: Vendor init directory missing")
            continue
        for rc in sorted(init_dir.rglob("*.rc")):
            inspected += 1
            try:
                lines = rc.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as exc:
                errors.append(f"E781: Cannot read {rc}: {exc}")
                continue
            for line_number, line in enumerate(lines, 1):
                match = SERVICE.match(line)
                if match:
                    service, binary = match.groups()
                    if "$" in binary or "%" in binary:
                        warnings.append(f"W785: Dynamic service path {service} in {rc.name}")
                        continue
                    path = root / binary.lstrip("/")
                    if not path.is_file():
                        errors.append(f"E782: {rc.relative_to(root)}:{line_number} service "
                                      f"{service} missing executable {binary}")
                    if service in declared and declared[service] != binary:
                        warnings.append(f"W786: {service} declared with different binaries")
                    declared[service] = binary
                imported = IMPORT.match(line)
                if imported:
                    candidate = imported.group(1)
                    if "$" in candidate or "%" in candidate:
                        continue
                    if not (root / candidate.lstrip("/")).is_file():
                        warnings.append(f"W787: Unresolved init import {candidate} in {rc.name}")
    return {
        "errors": errors, "warnings": warnings,
        "rc_files_checked": inspected, "services_checked": len(declared),
        "hardware_verified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("work_dir", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    report = inspect(args.work_dir)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    for problem in report["errors"] + report["warnings"]:
        print("2N1CA " + problem, file=sys.stderr)
    if report["errors"]:
        print("2N1CA: vendor init/HAL service entries unresolved", file=sys.stderr)
        return 2
    print(f"2N1CA: init audit checked {report['services_checked']} service binaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
