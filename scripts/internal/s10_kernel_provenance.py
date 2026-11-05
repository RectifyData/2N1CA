#!/usr/bin/env python3
"""Record a build's actual boot bytes and source provenance, NOT flash approval."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

DEVICES = {"beyond0lte", "beyond1lte", "beyond2lte", "beyondx"}


def record(boot: Path, target: str, commit: str, run_id: int, makefile: Path) -> dict:
    if target not in DEVICES:
        raise ValueError("Unrecognized S10 model")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or run_id < 1:
        raise ValueError("Missing pinned full kernel commit or GitHub Actions run")
    if not boot.is_file() or boot.stat().st_size < 4096:
        raise ValueError("No valid boot image artifact")
    with boot.open("rb") as f:
        header = f.read(48)
    if len(header) < 44 or header[:8] != b"ANDROID!":
        raise ValueError("Boot artifact lacks Android boot header")
    size = struct.unpack_from("<I", header, 8)[0]
    version = struct.unpack_from("<I", header, 40)[0]
    if size < 1 or size >= boot.stat().st_size or version > 4:
        raise ValueError("Boot kernel size/header version invalid")
    if not makefile.is_file():
        raise ValueError("Pinned kernel Makefile missing")
    raw = makefile.read_text(errors="replace")
    versions = {}
    for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"):
        match = re.search(r"^" + key + r"\s*=\s*([0-9]+)\s*$", raw, re.M)
        if not match:
            raise ValueError(f"Kernel source Makefile missing {key}")
        versions[key] = match.group(1)
    digest = hashlib.sha256()
    with boot.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "target": target, "boot_sha256": digest.hexdigest(),
        "kernel_commit": commit,
        "workflow_run_id": run_id,
        "kernel_source_version": ".".join(versions[k] for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL")),
        "boot_header_version": version,
        "boot_file_size": boot.stat().st_size,
        "compilation_verified": True,
        "hardware_boot_verified": False,
        "device_verified": False,
        "is_flash_safe": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boot", required=True, type=Path)
    p.add_argument("--target", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--makefile", type=Path, required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    try:
        value = record(args.boot, args.target, args.commit, args.run_id, args.makefile)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2) + "\n")
    except (OSError, ValueError) as exc:
        print(f"E634: Kernel build provenance missing: {exc}", file=sys.stderr)
        return 2
    print("2N1CA: boot artifact recorded; device/kernel runtime NOT verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
