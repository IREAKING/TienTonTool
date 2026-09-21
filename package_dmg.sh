#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "⚡ Đang đóng gói bộ cài đặt DMG cho Tiên Tôn Tool..."
DMG_TEMP="$DIR/build_dmg"
DMG_NAME="TienTonTool-macOS.dmg"

rm -rf "$DMG_TEMP" "$DMG_NAME"
mkdir -p "$DMG_TEMP"

# Copy App bundle
cp -R TienTonTool.app "$DMG_TEMP/"

# Tạo shortcut kéo thả vào Applications
ln -s /Applications "$DMG_TEMP/Applications"

# Đóng gói bằng hdiutil chuẩn macOS
hdiutil create -volname "Tiên Tôn Tool" -srcfolder "$DMG_TEMP" -ov -format UDZO "$DMG_NAME"

rm -rf "$DMG_TEMP"
echo "🎉 Đã xuất thành công bộ cài: $DMG_NAME"
ls -lh "$DMG_NAME"
