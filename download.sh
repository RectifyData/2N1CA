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
s10_info "Extracting downloaded firmware for $DEVICE"
"$ROOT/scripts/extract_fw.sh" "${options[@]}" ||
  s10_die "Firmware extraction failed; check storage, tar integrity and mount permissions"
s10_info "Firmware prepared for $DEVICE"
