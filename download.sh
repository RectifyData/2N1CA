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
# Never fetch an Android 16 donor using inherited S22 credentials or a
# made-up S25 FE identifier. The firmware ID is supplied as a CI secret.
[[ "$SOURCE_FIRMWARE" == SM-S731B/* ]] ||
  s10_die "E631: Expected S25 FE donor SM-S731B, got a different model"
[[ "$SOURCE_FIRMWARE" != */UNCONFIGURED ]] ||
  s10_die "E632: Set S10_ONEUI_85_SOURCE_FIRMWARE to a verified S25 FE firmware ID"
[[ "$TARGET_FIRMWARE" != "UNCONFIGURED" ]] ||
  s10_die "E633: Configure a private S10_TARGET_FIRMWARE identifier for $DEVICE"
case "$DEVICE" in
  beyond0lte) expected_regex='^(SM-G970F|SM-G970N)$' ;;
  beyond1lte) expected_regex='^(SM-G973F|SM-G973N)$' ;;
  beyond2lte) expected_regex='^(SM-G975F|SM-G975N)$' ;;
  beyondx)    expected_regex='^(SM-G977B|SM-G977N)$' ;;
esac
target_model="${TARGET_FIRMWARE%%/*}"
[[ "$target_model" =~ $expected_regex ]] ||
  s10_die "E634: Target firmware model $target_model does not match $DEVICE"
[[ "$TARGET_FIRMWARE" =~ ^SM-G[0-9]{3}[A-Z]/[A-Z0-9]{3}/[A-Za-z0-9]+$ ]] ||
  s10_die "E635: Malformed target firmware identifier"
[[ "$TARGET_FIRMWARE" != */UNCONFIGURED ]] ||
  s10_die "E636: Stock firmware identifier is not configured"
donor_model="${SOURCE_FIRMWARE%%/*}"
donor_remaining="${SOURCE_FIRMWARE#*/}"
donor_region="${donor_remaining%%/*}"
donor_cache="$FW_DIR/${donor_model}_${donor_region}/system/system/build.prop"
S10_DONOR_CACHED=false
if [[ -s "$donor_cache" ]] &&
   python3 "$ROOT/scripts/internal/validate_oneui_donor.py" "$donor_cache" >/dev/null 2>&1; then
  S10_DONOR_CACHED=true
  s10_info "Retaining verified cached One UI 8.5 donor; ignoring later Android versions"
fi
if ! $S10_DONOR_CACHED && [[ -z "${S10_ONEUI_85_SOURCE_VERSION:-}" ]]; then
  s10_die "E638: No verified cached One UI 8.5 donor and no S10_ONEUI_85_SOURCE_VERSION. Current FUS latest may be Android 17; refuse an unpinned download."
fi
bash "$ROOT/scripts/build_dependencies.sh" --check-tools ||
  s10_die "Host tools absent; run ./prepare.sh $DEVICE first"
options=()
[[ "$MODE" == "--force" ]] && options=(--force)
if $S10_DONOR_CACHED; then
  options+=(--ignore-source)
fi
s10_info "Downloading firmware for $DEVICE (validated One UI donor is pinned or cached)"
"$ROOT/scripts/download_fw.sh" "${options[@]}" ||
  s10_die "Firmware download failed; check model/CSC, connection and credentials"
if ! $S10_DONOR_CACHED; then
  # Samloader/FUS can fall back to newer releases when historical firmware
  # has been withdrawn. Never silently accept an Android 17 archive.
  S10_PINNED_PDA="${S10_ONEUI_85_SOURCE_VERSION%%/*}"
  S10_DONOR_ODIN="$ODIN_DIR/${donor_model}_${donor_region}"
  shopt -s nullglob
  s10_pinned_ap=("$S10_DONOR_ODIN"/AP_"$S10_PINNED_PDA"*.tar.md5)
  shopt -u nullglob
  [[ "${#s10_pinned_ap[@]}" -eq 1 ]] ||
    s10_die "E639: Pinned One UI 8.5 AP archive not found (FUS served another version or package missing)"
fi
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
# The upstream firmware downloader normally selects the newest FUS release.
# Verify the actual extracted firmware, never assume it remained One UI 8.5.
donor_model="${SOURCE_FIRMWARE%%/*}"
donor_rest="${SOURCE_FIRMWARE#*/}"
donor_region="${donor_rest%%/*}"
donor_prop="$FW_DIR/${donor_model}_${donor_region}/system/system/build.prop"
python3 "$ROOT/scripts/internal/validate_oneui_donor.py" "$donor_prop" ||
  s10_die "Donor is not Android 16 / One UI 8.5. Provide a pinned compatible firmware archive."
s10_info "Auditing S10 vendor HAL/init/VINTF/partition layout"
python3 "$ROOT/scripts/internal/s10_vendor_audit.py" \
  "$FW_DIR/${model}_${region}" \
  --output "$OUT_DIR/target/$DEVICE/vendor_audit.json" ||
  s10_die "Target S10 vendor firmware has missing mandatory components"
s10_info "Firmware prepared for $DEVICE"
