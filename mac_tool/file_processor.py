import os
import re
from typing import List, Optional, Callable
from translator import NovelTranslator

def natural_sort_key(s: str):
    """Sắp xếp tên file theo thứ tự số tự nhiên (1, 2, ... 10, ... 100)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def read_text_file(filepath: str) -> str:
    """Đọc file text với tự động thử các bảng mã phổ biến (UTF-8, GB18030, GBK, Big5, UTF-16)."""
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "big5", "utf-16", "latin-1"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

class BatchFileProcessor:
    def __init__(self, translator: NovelTranslator):
        self.translator = translator
        self.is_running = False
        self.is_paused = False
        self.should_stop = False

    def get_txt_files(self, folder_path: str) -> List[str]:
        if not os.path.isdir(folder_path):
            return []
        files = [
            f for f in os.listdir(folder_path) 
            if f.lower().endswith(".txt") and not f.startswith(".")
        ]
        files.sort(key=natural_sort_key)
        return [os.path.join(folder_path, f) for f in files]

    def process_folder(
        self,
        input_folder: str,
        output_folder: str,
        beam_size: int = 2,
        batch_size: int = 16,
        prefix_output: str = "",
        suffix_output: str = "_viet",
        status_callback: Optional[Callable[[str, float], None]] = None
    ) -> List[str]:
        """
        Dịch toàn bộ file .txt trong input_folder và lưu vào output_folder.
        Ví dụ: 100.txt -> 100_viet.txt (giống định dạng truyen_dich cũ)
        """
        self.is_running = True
        self.should_stop = False
        
        input_files = self.get_txt_files(input_folder)
        total_files = len(input_files)
        
        if total_files == 0:
            if status_callback:
                status_callback("Không tìm thấy file .txt nào trong thư mục nguồn!", 0.0)
            self.is_running = False
            return []

        os.makedirs(output_folder, exist_ok=True)
        completed_files = []

        for idx, filepath in enumerate(input_files):
            if self.should_stop:
                if status_callback:
                    status_callback(f"Đã dừng quá trình dịch tại file {idx}/{total_files}.", idx / total_files)
                break

            filename = os.path.basename(filepath)
            base_name, ext = os.path.splitext(filename)
            out_filename = f"{prefix_output}{base_name}{suffix_output}{ext}"
            out_filepath = os.path.join(output_folder, out_filename)

            msg = f"[{idx+1}/{total_files}] Đang đọc & dịch file: {filename}..."
            overall_progress = idx / total_files
            if status_callback:
                status_callback(msg, overall_progress)

            raw_text = read_text_file(filepath)
            
            def file_progress(pct, text_status):
                if status_callback:
                    # Tiến độ kết hợp giữa số file và số đoạn của file hiện tại
                    combined_pct = (idx + pct) / total_files
                    status_callback(f"[{idx+1}/{total_files}] {filename}: {text_status}", combined_pct)

            translated_text = self.translator.translate_text(
                raw_text,
                beam_size=beam_size,
                batch_size=batch_size,
                progress_callback=file_progress
            )

            with open(out_filepath, "w", encoding="utf-8") as f:
                f.write(translated_text)

            completed_files.append(out_filepath)

        self.is_running = False
        if not self.should_stop and status_callback:
            status_callback(f"Hoàn thành xuất sắc! Đã dịch xong {len(completed_files)}/{total_files} file.", 1.0)

        return completed_files

    def stop(self):
        self.should_stop = True
