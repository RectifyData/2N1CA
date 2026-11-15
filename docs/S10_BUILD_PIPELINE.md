# 2N1CA — Galaxy S10 build and installer workflow

This repository has four root-level build steps. They are **not** a replacement for
the Exynos 9820 hardware port, and they do not make an unverified ZIP safe to flash.

## Usage

Run from Linux (or an appropriately configured Linux build environment).

```bash
bash prepare.sh beyond2lte
bash download.sh beyond2lte
bash build.sh beyond2lte
bash verify.sh beyond2lte /path/to/2N1CA_flashable.zip
```

Supported target names: `beyond0lte` (S10e), `beyond1lte` (S10),
`beyond2lte` (S10+), `beyondx` (S10 5G).

- **prepare.sh** — rejects unported/non-S10 targets; checks S10 config,
  non-dynamic ext4 layout, installer recovery fstab, host Python tests and
  Bash syntax; builds needed host dependencies.
- **download.sh** — validates the selected target, downloads Samsung source
  and stock target firmwares, and extracts components. Optional `--force`
  refreshes both.
- **build.sh** — orchestrates preparation, download/extraction, forced ROM
  build, full flashable ZIP packaging and postbuild verification.
- **verify.sh** — checks ZIP structure, target/model metadata, installer
  references, payload presence, ZIP CRCs, forbidden S10 partition operations,
  and writes `.sha256` beside the validated ZIP.

## Experimental TWRP ZIP for testers (not boot-verified)

Use **Actions → 2N1CA S10 sync and build**, branch
`port/s10-exynos9820`, device `beyond2lte`, mode
`tester-zip`. This builds the pinned Android-Artisan Exynos9820 kernel
in a separate job, records the exact `boot.img` SHA256 and commit,
downloads its compiled artifact, and builds a complete recovery ZIP from
the actual donor and S10 stock firmware. If packaging and static integrity
checks pass, a **clearly labelled untested prerelease** is created.

The normal full `build` mode still requires independent physical
boot verification. In the `tester-zip` mode **only**, prior boot approval
is replaced by kernel compilation provenance and per-file SHA256 checks;
device/model assertions, stock PIT sizes, OTA/ZIP integrity tests, and
framework/security audits are retained. A missing `checkvintf` binary
is recorded as unverified, and a present checker reporting incompatibility
still blocks the build.

Both source and matching S10+ stock firmware identifiers/versions must be
provided through GitHub Actions secrets. They are **not guessed**.
The kernel has not been demonstrated to boot Android 16. Its build
provenance is not a hardware certification.

For an equivalent **local tester compilation** after preparing a verified
kernel artifact and its provenance JSON:

```bash
export S10_EXPERIMENTAL_BOOT_IMAGE=/absolute/path/to/compiled/boot.img
export S10_EXPERIMENTAL_KERNEL_PROVENANCE=/absolute/path/to/provenance.json
bash build.sh beyond2lte --tester-zip
```

**The output is experimental and may fail to install or boot.**
Only use a sacrificial or fully recoverable test phone with matching PIT
and verified stock restoration. The installer never silently repartitions,
wipes EFS, flashes a donor bootloader or claims runtime compatibility.

For a **non-flashable framework compilation** (no validated boot image
required), use `./build.sh beyond2lte --target-files-only`. This still needs
authorized One UI 8.5 donor firmware, matching S10 stock firmware, usable
partition sizes, host dependencies, and a complete framework/VINTF patch
set. It creates *target-files*, not a recovery installer. GitHub Actions
`s10-build.yml` exposes this as `mode: target-files` and labels any artifact
**DO-NOT-FLASH**. The normal flashable build remains blocked until kernel
and recovery compatibility have been independently established.

For automated CI, the lightweight
`.github/workflows/s10-installer-checks.yml` runs tests without requiring
firmware downloads or accessing a real phone.

## Error handling

Recovery's generic **Error 1 cannot be eliminated universally**.
A safe installer must refuse an incompatible ZIP or failed write instead of
claiming success. These scripts try to catch preventable packaging mistakes
during CI and emit precise E5xx diagnostics. They do not conceal real failures.

## Porting requirements

The port branch now contains all four S10 target configurations and
an Exynos9820 platform scaffold, but the port is **not complete**. Build-time
validation still stops on missing stock PIT information, unverified kernel
components, unsupported donor versions and unresolved framework/HAL compatibility.

The S10-specific framework audit checks per-device floating features and
resource overlays and, when firmware is available, rebuilt framework archives,
SystemUI, Samsung Camera, device/vendor identity, SELinux and VINTF evidence.
The full build invokes it before caching target files. The audit does not
establish bootability or compatibility of the proprietary HALs.

Do not reuse S21 firmware installer scripts or dynamic partition handling.
A compatible legacy S10 recovery fstab and verified partition sizes are
necessary. Treat boot, modem, EFS, calibration, and device-unique partitions
as protected. Thermal, audio, camera, RIL, vendor, SELinux, kernel, and VINTF
compatibility still require dedicated hardware validation.

This is a **development-only** branch. No boot-tested or flash-safe S10 ROM
has been produced by these changes.
