#!/usr/bin/env python3
"""Reject a donor that isn't Android 16 / One UI 8.5."""
import argparse
import sys
from pathlib import Path


class DonorError(ValueError):
    pass


def read_properties(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise DonorError(f"Missing extracted build.prop at {path}")
    lines = path.read_text(errors="replace").splitlines()
    return dict(line.split("=", 1) for line in lines
                if "=" in line and not line.lstrip().startswith("#"))


def validate(props: dict[str, str]) -> None:
    sdk = props.get("ro.build.version.sdk", "")
    if sdk != "36":
        raise DonorError(f"Expected Android 16 SDK 36, got {sdk!r}")
    raw = props.get("ro.build.version.oneui", "")
    if not raw.isdigit():
        raise DonorError(f"Missing/non-numeric One UI version: {raw!r}")
    version = int(raw)
    major, minor = divmod(version, 10000)
    minor //= 100
    if (major, minor) != (8, 5):
        raise DonorError(f"Expected One UI 8.5 (80500), got {raw!r}; do not sync to 9.0")
    model = props.get("ro.product.model", "")
    if model and "S25" not in model and "SM-S731" not in model:
        # Donor firmware model verification happens separately via directory name.
        # Do not hard reject Samsung product labels that omit the marketed name.
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_prop", type=Path)
    args = parser.parse_args()
    try:
        props = read_properties(args.build_prop)
        validate(props)
    except (DonorError, OSError) as exc:
        print(f"2N1CA E630: One UI donor rejected: {exc}", file=sys.stderr)
        return 2
    print("2N1CA donor verified: Android 16, One UI 8.5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
