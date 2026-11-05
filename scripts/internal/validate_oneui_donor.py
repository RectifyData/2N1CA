#!/usr/bin/env python3
"""Reject a donor that isn't Android 16 / One UI 8.5."""
import argparse
import re
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
    if model and not (
        "S25 FE" in model.upper() or model.upper().startswith("SM-S731")
    ):
        raise DonorError(f"Donor model does not identify Galaxy S25 FE: {model!r}")
    board = props.get("ro.board.platform", "") or props.get("ro.hardware", "")
    if board and board.lower() != "s5e9945":
        raise DonorError(f"Wrong donor SoC board {board!r}; expected S25 FE s5e9945")


def validate_pinned_version(version: str) -> None:
    """Require an S25 FE B-series Android 16 build, never a C-series One UI 9 build.

    Samsung's S25 FE Android 16 / One UI 8.5 releases use B-series PDAs
    (e.g. S731BXXU6BZDP); this is only a pre-download check. The extracted
    ro.build.version.sdk and ro.build.version.oneui remain authoritative.
    """
    parts = version.split("/")
    if len(parts) not in (3, 4) or any(
        not re.fullmatch(r"[A-Z0-9]{8,24}", p) for p in parts
    ):
        raise DonorError("Pinned FUS build must have 3 or 4 slash-separated component versions")
    pda = parts[0]
    if not re.fullmatch(r"S731B[A-Z0-9]+B[A-Z0-9]{3}", pda):
        raise DonorError(f"Pinned donor PDA {pda!r} is not S25 FE B-series Android 16")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_prop", type=Path, nargs="?")
    parser.add_argument("--pinned-version", help="Validate an explicit Samsung FUS Android 16 donor build")
    args = parser.parse_args()
    try:
        if args.pinned_version:
            validate_pinned_version(args.pinned_version)
        if args.build_prop:
            props = read_properties(args.build_prop)
            validate(props)
        elif not args.pinned_version:
            raise DonorError("Supply a build.prop file or --pinned-version")
    except (DonorError, OSError) as exc:
        print(f"2N1CA E630: One UI donor rejected: {exc}", file=sys.stderr)
        return 2
    print("2N1CA donor verified: Android 16, One UI 8.5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
