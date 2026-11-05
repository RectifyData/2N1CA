#!/usr/bin/env bash
# Shared S10-only build workflow checks.
S10_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
s10_die() { printf '2N1CA: %s\n' "$*" >&2; exit 2; }
s10_info() { printf '[2N1CA] %s\n' "$*"; }
s10_device() {
  case "$1" in
    beyond0lte|beyond1lte|beyond2lte|beyondx) ;;
    *) s10_die "Unsupported target: $1" ;;
  esac
}
s10_require_target() {
  local target="$1" config="$S10_ROOT/target/$1/config.sh"
  local fstab="$S10_ROOT/target/$1/installer/recovery.fstab"
  s10_device "$target"
  [[ -f "$config" ]] || s10_die "Missing S10 target/$target/config.sh"
  [[ -d "$S10_ROOT/platform/exynos9820" ]] || s10_die "Missing Exynos9820 platform folder"
  grep -Eq '^TARGET_PLATFORM="?exynos9820"?$' "$config" || s10_die "Wrong S10 platform"
  grep -Eq '^TARGET_USE_DYNAMIC_PARTITIONS=(false|"false")$' "$config" || s10_die "Legacy partitions must be explicit"
  grep -Eq '^TARGET_OS_FILE_SYSTEM_TYPE="?ext4"?$' "$config" || s10_die "S10 ext4 configuration missing"
  grep -Eq '^TARGET_OS_SINGLE_SYSTEM_IMAGE="?(essi|qssi)"?$' "$config" || s10_die "SSI config missing"
  [[ -f "$fstab" ]] || fstab="$S10_ROOT/platform/exynos9820/installer/recovery.fstab"
  [[ -s "$fstab" ]] || s10_die "Missing S10 recovery.fstab; unsafe flash prevented"
}
s10_env() {
  cd "$S10_ROOT" || s10_die "Cannot open repository root"
  # shellcheck source=/dev/null
  source "$S10_ROOT/buildenv.sh" "$1" || s10_die "Unable to load S10 build environment"
}
s10_package() {
  local target="$1" candidate="" file=""
  local -a matches=()
  shopt -s nullglob
  matches=("$S10_ROOT"/out/*_"$target"-sign.zip "$S10_ROOT"/out/*_"$target".zip)
  shopt -u nullglob
  for file in "${matches[@]}"; do
    [[ -f "$file" && ! -L "$file" ]] || continue
    if [[ -z "$candidate" || "$file" -nt "$candidate" ]]; then candidate="$file"; fi
  done
  [[ -n "$candidate" ]] || s10_die "No $target flashable ZIP found"
  printf '%s\n' "$candidate"
}

# Called after download.sh: prevent stale PIT or missing capacities from reaching mkfs.
s10_require_pit_layout() {
  local device="$1" layout="$S10_ROOT/out/target/$1/pit-layout.env"
  local firmware_hash value key
  [[ -s "$layout" ]] || s10_die "Missing stock PIT layout for $device; run ./download.sh $device"
  firmware_hash="$(printf '%s' "$TARGET_FIRMWARE:$S10_TARGET_FIRMWARE_VERSION" | sha256sum | cut -d ' ' -f 1)"
  grep -qxF "S10_TARGET_FIRMWARE_SHA256=\"$firmware_hash\"" "$layout" ||
    s10_die "PIT layout does not match current target firmware; redownload"
  grep -Eq '^S10_SOURCE_PIT_SHA256="[0-9a-f]{64}"$' "$layout" ||
    s10_die "No valid PIT checksum found"
  for key in SYSTEM VENDOR PRODUCT ODM BOOT; do
    value="TARGET_${key}_PARTITION_SIZE"
    if [[ ! "${!value:-}" =~ ^[0-9]+$ ]] || (( ${!value:-0} <= 0 )); then
      s10_die "Unverified partition size: $value; aborting before image build"
    fi
  done
  s10_info "PIT-derived capacities validated for $device; physical device still untested"
}

# Bind loaded build properties to a specific extracted firmware version.
s10_require_vendor_abi() {
  local dev="$1" path="$S10_ROOT/out/target/$1/vendor-abi.env"
  [[ -s "$path" ]] || s10_die "E748: No verified S10 stock ABI manifest"
  local model="${TARGET_FIRMWARE%%/*}" other="${TARGET_FIRMWARE#*/}"
  local region="${other%%/*}" vendor="$S10_ROOT/out/fw/${model}_${region}/vendor/build.prop"
  [[ -s "$vendor" ]] || s10_die "E749: Missing extracted stock vendor/build.prop"
  local sha firmware_sha
  sha="$(sha256sum "$vendor" | cut -d ' ' -f1)"
  firmware_sha="$(printf '%s' "$TARGET_FIRMWARE:$S10_TARGET_FIRMWARE_VERSION" | sha256sum | cut -d ' ' -f1)"
  grep -qxF "S10_VENDOR_BUILD_PROP_SHA256=\"$sha\"" "$path" ||
    s10_die "E750: Vendor ABI evidence does not match extracted vendor bytes"
  grep -qxF "S10_VENDOR_FIRMWARE_SHA256=\"$firmware_sha\"" "$path" ||
    s10_die "E751: Vendor ABI evidence belongs to another firmware version"
  local name value
  for name in TARGET_PLATFORM_SDK_VERSION TARGET_PRODUCT_SHIPPING_API_LEVEL TARGET_BOARD_API_LEVEL TARGET_VNDK_VERSION; do
    value="${!name:-0}"
    [[ "$value" =~ ^[0-9]+$ && "$value" -ge 28 && "$value" -le 36 ]] ||
      s10_die "E752: Missing or invalid stock vendor ABI value for $name: $value"
  done
}
