#!/usr/bin/env bash
# Build and validate a full recovery ZIP for one Galaxy S10 variant.
# Fail closed; does NOT install or flash anything.
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/lib/s10_pipeline.sh
source "$ROOT/scripts/lib/s10_pipeline.sh"
[[ "$#" -eq 1 ]] || s10_die "Usage: ./build.sh beyond2lte"
DEVICE="$1"
s10_require_target "$DEVICE"
# STOP before packaging if the required Android 16-compatible kernel port is absent.
# A working stock Android 12 kernel cannot be assumed compatible with One UI 8.
[[ -s "$ROOT/platform/exynos9820/kernel/boot-image-validated.sha256" ]] ||
  s10_die "E620: No verified Exynos 9820 One UI 8 boot image. Flashable build blocked."
s10_info "Step 1/4: prepare"
bash "$ROOT/prepare.sh" "$DEVICE" || s10_die "Preparation failed"
s10_info "Step 2/4: download and extract firmware"
bash "$ROOT/download.sh" "$DEVICE" || s10_die "Firmware acquisition failed"
s10_env "$DEVICE"
s10_require_pit_layout "$DEVICE"
s10_info "Step 3/4: rebuild ROM and flashable ZIP"
# Force work directory regeneration so updated donor firmware cannot reuse stale files.
"$ROOT/scripts/make_rom.sh" --force --build-rom-zip ||
  s10_die "ROM packaging failed; no release candidate should be published"
s10_info "Step 4/4: validate the built flashable ZIP"
bash "$ROOT/verify.sh" "$DEVICE" ||
  s10_die "ZIP verification failed; do not flash or release"
s10_info "Build ZIP checks passed, but bootability and on-device installation remain UNVERIFIED"
