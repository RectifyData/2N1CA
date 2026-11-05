#!/usr/bin/env bash
# Install an operator-supplied, SHA256-pinned Android 16 AOSP checkvintf host binary.
# Official source: android.googlesource.com/platform/system/libvintf
# Build in AOSP Android 16 with: m checkvintf (out/host/linux-x86/bin/checkvintf)
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
DEST="$ROOT/out/tools/bin/checkvintf"
SHA="${S10_CHECKVINTF_SHA256:-}"
[[ "$SHA" =~ ^[a-f0-9]{64}$ ]] || {
  echo "E760: Set S10_CHECKVINTF_SHA256 from a verified Android 16 host build" >&2
  exit 2
}
verify_binary() {
  local src="$1" magic
  [[ -s "$src" ]] || return 1
  magic="$(head -c5 "$src" | od -An -tx1 | tr -d ' \n')"
  [[ "$magic" == 7f454c4602 ]] || return 1  # ELF64, not shell stub or Python
  [[ "$(sha256sum "$src" | cut -d' ' -f1)" == "$SHA" ]] || return 1
  chmod u+x "$src"
  local help
  help="$("$src" --help 2>&1)" || {
    [[ "$help" == *--check-compat* ]] || return 1
  }
  [[ "$help" == *--check-compat* && "$help" == *--dirmap* &&
     "$help" == *--property* ]] || return 1
  return 0
}
if [[ -s "$DEST" ]] && verify_binary "$DEST"; then
  echo "2N1CA: SHA256-pinned Android 16 checkvintf already installed"
  exit 0
fi
mkdir -p "$ROOT/out/tools/bin"
tmp="$(mktemp "$ROOT/out/tools/bin/.checkvintf.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
if [[ -n "${S10_CHECKVINTF_SOURCE:-}" ]]; then
  [[ -f "$S10_CHECKVINTF_SOURCE" ]] || { echo "E760: checkvintf source file missing" >&2; exit 2; }
  cp -- "$S10_CHECKVINTF_SOURCE" "$tmp"
elif [[ -n "${S10_CHECKVINTF_URL:-}" ]]; then
  [[ "$S10_CHECKVINTF_URL" == https://* ]] || {
    echo "E760: only HTTPS is allowed for checkvintf" >&2; exit 2;
  }
  curl --fail --location --silent --show-error --max-time 180 \
    "$S10_CHECKVINTF_URL" --output "$tmp"
else
  echo "E760: Provide S10_CHECKVINTF_SOURCE or S10_CHECKVINTF_URL and pinned SHA256" >&2
  exit 2
fi
if ! verify_binary "$tmp"; then
  echo "E764: checkvintf is not the exact pinned ELF64 host binary or lacks required flags" >&2
  exit 2
fi
mv -f "$tmp" "$DEST"
chmod 755 "$DEST"
echo "2N1CA: pinned Android 16 checkvintf installed; HAL compatibility NOT yet tested"
