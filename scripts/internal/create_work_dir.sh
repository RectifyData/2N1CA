#!/usr/bin/env bash
# Copyright (c) 2025 Salvo Giangreco
# SPDX-License-Identifier: GPL-3.0-or-later

# [
source "$SRC_DIR/scripts/utils/build_utils.sh" || exit 1

# shellcheck source=scripts/lib/s10_model_allowed.sh
source "$SRC_DIR/scripts/lib/s10_model_allowed.sh" || exit 1

SOURCE_FIRMWARE_PATH="$(cut -d "/" -f 1 -s <<< "$SOURCE_FIRMWARE")_$(cut -d "/" -f 2 -s <<< "$SOURCE_FIRMWARE")"
TARGET_FIRMWARE_PATH="$(cut -d "/" -f 1 -s <<< "$TARGET_FIRMWARE")_$(cut -d "/" -f 2 -s <<< "$TARGET_FIRMWARE")"

COPY_SOURCE_FIRMWARE()
{
    local SOURCE_FOLDERS="product system"
    for f in $SOURCE_FOLDERS; do
        if [ -d "$FW_DIR/$SOURCE_FIRMWARE_PATH/$f" ]; then
            LOG "- Copying /$f from source firmware"
            EVAL "rsync -a --mkpath --delete --exclude=\"*system_ext*\" \"$FW_DIR/$SOURCE_FIRMWARE_PATH/$f\" \"$WORK_DIR\"" || exit 1
            sed "/system_ext/d" "$FW_DIR/$SOURCE_FIRMWARE_PATH/file_context-$f" > "$WORK_DIR/configs/file_context-$f"
            sed "/system_ext/d" "$FW_DIR/$SOURCE_FIRMWARE_PATH/fs_config-$f" > "$WORK_DIR/configs/fs_config-$f"
            if [[ "$f" == "product" ]]; then
                LOG_STEP_IN
                SET_PROP "product" "ro.product.product.name" "$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/product/etc/build.prop" "ro.product.product.name")" || return 1
                if [[ "${TARGET_PLATFORM:-}" == "exynos9820" ]]; then
                    # /product must not keep the S25 FE donor identity.
                    local S10_PRODUCT_DEVICE S10_PRODUCT_MODEL
                    S10_PRODUCT_DEVICE="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/vendor/build.prop" "ro.product.vendor.device")"
                    S10_PRODUCT_MODEL="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/product/etc/build.prop" "ro.product.product.model")"
                    [[ -n "$S10_PRODUCT_MODEL" ]] ||
                        S10_PRODUCT_MODEL="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/vendor/build.prop" "ro.product.vendor.model")"
                    [[ "$S10_PRODUCT_DEVICE" == "$TARGET_CODENAME" ||
                       "$S10_PRODUCT_DEVICE" == "${TARGET_CODENAME%lte}" ]] || {
                        LOGE "E663: Stock vendor identity inconsistent with S10 product"
                        return 1
                    }
                    S10_MODEL_ALLOWED "$S10_PRODUCT_MODEL" || {
                        LOGE "E664: Stock /product model not in target S10 model allowlist"
                        return 1
                    }
                    SET_PROP "product" "ro.product.product.model" "$S10_PRODUCT_MODEL" || return 1
                    SET_PROP "product" "ro.product.product.device" "$TARGET_CODENAME" || return 1
                fi
                LOG_STEP_OUT
            elif [[ "$f" == "system" ]]; then
                LOG_STEP_IN
                if [[ "${TARGET_PLATFORM:-}" == "exynos9820" ]]; then
                    # Do not stamp Galaxy S22 donor identity into S10 framework properties.
                    # Cross-check the actual stock vendor device before setting S10 identity.
                    local STOCK_DEVICE STOCK_MODEL
                    STOCK_DEVICE="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/vendor/build.prop" "ro.product.vendor.device")"
                    # Samsung stock vendor builds may use beyond0/1/2 aliases.
                    local STOCK_ALIAS="${TARGET_CODENAME%lte}"
                    if [[ "$STOCK_DEVICE" != "$TARGET_CODENAME" && "$STOCK_DEVICE" != "$STOCK_ALIAS" ]]; then
                        LOGE "E660: target stock vendor identifies as '$STOCK_DEVICE', expected '$TARGET_CODENAME'"
                        return 1
                    fi
                    STOCK_MODEL="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/vendor/build.prop" "ro.product.vendor.model")"
                    if [ -z "$STOCK_MODEL" ]; then
                        STOCK_MODEL="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/product/etc/build.prop" "ro.product.product.model")"
                    fi
                    if [ -z "$STOCK_MODEL" ]; then
                        STOCK_MODEL="$(GET_PROP "$FW_DIR/$TARGET_FIRMWARE_PATH/system/system/build.prop" "ro.product.model")"
                    fi
                    # Empty properties must never leave the One UI donor's S25
                    # model baked into the S10 framework image.
                    if ! S10_MODEL_ALLOWED "$STOCK_MODEL"; then
                        LOGE "E661: S10 stock model is missing or not on the target model allowlist"
                        return 1
                    fi
                    SET_PROP "system" "ro.product.device" "$TARGET_CODENAME" || return 1
                    SET_PROP "system" "ro.product.system.device" "$TARGET_CODENAME" || return 1
                    SET_PROP "system" "ro.product.model" "$STOCK_MODEL" || return 1
                    SET_PROP "system" "ro.product.system.model" "$STOCK_MODEL" || return 1
                else
                    SET_PROP "system" "ro.product.device" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/odm/etc/build.prop" "ro.product.odm.device")"
                fi
                LOG_STEP_OUT
            fi
        else
            [ -d "$WORK_DIR/$f" ] && rm -rf "${WORK_DIR:?}/$f"
            [ -f "$WORK_DIR/configs/file_context-$f" ] && rm -f "$WORK_DIR/configs/file_context-$f"
            [ -f "$WORK_DIR/configs/fs_config-$f" ] && rm -f "$WORK_DIR/configs/fs_config-$f"
        fi
    done

    if [ -d "$FW_DIR/$SOURCE_FIRMWARE_PATH/system_ext" ]; then
        if $TARGET_OS_BUILD_SYSTEM_EXT_PARTITION; then
            LOG_STEP_IN "- Copying /system_ext from source firmware"

            [ -L "$WORK_DIR/system/system_ext" ] && rm -f "$WORK_DIR/system/system_ext"
            [ -d "$WORK_DIR/system/system/system_ext" ] && rm -rf "$WORK_DIR/system/system/system_ext"

            EVAL "rsync -a --mkpath --delete \"$FW_DIR/$SOURCE_FIRMWARE_PATH/system_ext\" \"$WORK_DIR\"" || exit 1
            mkdir -p "$WORK_DIR/system/system_ext"
            EVAL "ln -sf \"/system_ext\" \"$WORK_DIR/system/system/system_ext\"" || exit 1
            SET_METADATA "system" "system_ext" 0 0 755 "u:object_r:system_file:s0"
            SET_METADATA "system" "system/system_ext" 0 0 644 "u:object_r:system_file:s0"
            EVAL "cp -a \"$FW_DIR/$SOURCE_FIRMWARE_PATH/file_context-system_ext\" \"$WORK_DIR/configs/file_context-system_ext\"" || exit 1
            EVAL "cp -a \"$FW_DIR/$SOURCE_FIRMWARE_PATH/fs_config-system_ext\" \"$WORK_DIR/configs/fs_config-system_ext\"" || exit 1

            LOG_STEP_OUT
        else
            LOG_STEP_IN "- Copying /system/system/system_ext from source firmware"

            [ -d "$WORK_DIR/system/system_ext" ] && rm -rf "$WORK_DIR/system/system_ext"
            [ -L "$WORK_DIR/system/system/system_ext" ] && rm -f "$WORK_DIR/system/system/system_ext"
            [ -d "$WORK_DIR/system_ext" ] && rm -rf "$WORK_DIR/system_ext"
            [ -f "$WORK_DIR/configs/file_context-system_ext" ] && rm -f "$WORK_DIR/configs/file_context-system_ext"
            [ -f "$WORK_DIR/configs/fs_config-system_ext" ] && rm -f "$WORK_DIR/configs/fs_config-system_ext"

            EVAL "rsync -a --mkpath --delete \"$FW_DIR/$SOURCE_FIRMWARE_PATH/system_ext\" \"$WORK_DIR/system/system\"" || exit 1
            EVAL "ln -sf \"/system/system_ext\" \"$WORK_DIR/system/system_ext\"" || exit 1
            SET_METADATA "system" "system_ext" 0 0 644 "u:object_r:system_file:s0"
            sed "s/^\/system_ext/\/system\/system_ext/g" "$FW_DIR/$SOURCE_FIRMWARE_PATH/file_context-system_ext" >> "$WORK_DIR/configs/file_context-system"
            sed "s/^system_ext/system\/system_ext/g" "$FW_DIR/$SOURCE_FIRMWARE_PATH/fs_config-system_ext" >> "$WORK_DIR/configs/fs_config-system"

            ADD_TO_WORK_DIR "b0sxxx" "system_ext" "etc/build_flags.json" 0 0 644 "u:object_r:system_file:s0" || exit 1
            DELETE_FROM_WORK_DIR "system" "system/system_ext/etc/NOTICE.xml.gz"

            LOG_STEP_OUT
        fi
    elif [ -d "$FW_DIR/$SOURCE_FIRMWARE_PATH/system/system/system_ext" ]; then
        if $TARGET_OS_BUILD_SYSTEM_EXT_PARTITION; then
            LOG_STEP_IN "- Copying /system_ext from source firmware"

            [ -L "$WORK_DIR/system/system_ext" ] && rm -f "$WORK_DIR/system/system_ext"
            [ -d "$WORK_DIR/system/system/system_ext" ] && rm -rf "$WORK_DIR/system/system/system_ext"

            EVAL "rsync -a --mkpath --delete \"$FW_DIR/$SOURCE_FIRMWARE_PATH/system/system/system_ext\" \"$WORK_DIR\"" || exit 1
            mkdir -p "$WORK_DIR/system/system_ext"
            EVAL "ln -sf \"/system_ext\" \"$WORK_DIR/system/system/system_ext\"" || exit 1
            SET_METADATA "system" "system_ext" 0 0 755 "u:object_r:system_file:s0"
            SET_METADATA "system" "system/system_ext" 0 0 644 "u:object_r:system_file:s0"
            grep -F "system/system_ext" "$FW_DIR/$SOURCE_FIRMWARE_PATH/file_context-system" | sed "s/^\/system//" > "$WORK_DIR/configs/file_context-system_ext"
            grep -F "system/system_ext" "$FW_DIR/$SOURCE_FIRMWARE_PATH/fs_config-system" | sed "s/^system\///" > "$WORK_DIR/configs/fs_config-system_ext"
            sed -i "s/^system_ext /  /g" "$WORK_DIR/configs/fs_config-system_ext"

            ADD_TO_WORK_DIR "b0qxxx" "system_ext" "etc/build_flags.json" 0 0 644 "u:object_r:system_file:s0" || exit 1
            ADD_TO_WORK_DIR "b0qxxx" "system_ext" "etc/NOTICE.xml.gz" 0 0 644 "u:object_r:system_file:s0" || exit 1

            LOG_STEP_OUT
        else
            LOG_STEP_IN "- Copying /system/system/system_ext from source firmware"

            [ -d "$WORK_DIR/system/system_ext" ] && rm -rf "$WORK_DIR/system/system_ext"
            [ -L "$WORK_DIR/system/system/system_ext" ] && rm -f "$WORK_DIR/system/system/system_ext"
            [ -d "$WORK_DIR/system_ext" ] && rm -rf "$WORK_DIR/system_ext"
            [ -f "$WORK_DIR/configs/file_context-system_ext" ] && rm -f "$WORK_DIR/configs/file_context-system_ext"
            [ -f "$WORK_DIR/configs/fs_config-system_ext" ] && rm -f "$WORK_DIR/configs/fs_config-system_ext"

            EVAL "rsync -a --mkpath --delete \"$FW_DIR/$SOURCE_FIRMWARE_PATH/system/system/system_ext\" \"$WORK_DIR/system/system\"" || exit 1
            EVAL "ln -sf \"/system/system_ext\" \"$WORK_DIR/system/system_ext\"" || exit 1
            grep -F "system_ext" "$FW_DIR/$SOURCE_FIRMWARE_PATH/file_context-system" >> "$WORK_DIR/configs/file_context-system"
            grep -F "system_ext" "$FW_DIR/$SOURCE_FIRMWARE_PATH/fs_config-system" >> "$WORK_DIR/configs/fs_config-system"

            LOG_STEP_OUT
        fi
    fi
}

COPY_TARGET_FIRMWARE()
{
    local TARGET_FOLDERS="odm odm_dlkm system_dlkm vendor vendor_dlkm"
    for f in $TARGET_FOLDERS; do
        if [ -d "$FW_DIR/$TARGET_FIRMWARE_PATH/$f" ]; then
            LOG "- Copying /$f from target firmware"
            EVAL "rsync -a --mkpath --delete \"$FW_DIR/$TARGET_FIRMWARE_PATH/$f\" \"$WORK_DIR\"" || exit 1
            EVAL "cp -a \"$FW_DIR/$TARGET_FIRMWARE_PATH/file_context-$f\" \"$WORK_DIR/configs/file_context-$f\"" || exit 1
            EVAL "cp -a \"$FW_DIR/$TARGET_FIRMWARE_PATH/fs_config-$f\" \"$WORK_DIR/configs/fs_config-$f\"" || exit 1
            if [[ "$f" == "vendor" ]]; then
                LOG_STEP_IN
                SET_PROP "vendor" "ro.config.ringtone" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/vendor/build.prop" "ro.config.ringtone")"
                SET_PROP "vendor" "ro.config.notification_sound" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/vendor/build.prop" "ro.config.notification_sound")"
                SET_PROP "vendor" "ro.config.alarm_alert" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/vendor/build.prop" "ro.config.alarm_alert")"
                SET_PROP "vendor" "ro.config.media_sound" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/vendor/build.prop" "ro.config.media_sound")"
                SET_PROP "vendor" "ro.config.ringtone_2" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/vendor/build.prop" "ro.config.ringtone_2")"
                SET_PROP "vendor" "ro.config.notification_sound_2" "$(GET_PROP "$FW_DIR/$SOURCE_FIRMWARE_PATH/vendor/build.prop" "ro.config.notification_sound_2")"
                LOG_STEP_OUT
            fi
        else
            [ -d "$WORK_DIR/$f" ] && rm -rf "${WORK_DIR:?}/$f"
            [ -f "$WORK_DIR/configs/file_context-$f" ] && rm -f "$WORK_DIR/configs/file_context-$f"
            [ -f "$WORK_DIR/configs/fs_config-$f" ] && rm -f "$WORK_DIR/configs/fs_config-$f"
        fi
    done
}

COPY_TARGET_KERNEL()
{
    if [ -d "$FW_DIR/$TARGET_FIRMWARE_PATH/kernel" ]; then
        LOG_STEP_IN "- Copying target firmware kernel images"
        EVAL "rsync -a --mkpath --delete \"$FW_DIR/$TARGET_FIRMWARE_PATH/kernel\" \"$WORK_DIR\"" || exit 1
        $TARGET_KEEP_ORIGINAL_SIGN || find "$WORK_DIR/kernel" -mindepth 1 -exec "$SRC_DIR/scripts/unsign_bin.sh" {} \;
        LOG_STEP_OUT
    else
        [ -d "$WORK_DIR/kernel" ] && rm -rf "$WORK_DIR/kernel"
    fi
}
# ]

mkdir -p "$WORK_DIR"
mkdir -p "$WORK_DIR/configs"
COPY_SOURCE_FIRMWARE
COPY_TARGET_FIRMWARE
COPY_TARGET_KERNEL

exit 0
