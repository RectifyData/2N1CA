#!/usr/bin/env bash
# Download and extract Samsung donor + target firmware for one S10 device.
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/lib/s10_pipeline.sh
source "$ROOT/scripts/lib/s10_pipeline.sh"
[[ "$#" -ge 1 && "$#" -le 2 ]] || s10_die "Usage: ./download.sh beyond2lte [--force]"
DEVICE="$1"
MODE="${2:-}"
[[ -z "$MODE" || "$MODE" == "--force" ]] || s10_die "Unknown argument: $MODE"
s10_require_target "$DEVICE"
s10_env "$DEVICE"
bash "$ROOT/scripts/build_dependencies.sh" --check-tools ||
  s10_die "Host tools absent; run ./prepare.sh $DEVICE first"
options=()
[[ "$MODE" == "--force" ]] && options=(--force)
s10_info "Downloading Samsung source and stock target firmware for $DEVICE"
"$ROOT/scripts/download_fw.sh" "${options[@]}" ||
  s10_die "Firmware download failed; check model/CSC, connection and credentials"
# Derive legacy partition capacities from the actual stock target CSC PIT.
# Do not use guessed partition sizes from a different model or firmware.
model="${TARGET_FIRMWARE%%/*}"
rest="${TARGET_FIRMWARE#*/}"
region="${rest%%/*}"
stock_dir="$ODIN_DIR/${model}_${region}"
layout="$OUT_DIR/target/$DEVICE/pit-layout.env"
firmware_hash="$(printf '%s' "$TARGET_FIRMWARE" | sha256sum | cut -d ' ' -f 1)"
shopt -s nullglob
csc_tars=("$stock_dir"/CSC_*.tar.md5 "$stock_dir"/CSC_*.tar "$stock_dir"/HOME_CSC_*.tar.md5)
shopt -u nullglob
if [ "${#csc_tars[@]}" -gt 0 ]; then
  s10_info "Extracting partition sizes from Samsung CSC PIT (no repartitioning)"
  python3 "$ROOT/scripts/internal/s10_pit_layout.py" "${csc_tars[0]}" \
    --firmware-id "$TARGET_FIRMWARE" --output "$layout" ||
    s10_die "Stock PIT is missing/invalid; cannot safely derive partition capacities"
elif [ -s "$layout" ] && grep -qx "S10_TARGET_FIRMWARE_SHA256=\"$firmware_hash\"" "$layout"; then
  s10_info "Using previously verified PIT capacity manifest for unchanged firmware"
else
  s10_die "No matching CSC PIT/verified cached layout for $DEVICE; unsafe to build images"
fi
s10_info "Extracting downloaded firmware for $DEVICE"
"$ROOT/scripts/extract_fw.sh" "${options[@]}" ||
  s10_die "Firmware extraction failed; check storage, tar integrity and mount permissions"
s10_info "Firmware prepared for $DEVICE"
