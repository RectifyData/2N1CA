# 2N1CA

2N1CA is a work-in-progress custom firmware build system for Samsung Galaxy devices. It is a fork of [UN1CA](https://github.com/salvogiangri/UN1CA), extended with a target for the **Galaxy S10+ (`beyond2lte`, Exynos 9820)**.

The project keeps UN1CA's overall design: the build automatically prepares the required tools, downloads and extracts firmware components, applies patches and generates a flashable zip for the selected target.

> **Status:** the `beyond2lte` target is **not flashable yet**. The Exynos 9820 hardware port is in progress. Build outputs for this target are refused until the required stock-firmware values are provided (see [Exynos 9820 port status](#exynos-9820-port-status)).

# Supported targets

| Codename    | Device                      | SoC        | Partition layout       | Status                  |
|-------------|-----------------------------|------------|------------------------|-------------------------|
| `beyond2lte`| Galaxy S10+ (SM-G975F/N)    | Exynos 9820| Non-dynamic, no `super`| In progress             |

The project's upstream UN1CA targets are documented in the UN1CA repository.

# Exynos 9820 port status

The S10+ target is scaffolded from an older ArtisanROM tree and converted to 2N1CA's configuration keys. The following pieces are in place:

- Target configuration in `target/beyond2lte/config.sh`, including the asserted models (`SM-G975F`, `SM-G975N`) and a non-dynamic, ext4, single-system-image layout
- Floating feature configuration in `target/beyond2lte/sff.sh`
- Exynos 9820 platform configuration in `platform/exynos9820/config.sh`, with a fail-closed loader for the stock ABI manifest
- Installer validation for S10 ZIPs, including boot evidence checks, block mapping protection, and an Edify function allowlist
- CI checks that syntax-check every platform and target configuration and parse all first-party Python

The following are still required before a build is considered complete:

- **Stock firmware identity.** Firmware IDs are never committed. Provide the matching stock firmware through the `S10_TARGET_FIRMWARE_BEYOND2LTE` environment variable (or `S10_TARGET_FIRMWARE`).
- **Vendor ABI manifest.** `vendor-abi.env` must be generated from the matching stock firmware (platform SDK, VNDK, first API, board API, and build.prop / firmware SHA-256 values). Values are not guessed.
- **Partition layout.** `pit-layout.env` must be generated from the matching stock PIT and CSC archive. Partition sizes are not guessed; an unset size causes a deliberate packaging failure.
- **Hardware verification.** A flashed build has to pass the opt-in, read-only ADB boot verification before it is considered working on a device.

Until these are provided, the S10+ target is for development and review only.

# Requirements

- A Linux environment with the build dependencies used by `prepare.sh` and `buildenv.sh`
- For `beyond2lte`: the stock firmware and CSC archive matching the device, and the environment variables listed above
- Enough disk space for firmware downloads and extracted images

# Contributing

Contributions, suggestions, bug reports, and feature requests are welcome. For S10+ / Exynos 9820 work, please include the stock firmware version you tested against and the relevant logs. Do not attach IMEIs, serial numbers, or other device identifiers.

# Licensing

This project is licensed under the terms of the [GNU General Public License v3.0](LICENSE). Because 2N1CA is derived from UN1CA, the original UN1CA copyright notices and license terms are preserved.

External dependencies might be distributed under a different license, such as:
- [android-tools](https://github.com/nmeum/android-tools), licensed under the [Apache License 2.0](https://github.com/nmeum/android-tools/blob/master/LICENSE)
- [apktool](https://github.com/iBotPeaches/Apktool), licensed under the [Apache License 2.0](https://github.com/iBotPeaches/Apktool/blob/master/LICENSE.md)
- [erofs-utils](https://github.com/sekaiacg/erofs-utils/), dual license ([GPL-2.0](https://github.com/sekaiacg/erofs-utils/blob/dev/LICENSES/GPL-2.0), [Apache-2.0](https://github.com/sekaiacg/erofs-utils/blob/dev/LICENSES/Apache-2.0))
- [img2sdat](https://github.com/xpirt/img2sdat), licensed under the [MIT License](https://github.com/xpirt/img2sdat/blob/master/LICENSE)
- [platform_build](https://android.googlesource.com/platform/build/) (ext4_utils, f2fs_utils, signapk), licensed under the [Apache License 2.0](https://source.android.com/docs/setup/about/licenses)

# Credits

2N1CA builds on the work of the UN1CA project. Thanks to:
- **[salvogiangri](https://github.com/salvogiangri)** and all UN1CA contributors, whose project this fork is based on
- **[ShaDisNX255](https://github.com/ShaDisNX255)** for [NcX ROM](https://github.com/ShaDisNX255/NcX_Stock), which inspired UN1CA
- **[DavidArsene](https://github.com/DavidArsene)**, **[paulowesll](https://github.com/paulowesll)**, **[Simon1511](https://github.com/Simon1511)**, **[ananjaser1211](https://github.com/ananjaser1211)**, **[Fede2782](https://github.com/Fede2782)**, **[iDrinkCoffee](https://github.com/iDrinkCoffee-TG)** and **[RisenID](https://github.com/RisenID)** for their help and support on UN1CA
- **[LineageOS Team](https://www.lineageos.org/)** for their original [OTA updater implementation](https://github.com/LineageOS/android_packages_apps_Updater)
- *The ArtisanROM and RebirthROM projects, whose older Galaxy S10 work the `beyond2lte` scaffold was converted from*
