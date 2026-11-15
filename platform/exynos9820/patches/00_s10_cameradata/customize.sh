# SPDX-License-Identifier: GPL-3.0-or-later
# Adapt camera framework capabilities using the matching S10 stock firmware.
# The camera HAL must still be ported and validated separately.
TARGET_FIRMWARE_PATH="$(cut -d "/" -f 1 -s <<< "$TARGET_FIRMWARE")_$(cut -d "/" -f 2 -s <<< "$TARGET_FIRMWARE")"
CAMERA_FEATURE="$FW_DIR/$TARGET_FIRMWARE_PATH/system/system/cameradata/camera-feature.xml"
if [ ! -s "$CAMERA_FEATURE" ]; then
    LOGE "E661: Missing stock S10 camera-feature.xml for $TARGET_CODENAME"
    return 1
fi
if ! python3 -c 'import sys,xml.etree.ElementTree as ET; ET.parse(sys.argv[1])' "$CAMERA_FEATURE"; then
    LOGE "E662: Invalid XML in S10 camera-feature.xml"
    return 1
fi
ADD_TO_WORK_DIR "$TARGET_FIRMWARE" "system" "system/cameradata/camera-feature.xml" \
    0 0 644 "u:object_r:system_file:s0" || return 1
unset CAMERA_FEATURE TARGET_FIRMWARE_PATH
