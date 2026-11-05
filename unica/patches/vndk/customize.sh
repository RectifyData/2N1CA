TARGET_VNDK_LEVEL="${TARGET_VNDK_VERSION:-$TARGET_BOARD_API_LEVEL}"
if [[ "$SOURCE_BOARD_API_LEVEL" == "$TARGET_VNDK_LEVEL" ]]; then
    LOG "\033[0;33m! Nothing to do\033[0m"
    return 0
fi

# [
ADD_TARGET_VNDK_APEX() {
    # An Exynos 9820 target must use its own Android 12 VNDK, not the
    # unrelated Qualcomm/A-series fallback previously used for API 31.
    if [[ "${TARGET_PLATFORM:-}" == "exynos9820" ]]; then
        if [[ "$TARGET_VNDK_LEVEL" != "31" ]]; then
            ABORT "E674: unsupported Exynos9820 VNDK level $TARGET_VNDK_LEVEL"
        fi
        local firmware_path source_apex candidate
        firmware_path="$(cut -d / -f 1 <<< "$TARGET_FIRMWARE")_$(cut -d / -f 2 <<< "$TARGET_FIRMWARE")"
        source_apex=""
        for candidate in \
            "$FW_DIR/$firmware_path/system_ext/apex/com.android.vndk.v31.apex" \
            "$FW_DIR/$firmware_path/system/system/system_ext/apex/com.android.vndk.v31.apex" \
            "$FW_DIR/$firmware_path/system/system_ext/apex/com.android.vndk.v31.apex" \
            "$FW_DIR/$firmware_path/system/system/apex/com.android.vndk.v31.apex"; do
            if [[ -s "$candidate" ]]; then source_apex="$candidate"; break; fi
        done
        if [[ -z "$source_apex" ]]; then
            ABORT "E675: Missing S10 stock VNDK 31 APEX; refusing Qualcomm substitute"
        fi
        if ! python3 -c 'import sys,zipfile; sys.exit(0 if zipfile.is_zipfile(sys.argv[1]) else 1)' "$source_apex"; then
            ABORT "E676: S10 stock VNDK APEX is corrupt or unsupported"
        fi
        mkdir -p "$SYS_EXT_DIR/apex" || return 1
        cp -a "$source_apex" "$SYS_EXT_DIR/apex/com.android.vndk.v31.apex" || return 1
        SET_METADATA "system_ext" "apex/com.android.vndk.v31.apex" 0 0 644 "u:object_r:system_file:s0" || return 1
        LOG "- Installed Exynos 9820 stock VNDK v31 from matching device firmware"
        return 0
    fi
    case "$TARGET_VNDK_LEVEL" in
        "30")
            ADD_TO_WORK_DIR "a73xqxx" "system_ext" "apex/com.android.vndk.v30.apex" 0 0 644 "u:object_r:system_file:s0"
            ;;
        "31")
            ADD_TO_WORK_DIR "b0qxxx" "system_ext" "apex/com.android.vndk.v31.apex" 0 0 644 "u:object_r:system_file:s0"
            ;;
        "32")
            ADD_TO_WORK_DIR "b4qxxx" "system_ext" "apex/com.android.vndk.v32.apex" 0 0 644 "u:object_r:system_file:s0"
            ;;
        "33")
            ADD_TO_WORK_DIR "dm1qxxx" "system_ext" "apex/com.android.vndk.v33.apex" 0 0 644 "u:object_r:system_file:s0"
            ;;
        "34")
            ADD_TO_WORK_DIR "gta9pxxx" "system_ext" "apex/com.android.vndk.v34.apex" 0 0 644 "u:object_r:system_file:s0"
            ;;
        *)
            ABORT "No APEX blob available for VNDK $TARGET_VNDK_LEVEL"
            ;;
    esac
}
# ]

if $TARGET_OS_BUILD_SYSTEM_EXT_PARTITION; then
    SYS_EXT_DIR="$WORK_DIR/system_ext"
else
    SYS_EXT_DIR="$WORK_DIR/system/system/system_ext"
fi

if [ "$SOURCE_BOARD_API_LEVEL" -gt "34" ] && [ "$TARGET_VNDK_LEVEL" -gt "34" ]; then
    :
elif [ "$SOURCE_BOARD_API_LEVEL" -gt "34" ] && [ "$TARGET_VNDK_LEVEL" -le "34" ]; then
    ADD_TARGET_VNDK_APEX
    LOG "- Patching ${SYS_EXT_DIR//$WORK_DIR/}/etc/vintf/manifest.xml"
    EVAL "sed -i \"\\\$d\" \"$SYS_EXT_DIR/etc/vintf/manifest.xml\""
    {
        echo "    <vendor-ndk>"
        echo "        <version>$TARGET_VNDK_LEVEL</version>"
        echo "    </vendor-ndk>"
        echo "</manifest>"
    } >> "$SYS_EXT_DIR/etc/vintf/manifest.xml"
elif [ "$SOURCE_BOARD_API_LEVEL" -le "34" ] && [ "$TARGET_VNDK_LEVEL" -gt "34" ]; then
    DELETE_FROM_WORK_DIR "system_ext" "apex/com.android.vndk.v$SOURCE_BOARD_API_LEVEL.apex"
    LOG "- Patching ${SYS_EXT_DIR//$WORK_DIR/}/etc/vintf/manifest.xml"
    EVAL "sed -i -e \"/vendor-ndk/d\" -e \"/version>/d\" \"$SYS_EXT_DIR/etc/vintf/manifest.xml\""
elif [ ! -f "$SYS_EXT_DIR/apex/com.android.vndk.v$TARGET_VNDK_LEVEL.apex" ]; then
    DELETE_FROM_WORK_DIR "system_ext" "apex/com.android.vndk.v$SOURCE_BOARD_API_LEVEL.apex"
    ADD_TARGET_VNDK_APEX
    LOG "- Patching ${SYS_EXT_DIR//$WORK_DIR/}/etc/vintf/manifest.xml"
    EVAL "sed -i \"s/version>$SOURCE_BOARD_API_LEVEL/version>$TARGET_VNDK_LEVEL/g\" \"$SYS_EXT_DIR/etc/vintf/manifest.xml\""
fi

unset SYS_EXT_DIR
unset -f ADD_TARGET_VNDK_APEX

unset TARGET_VNDK_LEVEL
