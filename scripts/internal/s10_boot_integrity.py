#!/usr/bin/env python3
"""Validate a specific Exynos9820 boot artifact against independent build evidence.

A matching SHA256 is necessary but NOT a bootability or firmware compatibility
certificate. Human device testing, TEE/VINTF, SELinux and recovery remain
independent requirements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

MODELS = {"beyond0lte", "beyond1lte", "beyond2lte", "beyondx"}
SHA = re.compile(r"[a-f0-9]{64}\Z")
COMMIT = re.compile(r"[a-f0-9]{40}\Z")


class BootError(ValueError):
    pass


def load_evidence(manifest: Path, target: str, test_report: Path) -> dict:
    if target not in MODELS:
        raise BootError(f"Unsupported S10 variant {target!r}")
    if not manifest.is_file() or not test_report.is_file():
        raise BootError("E620: Boot evidence manifest or device test report is missing")
    try:
        entry = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootError(f"E620: Malformed boot evidence manifest: {exc}") from exc
    fields = ("target", "boot_sha256", "kernel_commit",
              "workflow_run_id", "kernel_version", "test_report_sha256")
    if not isinstance(entry, dict) or any(key not in entry for key in fields):
        raise BootError("E621: Missing boot SHA256, provenance or test report evidence")
    if entry["target"] != target:
        raise BootError("E622: Boot evidence targets another Galaxy S10 model")
    if not isinstance(entry["boot_sha256"], str) or not SHA.fullmatch(entry["boot_sha256"]):
        raise BootError("E623: Invalid approved boot SHA256")
    if not isinstance(entry["kernel_commit"], str) or not COMMIT.fullmatch(entry["kernel_commit"]):
        raise BootError("E624: Kernel source commit must be a full 40-character SHA")
    if not isinstance(entry["workflow_run_id"], int) or entry["workflow_run_id"] <= 0:
        raise BootError("E625: A positive GitHub workflow run ID is required")
    if not isinstance(entry["kernel_version"], str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+._a-zA-Z0-9]*)?", entry["kernel_version"]
    ):
        raise BootError("E626: Invalid recorded Linux kernel release")
    if not isinstance(entry["test_report_sha256"], str) or not SHA.fullmatch(entry["test_report_sha256"]):
        raise BootError("E627: Device test report SHA256 absent")
    report_hash = hashlib.sha256(test_report.read_bytes()).hexdigest()
    if report_hash != entry["test_report_sha256"]:
        raise BootError("E628: Device test report changed since boot approval")
    try:
        report = json.loads(test_report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BootError(f"E629: Device test report is not JSON: {exc}") from exc
    if not isinstance(report, dict) or report.get("device") != target or report.get("boot_completed") is not True:
        raise BootError("E630: Device test report does not document boot completion")
    if report.get("hardware_verified") is not True:
        raise BootError("E631: Device hardware verification is not complete")
    # Report and SHA fields are supplied by the owner, not evidence that
    # hardware testing happened. They cannot be trusted automatically.
    return entry


def verify_boot(boot: Path, manifest: Path, target: str, test_report: Path) -> dict:
    entry = load_evidence(manifest, target, test_report)
    if not boot.is_file() or boot.stat().st_size < 4096:
        raise BootError("E632: Missing or truncated boot.img")
    with boot.open("rb") as stream:
        header = stream.read(48)
        if header[:8] != b"ANDROID!":
            raise BootError("E633: boot.img has no Android boot magic")
        kernel_size = struct.unpack_from("<I", header, 8)[0]
        header_version = struct.unpack_from("<I", header, 40)[0]
        if not kernel_size or kernel_size >= boot.stat().st_size:
            raise BootError("E634: Boot header kernel size is invalid")
        if header_version > 4:
            raise BootError("E635: Unrecognized Android boot header")
    h = hashlib.sha256()
    with boot.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != entry["boot_sha256"]:
        raise BootError("E636: Boot image SHA256 does not match reviewed kernel artifact")
    return {"device": target, "boot_sha256": h.hexdigest(),
            "kernel_version": entry["kernel_version"], "boot_header_version": header_version,
            "hash_matched": True, "on_device_boot_verified_by_this_tool": False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True, choices=sorted(MODELS))
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--test-report", type=Path, required=True)
    p.add_argument("--boot", type=Path)
    args = p.parse_args()
    try:
        if args.boot:
            result = verify_boot(args.boot, args.manifest, args.target, args.test_report)
            print(json.dumps(result, sort_keys=True))
        else:
            load_evidence(args.manifest, args.target, args.test_report)
            print("2N1CA: boot evidence present; image hash NOT YET CHECKED")
    except (OSError, BootError) as exc:
        print(f"2N1CA boot gate: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
