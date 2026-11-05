# Galaxy S10 ships a different vendor HAL contract from the S22 donor.
# In the initial port, use stock target VINTF documents as an explicit baseline.
# Their Android 16 runtime compatibility must still pass checkvintf on a full build.
S10_STOCK_VINTF=""
if [[ "${TARGET_PLATFORM:-}" == "exynos9820" ]]; then
    S10_FIRMWARE_DIR="$(cut -d / -f 1 <<< "$TARGET_FIRMWARE")_$(cut -d / -f 2 <<< "$TARGET_FIRMWARE")"
    S10_STOCK_VINTF="$FW_DIR/$S10_FIRMWARE_DIR/system/system/etc/vintf"
fi

S10_COPY_VINTF()
{
    local file="$1"
    local source="$S10_STOCK_VINTF/$1"
    local destination="$WORK_DIR/system/system/etc/vintf/$1"
    if [[ ! -s "$source" ]]; then
        ABORT "E670: Missing S10 stock VINTF $file; cannot use S22 framework HAL contract"
    fi
    if ! python3 -c 'import sys, xml.etree.ElementTree as ET; ET.parse(sys.argv[1])' "$source"; then
        ABORT "E671: Invalid S10 VINTF XML $file"
    fi
    LOG "- Installing S10 stock VINTF baseline: $file (Android 16 check still required)"
    mkdir -p "$(dirname "$destination")" || return 1
    cp -a "$source" "$destination" || return 1
    return 0
}

_LOG() { if $DEBUG; then LOGW "$1"; else ABORT "$1"; fi }

if [ -f "$SRC_DIR/target/$TARGET_CODENAME/vintf/compatibility_matrix.device.xml" ]; then
    LOG "- Adding /system/system/etc/vintf/compatibility_matrix.device.xml"
    EVAL "cp -a \"$SRC_DIR/target/$TARGET_CODENAME/vintf/compatibility_matrix.device.xml\" \"$WORK_DIR/system/system/etc/vintf/compatibility_matrix.device.xml\""
elif [ -n "$S10_STOCK_VINTF" ]; then
    S10_COPY_VINTF "compatibility_matrix.device.xml" || return 1
elif [[ "$SOURCE_PLATFORM_SDK_VERSION" == "$TARGET_PLATFORM_SDK_VERSION" ]]; then
    ADD_TO_WORK_DIR "$TARGET_FIRMWARE" "system" "system/etc/vintf/compatibility_matrix.device.xml"
else
    _LOG "File not found: $SRC_DIR/target/$TARGET_CODENAME/vintf/compatibility_matrix.device.xml"
fi

if [ -f "$SRC_DIR/target/$TARGET_CODENAME/vintf/manifest.xml" ]; then
    LOG "- Adding /system/system/etc/vintf/manifest.xml"
    EVAL "cp -a \"$SRC_DIR/target/$TARGET_CODENAME/vintf/manifest.xml\" \"$WORK_DIR/system/system/etc/vintf/manifest.xml\""
elif [ -n "$S10_STOCK_VINTF" ]; then
    # Android 16 framework HAL registrations are owned by the donor system.
    # Replacing them with Android 12 stock SYSTEM manifest silently removes
    # framework services. The S10 vendor manifest remains in /vendor.
    S10_FRAMEWORK_MANIFEST="$WORK_DIR/system/system/etc/vintf/manifest.xml"
    if [[ ! -s "$S10_FRAMEWORK_MANIFEST" ]]; then
        ABORT "E672: Android 16 framework manifest absent; refusing S10 VINTF port"
    fi
    if ! python3 -c 'import sys, xml.etree.ElementTree as ET; ET.parse(sys.argv[1])' "$S10_FRAMEWORK_MANIFEST"; then
        ABORT "E673: Malformed Android 16 framework manifest"
    fi
    LOG "- Retaining Android 16 framework manifest; S10 vendor HALs come from stock vendor"
    unset S10_FRAMEWORK_MANIFEST
elif [[ "$SOURCE_PLATFORM_SDK_VERSION" == "$TARGET_PLATFORM_SDK_VERSION" ]]; then
    ADD_TO_WORK_DIR "$TARGET_FIRMWARE" "system" "system/etc/vintf/manifest.xml"
fi

unset -f _LOG

unset S10_STOCK_VINTF S10_FIRMWARE_DIR
unset -f S10_COPY_VINTF
