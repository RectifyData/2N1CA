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
    if report.get("synthetic_fixture") is True:
        raise BootError("E637: Synthetic device report is not acceptable boot approval")
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


def verify_experimental_boot(boot: Path, provenance: Path, target: str) -> dict:
    """Check compiled test boot bytes, not physical boot or flash safety."""
    if target not in MODELS:
        raise BootError(f"E640: Unknown S10 variant {target!r}")
    if not provenance.is_file():
        raise BootError("E641: Missing experimental kernel compilation provenance")
    try:
        entry = json.loads(provenance.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootError(f"E642: Invalid experimental kernel provenance: {exc}") from exc
    if not isinstance(entry, dict) or entry.get("target") != target:
        raise BootError("E643: Compiler artifact targets another S10 model")
    digest, commit = entry.get("boot_sha256"), entry.get("kernel_commit")
    run_id, version = entry.get("workflow_run_id"), entry.get("kernel_source_version")
    if not isinstance(digest, str) or not SHA.fullmatch(digest):
        raise BootError("E644: Missing SHA256 of compiled boot image")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise BootError("E645: Missing full kernel source commit")
    if type(run_id) is not int or run_id <= 0:
        raise BootError("E646: Missing compiler workflow run ID")
    if not isinstance(version, str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+._a-zA-Z0-9]*)?", version
    ):
        raise BootError("E647: Invalid kernel source release")
    if (entry.get("compilation_verified") is not True or
        entry.get("hardware_boot_verified") is not False or
        entry.get("device_verified") is not False or
        entry.get("is_flash_safe") is not False):
        raise BootError("E648: Artifact is not explicitly marked compiled but untested")
    if not boot.is_file() or boot.is_symlink() or boot.stat().st_size < 4096:
        raise BootError("E649: Missing or truncated compiled boot image")
    with boot.open("rb") as stream:
        header = stream.read(48)
    if len(header) < 44 or header[:8] != b"ANDROID!":
        raise BootError("E650: Compiled boot image lacks Android magic")
    size = struct.unpack_from("<I", header, 8)[0]
    header_version = struct.unpack_from("<I", header, 40)[0]
    if size < 1 or size >= boot.stat().st_size or header_version > 4:
        raise BootError("E651: Compiled boot image header is invalid")
    if (type(entry.get("boot_header_version")) is not int or
        entry["boot_header_version"] != header_version or
        type(entry.get("boot_file_size")) is not int or
        entry["boot_file_size"] != boot.stat().st_size):
        raise BootError("E652: Compiler output size/header changed")
    actual = hashlib.sha256()
    with boot.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            actual.update(chunk)
    if actual.hexdigest() != digest:
        raise BootError("E653: Boot image differs from its compiled kernel artifact")
    return {"target": target, "boot_sha256": digest, "kernel_commit": commit,
            "kernel_source_version": version, "compilation_verified": True,
            "hardware_boot_verified": False, "is_flash_safe": False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target", required=True, choices=sorted(MODELS))
    p.add_argument("--manifest", type=Path)
    p.add_argument("--test-report", type=Path)
    p.add_argument("--experimental-provenance", type=Path,
                   help="Compile-only kernel provenance for unverified tester ROMs")
    p.add_argument("--boot", type=Path)
    args = p.parse_args()
    try:
        if args.experimental_provenance is not None:
            if args.boot is None or args.manifest is not None or args.test_report is not None:
                raise BootError("E654: Tester mode requires --boot and experimental provenance only")
            result = verify_experimental_boot(
                args.boot, args.experimental_provenance, args.target
            )
            print(json.dumps(result, sort_keys=True))
        else:
            if args.manifest is None or args.test_report is None:
                raise BootError("E620: Approved build needs boot manifest and device report")
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
