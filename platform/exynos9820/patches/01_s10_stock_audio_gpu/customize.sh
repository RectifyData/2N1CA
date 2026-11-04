# SPDX-License-Identifier: GPL-3.0-or-later
# Derived from the archived ArtisanROM Exynos9820 stock_blobs module:
# platform/exynos9820/patches/stock_blobs/customize.sh
# Only use exact matching S10 stock firmware. Does not certify runtime ABI.
[[ "${TARGET_PLATFORM:-}" == "exynos9820" ]] || return 0
S10_MODEL="${TARGET_FIRMWARE%%/*}"
S10_REST="${TARGET_FIRMWARE#*/}"
S10_REGION="${S10_REST%%/*}"
S10_STOCK="$FW_DIR/${S10_MODEL}_${S10_REGION}/system/system"

# Never discard donor components unless their S10 replacements were found.
S10_AUDIO_LIBS=(lib_SoundBooster_ver1000.so libsamsungSoundbooster_plus_legacy.so)
for S10_LIB in "${S10_AUDIO_LIBS[@]}"; do
    if [[ ! -s "$S10_STOCK/lib64/$S10_LIB" ]]; then
        ABORT "E690: Required S10 SoundBooster replacement absent: $S10_LIB"
    fi
done
LOG "- Replacing newer donor SoundBooster with Exynos9820 stock components"
for S10_DONOR_LIB in lib_SoundBooster_ver2080.so lib_SAG_EQ_ver2080.so libsoundboostereq_legacy.so; do
    [[ -f "$WORK_DIR/system/system/lib64/$S10_DONOR_LIB" ]] &&
        DELETE_FROM_WORK_DIR "system" "system/lib64/$S10_DONOR_LIB"
done
for S10_LIB in "${S10_AUDIO_LIBS[@]}"; do
    ADD_TO_WORK_DIR "$TARGET_FIRMWARE" "system" "system/lib64/$S10_LIB" \
        0 0 644 "u:object_r:system_lib_file:s0" || return 1
done

# GPU apps must match Exynos9820 rather than the new donor GPU driver.
S10_GPU_APPS=(GameDriver-EX9820 DevGPUDriver-EX9820)
for S10_APP in "${S10_GPU_APPS[@]}"; do
    if [[ ! -s "$S10_STOCK/priv-app/$S10_APP/$S10_APP.apk" ]]; then
        ABORT "E691: Required stock Exynos9820 driver APK absent: $S10_APP"
    fi
    ADD_TO_WORK_DIR "$TARGET_FIRMWARE" "system" \
        "system/priv-app/$S10_APP/$S10_APP.apk" \
        0 0 644 "u:object_r:system_file:s0" || return 1
done
unset S10_MODEL S10_REST S10_REGION S10_STOCK S10_AUDIO_LIBS S10_LIB S10_DONOR_LIB S10_GPU_APPS S10_APP
