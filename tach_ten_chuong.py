#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tiện ích Tiên Tôn Tool: Tách tên truyện, tên chương và nội dung truyện
- Tách dòng đầu dính chùm: [Tên truyện][Tên chương] (VD: Hoàn Mỹ Thế Giới: Ta, Trùm Try HardChương 1: Bạch Nhất Tâm)
- Xuất toàn bộ tên chương ra file riêng: danh_sach_chuong.txt
- Làm sạch file truyện: chỉ giữ lại nội dung truyện thuần túy
"""

import os
import sys
import re

# Thêm đường dẫn mac_tool
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAC_TOOL_DIR = os.path.join(BASE_DIR, "mac_tool")
if MAC_TOOL_DIR not in sys.path:
    sys.path.insert(0, MAC_TOOL_DIR)

from exporter import strip_titles_and_export_catalog

def main():
    if len(sys.argv) < 2:
        print("Cách sử dụng:")
        print("  python tach_ten_chuong.py <duong_dan_thu_muc_truyen> [--ghi-de]")
        print("Ví dụ:")
        print("  python tach_ten_chuong.py ./truyen_raw")
        print("  python tach_ten_chuong.py ./truyen_raw --ghi-de")
        return

    folder = sys.argv[1]
    in_place = "--ghi-de" in sys.argv or "--inplace" in sys.argv

    if not os.path.isdir(folder):
        print(f"❌ Thư mục không tồn tại: {folder}")
        return

    print(f"⚡ Đang xử lý thư mục: {folder}")
    res = strip_titles_and_export_catalog(folder, in_place=in_place)

    if res.get("success"):
        print("\n" + "="*50)
        print("🎉 XỬ LÝ THÀNH CÔNG!")
        if res.get("detected_novel_title"):
            print(f"📖 Tên truyện nhận diện: {res['detected_novel_title']}")
        print(f"📑 Tổng số chương đã tách: {res['total_chapters']}")
        print(f"📂 Thư mục chứa nội dung thuần: {res['target_folder']}")
        print(f"📄 File danh sách tên chương: {res['catalog_file']}")
        print("="*50)
    else:
        print("❌ Lỗi:", res.get("error"))

if __name__ == "__main__":
    main()
