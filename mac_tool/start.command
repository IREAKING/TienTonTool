#!/bin/bash
# Script khởi chạy Tool Dịch Truyện trên macOS

# Chuyển về thư mục chứa file script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "    🚀 ĐANG KHỞI CHẠY TOOL DỊCH TRUYỆN CHO MACOS"
echo "=========================================================="
echo ""

PYTHON_BIN="/usr/local/Caskroom/miniconda/base/envs/dichtruyen/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "⚠️ Không tìm thấy Python trong môi trường conda 'dichtruyen'."
    echo "Thử sử dụng python3 hệ thống..."
    PYTHON_BIN="python3"
fi

echo "Đang mở giao diện trên trình duyệt (http://127.0.0.1:7860)..."
"$PYTHON_BIN" app.py
