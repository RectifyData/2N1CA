#!/usr/bin/env bash
# Copyright (c) 2023 Salvo Giangreco
# SPDX-License-Identifier: GPL-3.0-or-later

# [
source "$SRC_DIR/scripts/utils/install_utils.sh" || exit 1

TMP_DIR="$OUT_DIR/target/$TARGET_CODENAME/zip"

PRIVATE_KEY_PATH="$SRC_DIR/security/"
PUBLIC_KEY_PATH="$SRC_DIR/security/"
if $ROM_IS_OFFICIAL; then
    PRIVATE_KEY_PATH+="unica_ota"
    PUBLIC_KEY_PATH+="unica_ota"
else
    PRIVATE_KEY_PATH+="aosp_testkey"
    PUBLIC_KEY_PATH+="aosp_testkey"
fi
PRIVATE_KEY_PATH+=".pk8"
PUBLIC_KEY_PATH+=".x509.pem"

trap 'rm -rf "$TMP_DIR"' EXIT INT

# https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/common.py#4042
GENERATE_OP_LIST()
{
    local OP_LIST_FILE="$TMP_DIR/dynamic_partitions_op_list"

    local SUPER_GROUP_NAME
    local SUPER_GROUP_SIZE

    SUPER_GROUP_NAME="$(grep "^super_partition_group" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    SUPER_GROUP_SIZE="$(grep "^super_${SUPER_GROUP_NAME}_group_size" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"

    local PARTITION_SIZE=0
    local OCCUPIED_SPACE=0

    {
        echo "# Remove all existing dynamic partitions and groups before applying full OTA"
        echo "remove_all_groups"
        echo "# Add group $SUPER_GROUP_NAME with maximum size $SUPER_GROUP_SIZE"
        echo "add_group $SUPER_GROUP_NAME $SUPER_GROUP_SIZE"
        for p in $PARTITIONS_LIST; do
            if [ -f "$TMP_DIR/$p.img" ]; then
                echo "# Add partition $p to group $SUPER_GROUP_NAME"
                echo "add $p $SUPER_GROUP_NAME"
            fi
        done
        for p in $PARTITIONS_LIST; do
            if [ -f "$TMP_DIR/$p.img" ]; then
                PARTITION_SIZE="$(GET_IMAGE_SIZE "$TMP_DIR/$p.img")"
                echo "# Grow partition $p from 0 to $PARTITION_SIZE"
                echo "resize $p $PARTITION_SIZE"
                OCCUPIED_SPACE=$((OCCUPIED_SPACE + PARTITION_SIZE))
            fi
        done
    } > "$OP_LIST_FILE"

    if [ "$OCCUPIED_SPACE" -gt "$SUPER_GROUP_SIZE" ]; then
        LOGE "OS size ($OCCUPIED_SPACE) is bigger than the target group size ($SUPER_GROUP_SIZE)"
        exit 1
    fi
}

GENERATE_OTA_METADATA()
{
    local PROTO_FILE="$SRC_DIR/external/android-tools/vendor/build/tools/releasetools/ota_metadata.proto"

    local DEVICE
    local SDK_LEVEL
    local INCREMENTAL
    local TIMESTAMP
    local SECURITY_PATCH_LEVEL
    local FINGERPRINT

    DEVICE="$(grep "^device" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    SDK_LEVEL="$(grep "^sdk_level" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    INCREMENTAL="$(grep "^build_incremental" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    TIMESTAMP="$(grep "^build_date" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    SECURITY_PATCH_LEVEL="$(grep "^security_patch" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    FINGERPRINT="$(grep "^target_fingerprint" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
    if [[ ! "$SDK_LEVEL" =~ ^[0-9]+$ || -z "$FINGERPRINT" ]]; then
        LOGE "E551: Invalid final SDK level or missing post-build fingerprint"
        return 1
    fi

    mkdir -p "$TMP_DIR/META-INF/com/android"

    # https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/ota_utils.py#259
    if [[ "$TARGET_CODENAME" == beyond* && ! -f "$PROTO_FILE" ]]; then
        LOGE "E552: OTA metadata protobuf schema absent from host tools"
        return 1
    fi
    if [ -f "$PROTO_FILE" ]; then
        local MESSAGE

        MESSAGE+="type: BLOCK"
        MESSAGE+=", precondition: {device: \\\"$DEVICE\\\"}"
        MESSAGE+=", postcondition: {device: \\\"$DEVICE\\\""
        MESSAGE+=", build: \\\"$FINGERPRINT\\\""
        MESSAGE+=", build_incremental: \\\"$INCREMENTAL\\\""
        MESSAGE+=", timestamp: $TIMESTAMP"
        MESSAGE+=", sdk_level: \\\"$SDK_LEVEL\\\""
        MESSAGE+=", security_patch_level: \\\"$SECURITY_PATCH_LEVEL\\\"}"

        EVAL "protoc --encode=build.tools.releasetools.OtaMetadata --proto_path=\"$(dirname "$PROTO_FILE")\" \"$PROTO_FILE\" <<< \"$MESSAGE\" > \"$TMP_DIR/META-INF/com/android/metadata.pb\"" || exit 1
    fi

    # https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/ota_utils.py#317
    {
        echo "ota-required-cache=0"
        echo "ota-type=BLOCK"
        echo "post-build=$FINGERPRINT"
        echo "post-build-incremental=$INCREMENTAL"
        echo "post-sdk-level=$SDK_LEVEL"
        echo "post-security-patch-level=$SECURITY_PATCH_LEVEL"
        echo "post-timestamp=$TIMESTAMP"
        echo "pre-device=$DEVICE"
    } > "$TMP_DIR/META-INF/com/android/metadata"
}

GENERATE_UPDATER_SCRIPT()
{
    local SCRIPT_FILE="$TMP_DIR/META-INF/com/google/android/updater-script"

    local PARTITION_COUNT=0

    [ -f "$TMP_DIR/vendor.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))
    [ -f "$TMP_DIR/product.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))
    [ -f "$TMP_DIR/system_ext.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))
    [ -f "$TMP_DIR/odm.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))
    [ -f "$TMP_DIR/vendor_dlkm.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))
    [ -f "$TMP_DIR/odm_dlkm.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))
    [ -f "$TMP_DIR/system_dlkm.transfer.list" ] && PARTITION_COUNT=$((PARTITION_COUNT + 1))

    {
        PRINT_ASSERTIONS "$BUILD_INFO" || exit 1

        PRINT_HEADER "$BUILD_INFO" || exit 1

        if $TARGET_USE_DYNAMIC_PARTITIONS; then
            # https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/common.py#4007
            echo -e "\n# --- Start patching dynamic partitions ---\n"
            echo -e "\n# Update dynamic partition metadata\n"
            echo -n 'assert(update_dynamic_partitions(package_extract_file("dynamic_partitions_op_list")'
            if [ -f "$TMP_DIR/unsparse_super_empty.img" ]; then
                # https://github.com/LineageOS/android_build/commit/98549f6893c3a93057e2d4cdd1015a93e9473b16
                # https://github.com/LineageOS/android_bootable_deprecated-ota/commit/e97be4333bd3824b8561c9637e9e6de28bc29da0
                echo -n ', package_extract_file("unsparse_super_empty.img")'
            fi
            echo    '));'
        fi
        for p in $PARTITIONS_LIST; do
            if [ ! -f "$TMP_DIR/$p.transfer.list" ]; then
                continue
            fi
            $TARGET_USE_DYNAMIC_PARTITIONS && echo -e "\n# Patch partition $p\n"
            echo -n 'ui_print("Patching '
            echo -n "$p image unconditionally..."
            echo    '");'
            if [[ "$p" == "system" ]]; then
                echo -n 'show_progress(0.'
                echo -n "$(bc -l <<< "9 - $PARTITION_COUNT")"
                echo    '00000, 0);'
            else
                echo    'show_progress(0.100000, 0);'
            fi
            echo -n "block_image_update("
            GET_DEVICE_FROM_MOUNTPOINT "/$p" || {
                printf 'E546: Cannot resolve partition %s in recovery fstab\n' "$p" >&2
                exit 1
            }
            echo -n ', package_extract_file("'
            echo -n "$p.transfer.list"
            echo -n '"), "'
            echo -n "$p.new.dat"
            [ -f "$TMP_DIR/$p.new.dat.br" ] && echo -n ".br"
            echo -n '", "'
            echo -n "$p.patch.dat"
            echo    '") ||'
            echo -n '  abort("'
            [[ "$p" == "system" ]] && echo -n "E1001" || echo -n "E2001"
            echo -n ": Failed to update $p image."
            echo    '");'
        done
        $TARGET_USE_DYNAMIC_PARTITIONS && echo -e "\n# --- End patching dynamic partitions ---\n"

        for b in $KERNEL_BINS; do
            if [ -f "$TMP_DIR/$b.img" ]; then
                echo -n 'ui_print("Full Patching '
                echo -n "$b.img img..."
                echo    '");'
                echo -n 'package_extract_file("'
                echo -n "$b.img"
                echo -n '", '
                GET_DEVICE_FROM_MOUNTPOINT "/$b" || {
                    printf 'E547: Unsupported recovery kernel mount %s\n' "$b" >&2
                    exit 1
                }
                echo    ') || abort("E4002: Failed to write kernel image.");'
            fi
        done
        if [ -f "$TMP_DIR/boot.img" ]; then
            echo    'ui_print("Installing boot image...");'
            echo -n 'package_extract_file("boot.img", '
            GET_DEVICE_FROM_MOUNTPOINT "/boot" || {
                printf 'E548: Recovery fstab lacks a valid boot partition\n' >&2
                exit 1
            }
            echo    ') || abort("E4003: Failed to write boot image.");'
        fi

        echo    'show_progress(0.100000, 10);'

        if [ -f "$SRC_DIR/target/$TARGET_CODENAME/installer/install-end.edify" ]; then
            cat "$SRC_DIR/target/$TARGET_CODENAME/installer/install-end.edify"
        fi

        echo    'set_progress(1.000000);'

        PRINT_SEPARATOR
        echo    'ui_print(" ");'
    } > "$SCRIPT_FILE"
}
# ]

if [ "$#" != "2" ]; then
    echo "Usage: build_full_ota_zip <file> <output>" >&2
    exit 1
fi

TARGET_ZIP="$1"
OUTPUT_FILE="$2"

if ! unzip -p "$TARGET_ZIP" build_info.txt >/dev/null 2>&1; then
    LOGE "File not valid: ${TARGET_ZIP//$SRC_DIR\//}"
    exit 1
fi

[ -d "$TMP_DIR" ] && rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR/META-INF/com/google/android"
cp -a "$SRC_DIR/prebuilts/bootable/deprecated-ota/updater" "$TMP_DIR/META-INF/com/google/android/update-binary"

LOG "- Extracting target files"
EVAL "unzip -o \"$TARGET_ZIP\" -d \"$TMP_DIR\"" || exit 1

BUILD_INFO="$(cat "$TMP_DIR/build_info.txt")"
rm -f "$TMP_DIR/build_info.txt"

TARGET_CODENAME="$(grep "^device" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"
if [ ! -d "$SRC_DIR/target/$TARGET_CODENAME" ]; then
    LOGE "Folder not found: target/$TARGET_CODENAME"
    exit 1
fi

TARGET_USE_DYNAMIC_PARTITIONS="$(grep "^use_dynamic_partitions" <<< "$BUILD_INFO" | cut -d "=" -f 2 -s)"

# Legacy S10 devices must not use the dynamic-partition updater from newer models.
case "$TARGET_CODENAME" in
    beyond0lte|beyond1lte|beyond2lte|beyondx)
        if [[ "$TARGET_USE_DYNAMIC_PARTITIONS" != "false" ]]; then
            LOGE "S10 legacy ZIP requested dynamic partitions; refusing to package"
            exit 1
        fi
        [[ -s "$TMP_DIR/boot.img" ]] || {
            LOGE "E632: S10 flashable package requires an approved boot.img"
            exit 1
        }
        # Prevent the updater from looking up /dt, /dtbo, /vendor_boot or
        # /init_boot partitions that are not present in the verified S10 fstab.
        # The required S10 kernel packaging must be designed and verified separately.
        for image in dt.img dtbo.img init_boot.img vendor_boot.img; do
            if [ -f "$TMP_DIR/$image" ]; then
                LOGE "E526: Unsafe S10 kernel payload: $image has no validated partition mapping"
                exit 1
            fi
        done
        ;;
esac

if $TARGET_USE_DYNAMIC_PARTITIONS; then
    LOG "- Generating dynamic_partitions_op_list"
    GENERATE_OP_LIST
fi

for p in $PARTITIONS_LIST; do
    if [ ! -f "$TMP_DIR/$p.img" ]; then
        continue
    fi

    LOG "- Converting $p.img to $p.new.dat"
    EVAL "img2sdat -o \"$TMP_DIR\" --tgt-block-map \"$TMP_DIR/$p.map\" \"$TMP_DIR/$p.img\"" || exit 1
    rm -f "$TMP_DIR/$p.img" "$TMP_DIR/$p.map"
    # Full block OTAs can have an empty patch file; edify still references it.
    # Include the empty payload explicitly instead of an Error 1 at install time.
    [ -f "$TMP_DIR/$p.patch.dat" ] || : > "$TMP_DIR/$p.patch.dat"

    if ! $DEBUG; then
        LOG "- Compressing $p.new.dat"
        # https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/common.py#3585
        EVAL "brotli --quality=6 --output=\"$TMP_DIR/$p.new.dat.br\" \"$TMP_DIR/$p.new.dat\"" || exit 1
        # A ZIP CRC validates only the container, not the Brotli stream.
        # Check Brotli's internal integrity before removing the raw data.
        if ! brotli --test "$TMP_DIR/$p.new.dat.br"; then
            LOGE "E527: $p.new.dat.br failed Brotli integrity check"
            exit 1
        fi
        rm -f "$TMP_DIR/$p.new.dat"
    fi
done

LOG "- Generating updater-script"
GENERATE_UPDATER_SCRIPT

LOG "- Generating build_info.txt"
PRINT_BUILD_INFO "$BUILD_INFO" > "$TMP_DIR/build_info.txt" || exit 1

LOG "- Generating OTA metadata"
GENERATE_OTA_METADATA || exit 1

if [ -d "$SRC_DIR/target/$TARGET_CODENAME/installer/root" ]; then
    LOG "- Copying target custom install files"
    EVAL "cp -a \"$SRC_DIR/target/$TARGET_CODENAME/installer/root/\"* \"$TMP_DIR\"" || exit 1
fi

if [ -f "$SRC_DIR/target/$TARGET_CODENAME/installer/customize.sh" ]; then
    LOG_STEP_IN "- Running target custom install script"
    (
    . "$SRC_DIR/target/$TARGET_CODENAME/installer/customize.sh"
    ) || exit 1
    LOG_STEP_OUT
fi

LOG "- Creating zip"
EVAL "rm -f \"$TMP_DIR/rom.zip\"" || exit 1
# https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/common.py#3601
# https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/common.py#3609
# https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/ota_utils.py#184
# https://android.googlesource.com/platform/build/+/refs/tags/android-15.0.0_r1/tools/releasetools/ota_utils.py#186
EVAL "cd \"$TMP_DIR\" && 7z a -tzip -mx=0 -mmt=$(nproc) $TMP_DIR/rom.zip -r *.patch.dat -ir!META-INF/com/android/* -i!*.new.dat.br" || exit 1
EVAL "cd \"$TMP_DIR\" && 7z a -tzip -mx=3 -mmt=$(nproc) $TMP_DIR/rom.zip -r * -xr!META-INF/com/android/* -x!*.new.dat.br -x!*.patch.dat -x!rom.zip" || exit 1

if ! $DEBUG || $ROM_IS_OFFICIAL; then
    LOG "- Signing zip"
    EVAL "signapk -w \"$PUBLIC_KEY_PATH\" \"$PRIVATE_KEY_PATH\" \"$TMP_DIR/rom.zip\" \"$OUTPUT_FILE\"" || exit 1
    rm -f "$TMP_DIR/rom.zip"
else
    mv -f "$TMP_DIR/rom.zip" "$OUTPUT_FILE"
fi


# Validate ZIP references and integrity before reporting packaging success.
case "$TARGET_CODENAME" in
    beyond0lte|beyond1lte|beyond2lte|beyondx)
        if ! python3 "$SRC_DIR/scripts/internal/validate_flashable_zip.py" \
            "$OUTPUT_FILE" --expected-device "$TARGET_CODENAME" \
            --layout "$OUT_DIR/target/$TARGET_CODENAME/pit-layout.env" --deep; then
            LOGE "Produced ZIP failed S10 installer validation; refusing to publish"
            rm -f "$OUTPUT_FILE"
            exit 1
        fi
        ;;
esac

exit 0
