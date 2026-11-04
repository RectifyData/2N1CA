#!/usr/bin/env bash
# Prepare reproducible 2N1CA Galaxy S10 builds. No devices are flashed.
set -eo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/lib/s10_pipeline.sh
source "$ROOT/scripts/lib/s10_pipeline.sh"
[[ "$#" -eq 1 ]] || s10_die "Usage: ./prepare.sh beyond2lte"
DEVICE="$1"
s10_require_target "$DEVICE"
command -v python3 >/dev/null || s10_die "Python 3 is required"
s10_info "Checking installer regression tests"
python3 -m unittest discover -s "$ROOT/scripts/tests" -p 'test_*.py' -v
s10_info "Checking shell syntax"
for script in "$ROOT/prepare.sh" "$ROOT/download.sh" "$ROOT/build.sh" "$ROOT/verify.sh" "$ROOT/scripts/lib/s10_pipeline.sh"; do
  [[ -f "$script" ]] || s10_die "Required pipeline script absent: $script"
  bash -n "$script" || s10_die "Shell syntax failure: $script"
done
s10_info "Checking external source submodules"
if command -v git >/dev/null 2>&1 && [[ -d "$ROOT/.git" ]]; then
  git -C "$ROOT" submodule update --init --recursive ||
    s10_die "Cannot initialize required build submodules"
fi
s10_info "Building required host tools (reuses already-built dependencies)"
bash "$ROOT/scripts/build_dependencies.sh" || s10_die "Host tool build failed"
s10_env "$DEVICE"
s10_info "Preparation succeeded for $DEVICE; boot compatibility is NOT verified"
