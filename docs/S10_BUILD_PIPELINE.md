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

For automated CI, the lightweight
`.github/workflows/s10-installer-checks.yml` runs tests without requiring
firmware downloads or accessing a real phone.

## Error handling

Recovery's generic **Error 1 cannot be eliminated universally**.
A safe installer must refuse an incompatible ZIP or failed write instead of
claiming success. These scripts try to catch preventable packaging mistakes
during CI and emit precise E5xx diagnostics. They do not conceal real failures.

## Porting requirements

The source branch currently does **not** contain production-ready
`target/beyond*` directories or a compatible `platform/exynos9820` stack.
Until those are integrated, `prepare.sh` deliberately stops before downloading
firmware or creating a dangerous package.

Do not reuse S21 firmware installer scripts or dynamic partition handling.
A compatible legacy S10 recovery fstab and verified partition sizes are
necessary. Treat boot, modem, EFS, calibration, and device-unique partitions
as protected. Thermal, audio, camera, RIL, vendor, SELinux, kernel, and VINTF
compatibility still require dedicated hardware validation.

This is a **development-only** branch. No boot-tested or flash-safe S10 ROM
has been produced by these changes.
