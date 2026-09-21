#!/bin/bash
# ==========================================================
# Script khởi chạy Tiên Tôn Tool trên macOS
# ==========================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Khởi chạy Python AI Bridge nếu chưa hoạt động
if ! curl -s http://127.0.0.1:58231/health >/dev/null 2>&1; then
    PYTHON_BIN="/usr/local/Caskroom/miniconda/base/envs/dichtruyen/bin/python"
    if [ ! -f "$PYTHON_BIN" ]; then
        PYTHON_BIN="python3"
    fi
    nohup "$PYTHON_BIN" "$DIR/mac_tool/bridge.py" >/dev/null 2>&1 &
fi

open "$DIR/TienTonTool.app"
