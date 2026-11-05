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


def validate(props: dict[str, str], vendor_props: dict[str, str] | None = None) -> None:
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
    # A system-only build.prop is insufficient proof of the SoC: Samsung
    # normally publishes the board platform on the vendor partition.
    if vendor_props is None:
        raise DonorError("Missing donor vendor/build.prop: board identity is unverified")
    model = props.get("ro.product.model", "") or vendor_props.get("ro.product.vendor.model", "")
    if not model or not (
        "S25 FE" in model.upper() or model.upper().startswith("SM-S731B")
    ):
        raise DonorError(f"Donor model does not prove Galaxy S25 FE: {model!r}")
    vendor_board = vendor_props.get("ro.board.platform", "").strip()
    if not vendor_board:
        raise DonorError("Donor vendor/build.prop is missing ro.board.platform")
    # This is an expected source hardware contract, not proof of bootability.
    # It is accepted only when the value is read from actual extracted firmware.
    if vendor_board.lower() != "s5e9945":
        raise DonorError(f"Unexpected donor vendor board {vendor_board!r}; expected s5e9945")
    system_board = props.get("ro.board.platform", "").strip()
    if system_board and system_board.lower() != vendor_board.lower():
        raise DonorError(f"Donor system board {system_board!r} conflicts with vendor {vendor_board!r}")


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
    parser.add_argument("--vendor-build-prop", type=Path,
                        help="matching extracted S25 FE vendor/build.prop; mandatory for donor verification")
    parser.add_argument("--pinned-version", help="Validate an explicit Samsung FUS Android 16 donor build")
    args = parser.parse_args()
    try:
        if args.pinned_version:
            validate_pinned_version(args.pinned_version)
        if args.build_prop:
            if args.vendor_build_prop is None:
                raise DonorError("--vendor-build-prop required with build.prop")
            props = read_properties(args.build_prop)
            vendor_props = read_properties(args.vendor_build_prop)
            validate(props, vendor_props)
        elif not args.pinned_version:
            raise DonorError("Supply a build.prop file or --pinned-version")
    except (DonorError, OSError) as exc:
        print(f"2N1CA E630: One UI donor rejected: {exc}", file=sys.stderr)
        return 2
    if args.build_prop:
        print("2N1CA extracted donor properties verified (hardware/boot untested)")
    else:
        print("2N1CA donor version string syntax verified; firmware NOT yet checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
