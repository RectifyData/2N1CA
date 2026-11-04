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
