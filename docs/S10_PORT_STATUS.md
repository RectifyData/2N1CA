# 2N1CA / Exynos 9820 — migration status

> **DEVELOPMENT ONLY — NOT SAFE TO FLASH.** No S10 boot, recovery installation,
> modem, NFC, camera, Wi-Fi, graphics, telephony, encryption, or SELinux test on
> physical hardware has been completed. This source branch does not yet supply a
> validated flashable ROM.

## Scope

This branch intentionally contains only these Exynos Galaxy S10 targets:

| Codename | Model | Exynos |
|---|---|---|
| `beyond0lte` | S10e SM-G970F / SM-G970N | 9820 |
| `beyond1lte` | S10 SM-G973F / SM-G973N | 9820 |
| `beyond2lte` | S10+ SM-G975F / SM-G975N | 9820 |
| `beyondx` | S10 5G SM-G977B / SM-G977N | 9820 |

Archive-derived device floating features and overlays were imported from
[ArtisanROM_old `sixteen-old`](https://github.com/ArtisanROM-archive/ArtisanROM_old/tree/sixteen-old)
(see license in upstream). This branch uses the new 2N1CA `TARGET_...` key schema.

## Operating-system donor

The S10-specific Exynos SSI configuration now selects the Samsung Galaxy S25
FE (SM-S731B) as an **experimental Android 16 / One UI 8.5 donor** instead of
the previous S22 One UI 8.0 firmware. Samsung announced One UI 8.5 on S25 FE in
May 2026. Verified stock build examples include `S731BXXU6BZDP`, but the
firmware auto-downloader may select a **newer Android 17 / One UI 9 build**.

The donor version gate reads the actual extracted `build.prop` and rejects
all firmware that does not identify as Android SDK 36 and One UI 8.5.
An authenticated/cached historical One UI 8.5 source archive may be required
if Samsung's firmware service now returns One UI 9.

**Changing the donor does not automatically port every One UI framework patch.**
Existing UN1CA 3.2.1 patches must be reviewed and reworked against the actual
8.5 APK/JAR/binary versions. Stock S10 Android 12 vendor HALs also need
compatibility work for Android 16; do not assume a successful image build boots.

## Recovery ZIP and partition safety

- Legacy `ext4` partitions; no dynamic super partition or retrofit super.
- `platform/exynos9820/installer/recovery.fstab` names only allowed
  legacy OS partitions and boot.
- The stock Samsung CSC PIT is parsed for system/vendor/product/odm/boot
  capacities. No capacity is invented or copied from a different device.
- Each cached PIT-derived layout is associated with a SHA256 of the stock
  target firmware identifier; credentials are not printed in normal build logs.
- Before image creation, all five capacities must be present and numeric.
- The installer excludes unsupported modern boot images, includes required
  block-patch files, checks ZIP CRCs, and rejects unrecognized S10 partition
  writes in the static pre-release validator.
- A source-only kernel marker blocks flashable packaging until there is a
  separately validated Android 16-capable Exynos9820 boot image.
- No EFS, modem calibration, metadata, bootloader or unique device partitions
  are wiped, resized, or intentionally included in S10 ZIPs.

Note that **a valid CSC PIT is not necessarily the PIT installed on a phone
that has previously been repartitioned**. A physical per-device partition audit
remains mandatory before any installation.

## Build workflow

The four top-level commands are `prepare.sh`, `download.sh`, `build.sh`,
and `verify.sh`. The GitHub Actions **2N1CA S10 sync and build** workflow
supports a light `config` check or an explicit `build` request, selecting
one of the four target codenames.

Optional private secrets used by the manual build workflow:
`S10_SOURCE_FIRMWARE` and `S10_TARGET_FIRMWARE`. These are intended for
permitted Samsung firmware download credentials and are **not stored in Git**.

The experimental kernel CI compiles pinned
[Android-Artisan Exynos 9820 kernel](https://github.com/Android-Artisan/android_kernel_samsung_exynos9820)
revision `9a0a792d227c8ae6cddac0c9d68a8bb9782c44cb`. Its output is a
developer artifact, **not a validated Galaxy S10 ROM**.

## Framework adaptation work

- Imported S10-specific floating-feature profiles and framework-res overlays for all four variants.
- Updated the build to obtain system device/model identity from matching S10 stock vendor properties instead of retaining the One UI donor's device identity.
- Added a platform patch to install the appropriate stock S10 camera capability XML after validation. Actual camera HAL compatibility is still unverified.
- Updated the VINTF patch path to prefer extracted S10 stock system manifests and compatibility matrices instead of silently retaining donor files. Android 16 checkvintf and vendor HAL compatibility still must be proven.
- Added a per-variant framework audit: verifies profile and overlay XML, identity, framework/telephony/SSRM JARs, Settings, SystemUI, SamsungCamera, floating-feature XML, vendor SELinux metadata and VINTF XML before marking the work directory complete.
- Existing UN1CA smali patches are applied using S10 target feature settings; they have not yet been verified against every One UI 8.5 APK/JAR method and vendor interface.

**This source is still not a boot-verified or flash-safe ROM.** The framework audit checks file structure and consistency, not runtime behavior. Thermal policy, Exynos9820 vendor HALs, APEX compatibility, SELinux, NFC, camera, audio, graphics, fingerprint, modem and recovery installation all remain hardware-dependent blockers.

### Framework verification and donor isolation (current branch)

- Runtime system identity is sourced from matching S10 stock vendor properties, with model checks before overwriting the One UI donor properties.
- The S10 build selects a Galaxy S25 FE donor profile; actual Android 16/One UI 8.5 properties are validated after extraction, and an unconfigured donor is rejected.
- Per-device framework and SystemUI resource overlays and floating-feature profiles have been imported; source availability and XML syntax are checked.
- VNDK 31 for S10 stock vendor is separate from S10 original launch board API 28 and from donor board API 34. The compatibility script rejects unrelated Qualcomm APEX substitutions.
- The Exynos9820 NFC path preserves SLSI stock variants rather than injecting a newer, unrelated NFC JNI library.
- The final Samsung camera capability XML is checked by hash against the matching S10 stock firmware, not merely by XML syntax.
- Samsung Device Health Manager's rebuilt APK is checked for the exact S10 SSRM/thermal policy name. Missing policy is a hard E734 error; donor thermal policy is not substituted.
- Framework JARs/APKs, VINTF manifest XML, SELinux policy version, Android SDK, One UI version and S10 device identity are checked before target-files packaging.

These checks do **not** make ART, APEX, HIDL/AIDL, RIL, camera, audio, graphics, fingerprint, Bluetooth or NFC work at runtime. They detect mismatches in available source and images. Firmware extraction, dependency resolution, and physical-device testing are still outstanding.

## Non-flashable integration build route

The new `--target-files-only` mode compiles the framework and produces a
target-files archive for inspection without requiring the boot-image safety
marker. It cannot be installed via recovery. On the manual S10 GitHub Actions
workflow, select `target-files` instead of `build` for this stage.

The experimental Exynos 9820 kernel build workflow has also been started.
Compilation and a valid Android boot-image header cannot establish that
a Galaxy S10 will reach the lock screen. None of this constitutes physical
boot evidence.

## Remaining blockers

1. Obtain per-variant stock PIT/firmware data and compare with the *actual*
   on-device partition map; never repartition an only device as a shortcut.
2. Complete One UI 8.5 framework/APEX/system_ext adaptation for S10's Android
   12 vendor, VNDK/HIDL/AIDL bridges, init services, SELinux, VINTF and kernel.
3. Validate selected Exynos 9820 boot image and device tree; a header check,
   checksum or successful compilation is **not** a successful boot test.
4. Confirm at minimum calls/data/SMS, graphics, camera, audio, Wi-Fi, BT,
   NFC, thermal protections, fingerprint, encryption and recovery behavior.
5. Only after independent hardware evidence, consider a clearly labeled
   test ROM release. The installer must stop on irrecoverable failures even
   if recovery displays its generic "Error 1" status.

The `sixteen` branch is unchanged by this experimental migration.

## November 4 engineering regression audit

The S10-only branch now separates **source validation** from manual firmware
compilation. The old CI attempted four firmware builds automatically and
failed installing an unavailable `linux-modules-extra` package on GitHub's
hosted runner. The replacement CI runs Bash/Python tests and source
configuration checks for each S10 target without misrepresenting those checks
as a booted ROM. `s10-build.yml` remains the manual firmware-build entry
point; kernel development uses a separate experimental workflow.

The flashable ZIP verifier now parses full-OTA sdat transfer ranges, compares
them with stock CSC PIT capacities, detects missing/corrupt metadata, rejects
oversized raw boot images, and forbids auxiliary DT/DTBO/vendor_boot/init_boot
writes without verified S10 partition mappings. It requires a PIT manifest
at packaging time; the source PIT alone cannot prove the actual partition
map of a phone that was repartitioned previously.

Four archived demonstration firmware identifiers have been removed from the
device targets. Private `S10_TARGET_FIRMWARE` (or its target-specific
`S10_TARGET_FIRMWARE_BEYOND*` equivalents) is required for downloading
firmware; source and target models are checked to avoid mixing a Galaxy S10
5G and S10+. The source donor ID is separately configured through
`S10_ONEUI_85_SOURCE_FIRMWARE` and remains a hard prerequisite for a
real firmware compile. Neither value should be checked into Git.

Framework model properties are now required to match the actual target
model allowlist. Third-party recoveries that omit `ro.boot.em.model` can
use the S10 codename fallback in the Edify assertion; a present but
mismatched bootloader model is never ignored.

### Unresolved, do-not-flash conditions

- No validated One UI 8.5 donor firmware extraction, VINTF runtime compatibility
  test, or complete framework/APEX/native library port is available.
- Proprietary Exynos 9820 graphics, RIL, NFC, Wi-Fi, Bluetooth, camera, fingerprint,
  thermal and audio integration is not proven on Android 16.
- Bootloader, ramdisk, kernel, recovery and real on-device partition mappings
  have not been validated for a safe flashable image. The kernel compiler
  workflow, even if successful, is not evidence of a completed boot.
- None of the four variants has a demonstrated first boot or a hardware
  regression pass. Do not download this prerelease for flashing on a daily
  driver or only phone.

## November 4 — additional framework and kernel integration audit

- The pinned experimental Exynos9820 kernel workflow **compiled successfully** for
  `beyond2lte` on GitHub Actions (run 41921304830). This only establishes that
  the source builds and boot image header exists; it does not prove compatible
  Android 16 init, display, drivers or a completed boot. Artifacts remain DO-NOT-FLASH.
- Removed a contradictory duplicate One UI donor profile from `essi.sh`.
- Fixed framework VINTF handling: the Android 12 S10 system manifest must not
  replace Android 16 framework HAL registrations. The Android 16 source system
  manifest is retained while the S10 vendor manifest remains stock-derived.
- Added `scripts/internal/s10_checkvintf.py`, which invokes Android's official
  `checkvintf --check-compat` against the assembled system, vendor, product, ODM
  and system_ext partition tree. The command's absence is allowed only for
  *non-flashable* development output. An actual flashable candidate requires
  the checker and a successful compatibility result. The runner does not
  emulate a device kernel.
- Added `scripts/internal/s10_init_audit.py` to resolve vendor/ODM init
  service executable paths against the merged ROM after patching. Missing
  declared vendor binaries block image packaging instead of causing a runtime
  service-start failure to go unnoticed.
- Added post-compression Brotli integrity checks for full-OTA block payloads
  prior to discarding their uncompressed bytes. These checks reduce packaging
  failures but cannot prevent every recovery-side installation failure.

**Still missing:** Actual One UI 8.5 donor firmware extraction and APK/DEX
compatibility verification, complete Exynos 9820 hardware service adaptations,
VTS and SELinux validation, flash-safe kernel/ramdisk evidence, and a physical
boot. The ROM remains source-stage experimental.
