#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tiên Tôn Tool: Công cụ chuyển đổi truyện Convert sang Truyện Dịch
Tác giả: Antigravity - Tiên Tôn Tool Team
Mục đích:
- Khử sạch 100% các dị tật convert (ngữ pháp ngược, lượng từ tiếng Trung, cụm từ thô lậu, ...)
- Chuẩn hóa đại từ, nhân xưng, dấu câu, danh từ riêng
- Hỗ trợ 3 chế độ:
  1. Rules (Siêu tốc, 100% Offline, 0s, 0 token - xử lý 400 chương trong vài giây)
  2. AI (DeepSeek / Gemini API - văn phong văn học xuất sắc)
  3. Hybrid (Quy tắc lọc thô + AI trau chuốt)
"""

import os
import sys
import re
import time
import argparse
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# Thêm đường dẫn mac_tool vào hệ thống
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAC_TOOL_DIR = os.path.join(BASE_DIR, "mac_tool")
if MAC_TOOL_DIR not in sys.path:
    sys.path.insert(0, MAC_TOOL_DIR)

from convert_polisher import convert_polisher, ConvertRulesEngine

def natural_sort_key(s):
    """Sắp xếp tự nhiên (1, 2, 10 thay vì 1, 10, 2)"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def print_banner():
    print("=" * 65)
    print("✨  TIÊN TÔN TOOL - CHUYỂN TRUYỆN CONVERT SANG TRUYỆN DỊCH  ✨")
    print("=" * 65)

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=40, fill='█'):
    """Vẽ thanh tiến trình trực quan trong Terminal"""
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration >= total:
        sys.stdout.write('\n')

def read_file_safe(file_path: str) -> str:
    for enc in ["utf-8", "utf-8-sig", "gb18030", "utf-16", "cp1258", "latin1"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def process_single_file(file_path: str, out_path: str, mode: str = "rules", engine: str = "gemini", genre: str = "xianxia", api_key: str = None):
    content = read_file_safe(file_path)
    if not content.strip():
        return 0, 0

    word_count_in = len(content.split())
    translated = convert_polisher.polish(
        text=content,
        mode=mode,
        engine=engine,
        genre=genre,
        api_key=api_key
    )
    word_count_out = len(translated.split())

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(translated)

    return word_count_in, word_count_out

def main():
    parser = argparse.ArgumentParser(
        description="Tiên Tôn Tool: Chuyển truyện Convert sang Truyện Dịch mượt mà, tự nhiên"
    )
    parser.add_argument("input", nargs="?", help="Đường dẫn thư mục hoặc file truyện convert cần xử lý")
    parser.add_argument("--file", "-f", help="Xử lý 1 file truyện cụ thể")
    parser.add_argument("--out", "-o", help="Thư mục xuất kết quả truyện dịch (mặc định: <input>_dich)")
    parser.add_argument("--mode", "-m", choices=["rules", "ai", "hybrid"], default="rules",
                        help="Chế độ xử lý: rules (siêu tốc offline), ai (dùng LLM), hybrid (kết hợp). Mặc định: rules")
    parser.add_argument("--engine", "-e", choices=["gemini", "deepseek"], default="gemini",
                        help="Mô hình AI khi dùng mode ai/hybrid (gemini / deepseek). Mặc định: gemini")
    parser.add_argument("--api-key", "-k", help="API Key của Gemini hoặc DeepSeek (có thể dùng biến môi trường GEMINI_API_KEY hoặc config.json)")
    parser.add_argument("--genre", "-g", choices=["xianxia", "fantasy", "urban", "romance"], default="xianxia",
                        help="Thể loại truyện (xianxia: Tiên hiệp, fantasy: Huyền huyễn, urban: Đô thị, romance: Ngôn tình)")
    parser.add_argument("--workers", "-w", type=int, default=8, help="Số luồng xử lý đồng thời (mặc định: 8)")
    parser.add_argument("--ghi-de", action="store_true", help="Ghi đè trực tiếp lên file gốc thay vì tạo thư mục mới")
    parser.add_argument("--sample", "-s", action="store_true", help="In đoạn trích mẫu so sánh Trước và Sau khi dịch")

    args = parser.parse_args()

    print_banner()

    target_path = args.file or args.input
    if not target_path:
        parser.print_help()
        print("\nVí dụ sử dụng:")
        print("  python chuyen_convert_sang_dich.py /Users/macbook-pro/Downloads/tryhard")
        print("  python chuyen_convert_sang_dich.py /Users/macbook-pro/Downloads/tryhard --out ./tryhard_dich")
        print("  python chuyen_convert_sang_dich.py /Users/macbook-pro/Downloads/tryhard --sample")
        print("  python chuyen_convert_sang_dich.py --file /Users/macbook-pro/Downloads/tryhard/0001_xxx.txt")
        return

    target_path = os.path.abspath(target_path)
    if not os.path.exists(target_path):
        print(f"❌ Đường dẫn không tồn tại: {target_path}")
        return

    # XỬ LÝ 1 FILE ĐƠN LẺ
    if os.path.isfile(target_path):
        fname = os.path.basename(target_path)
        out_path = target_path if args.ghi_de else (args.out or target_path.replace(".txt", "_dich_chuan.txt"))
        print(f"📄 Xử lý file: {fname}")
        print(f"⚙️  Chế độ: {args.mode.upper()} | Thể loại: {args.genre}")
        t0 = time.time()
        win, wout = process_single_file(target_path, out_path, mode=args.mode, engine=args.engine, genre=args.genre, api_key=args.api_key)
        t1 = time.time()
        print(f"✅ Hoàn thành trong {t1 - t0:.2f}s ({win} từ -> {wout} từ)")
        print(f"📂 Đã lưu tại: {out_path}")

        if args.sample:
            content_in = read_file_safe(target_path)[:400]
            content_out = read_file_safe(out_path)[:400]
            print("\n" + "-"*30 + " SO SÁNH TRƯỚC VÀ SAU " + "-"*30)
            print("【 BẢN GỐC CONVERT 】:\n" + content_in)
            print("\n【 TRUYỆN DỊCH SAU KHI POLISH 】:\n" + content_out)
            print("-" * 75)
        return

    # XỬ LÝ TOÀN BỘ THƯ MỤC
    input_folder = target_path
    if args.ghi_de:
        output_folder = input_folder
    else:
        output_folder = args.out or (input_folder.rstrip("/\\") + "_dich")
    os.makedirs(output_folder, exist_ok=True)

    files = [f for f in os.listdir(input_folder) if f.endswith(".txt") and not f.startswith(".")]
    files.sort(key=natural_sort_key)

    catalog_file = None
    if "danh_sach_chuong.txt" in files:
        catalog_file = "danh_sach_chuong.txt"
        files.remove("danh_sach_chuong.txt")

    total_files = len(files)
    if total_files == 0:
        print(f"⚠️ Không tìm thấy file .txt nào trong thư mục: {input_folder}")
        return

    print(f"📂 Thư mục nguồn: {input_folder}")
    print(f"📁 Thư mục xuất : {output_folder}")
    print(f"📑 Tổng số chương cần xử lý: {total_files}")
    print(f"⚡ Chế độ: {args.mode.upper()} | Luồng: {args.workers} worker(s)")
    print("-" * 65)

    # In mẫu thử trước nếu có yêu cầu --sample
    if args.sample and total_files > 0:
        sample_path = os.path.join(input_folder, files[0])
        raw_text = read_file_safe(sample_path)
        sample_res = convert_polisher.polish(raw_text[:600], mode=args.mode, engine=args.engine, genre=args.genre)
        print("🔍 MẪU THỬ TRƯỚC (CHƯƠNG 1):")
        print(f"--- [CONVERT THÔ] ---\n{raw_text[:350]}...\n")
        print(f"--- [TRUYỆN DỊCH ĐÃ BIÊN TẬP] ---\n{sample_res[:350]}...\n")
        print("-" * 65)

    start_time = time.time()
    total_words = 0
    completed_count = 0

    print_progress_bar(0, total_files, prefix='Tiến độ:', suffix=f'0/{total_files}', length=35)

    # Nếu mode rules và nhiều file, dùng ThreadPoolExecutor để xử lý đa luồng siêu tốc
    if args.mode == "rules":
        def worker(fname):
            in_file = os.path.join(input_folder, fname)
            out_file = os.path.join(output_folder, fname)
            try:
                win, wout = process_single_file(in_file, out_file, mode="rules", genre=args.genre)
                return True, wout, fname, None
            except Exception as e:
                return False, 0, fname, str(e)

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(worker, f) for f in files]
            for future in as_completed(futures):
                success, words, fname, err = future.result()
                completed_count += 1
                if success:
                    total_words += words
                print_progress_bar(
                    completed_count, total_files,
                    prefix='Tiến độ:',
                    suffix=f'{completed_count}/{total_files} ({fname[:20]}...)',
                    length=35
                )
    else:
        # Mode AI / Hybrid: chạy tuần tự hoặc ít luồng để kiểm soát API rate limit
        ai_workers = min(args.workers, 4)
        def ai_worker(fname):
            in_file = os.path.join(input_folder, fname)
            out_file = os.path.join(output_folder, fname)
            try:
                win, wout = process_single_file(in_file, out_file, mode=args.mode, engine=args.engine, genre=args.genre, api_key=args.api_key)
                return True, wout, fname, None
            except Exception as e:
                return False, 0, fname, str(e)

        with ThreadPoolExecutor(max_workers=ai_workers) as executor:
            futures = [executor.submit(ai_worker, f) for f in files]
            for future in as_completed(futures):
                success, words, fname, err = future.result()
                completed_count += 1
                if success:
                    total_words += words
                print_progress_bar(
                    completed_count, total_files,
                    prefix='Tiến độ:',
                    suffix=f'{completed_count}/{total_files}',
                    length=35
                )

    # Sao chép file danh_sach_chuong.txt nếu có
    if catalog_file:
        src_cat = os.path.join(input_folder, catalog_file)
        dst_cat = os.path.join(output_folder, catalog_file)
        if src_cat != dst_cat:
            shutil.copy2(src_cat, dst_cat)

    elapsed = time.time() - start_time
    speed = total_files / elapsed if elapsed > 0 else 0

    print("=" * 65)
    print("🎉 HOÀN TẤT CHUYỂN ĐỔI TOÀN BỘ TRUYỆN!")
    print(f"⏱️  Thời gian thực thi : {elapsed:.2f} giây ({speed:.1f} chương/giây)")
    print(f"📖 Tổng số chương      : {completed_count}/{total_files}")
    print(f"📝 Tổng lượng từ dịch  : {total_words:,} từ")
    print(f"📂 Thư mục truyện dịch : {output_folder}")
    if catalog_file:
        print(f"📑 File mục lục        : {os.path.join(output_folder, catalog_file)}")
    print("=" * 65)

if __name__ == "__main__":
    main()
