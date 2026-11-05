#!/usr/bin/env bash
# Validate installer archive, device ID, referenced payloads and ZIP CRC.
# This cannot establish bootability without actual device testing.
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/lib/s10_pipeline.sh
source "$ROOT/scripts/lib/s10_pipeline.sh"
[[ "$#" -ge 1 && "$#" -le 2 ]] || s10_die "Usage: ./verify.sh beyond2lte [path/to/flashable.zip]"
DEVICE="$1"
s10_device "$DEVICE"
FILE="${2:-}"
if [[ -z "$FILE" ]]; then FILE="$(s10_package "$DEVICE")"; fi
[[ -f "$FILE" && ! -L "$FILE" ]] || s10_die "Missing or unsafe ZIP file: $FILE"
command -v python3 >/dev/null || s10_die "Python 3 required"
s10_info "Running installer unit tests"
python3 -m unittest discover -s "$ROOT/scripts/tests" -p 'test_*.py' -v ||
  s10_die "Installer regression tests failed"
# The stock PIT is the only supported source for partition capacities.
# A ZIP without this manifest must not be labelled an S10 release candidate.
LAYOUT="$ROOT/out/target/$DEVICE/pit-layout.env"
[[ -s "$LAYOUT" ]] || s10_die "E610: No verified S10 stock PIT manifest; refusing ZIP verification"
s10_info "Checking recorded S10 kernel provenance and independent device-test report"
BOOT_MANIFEST="$ROOT/platform/exynos9820/kernel/boot-image-validated.json"
BOOT_REPORT="$ROOT/out/target/$DEVICE/boot-test-report.json"
python3 "$ROOT/scripts/internal/s10_boot_integrity.py" \
  --target "$DEVICE" --manifest "$BOOT_MANIFEST" --test-report "$BOOT_REPORT" ||
  s10_die "E620: Boot evidence missing; ZIP cannot be certified"
s10_info "Checking ZIP payload ranges, stock PIT capacities, boot hash and CRC"
python3 "$ROOT/scripts/internal/validate_flashable_zip.py" "$FILE" \
  --expected-device "$DEVICE" --layout "$LAYOUT" --deep \
  --boot-manifest "$BOOT_MANIFEST" ||
  s10_die "ZIP rejected; do not install or release"
s10_info "Writing SHA256 checksum"
sha256sum "$FILE" > "$FILE.sha256" || s10_die "Cannot write checksum"
s10_info "Static verification passed: $FILE"
s10_info "This does not certify flash safety, bootability, camera, radio or SELinux"
