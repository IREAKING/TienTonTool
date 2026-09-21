import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Callable, Dict, Any

from translator import NovelTranslator
from text_cleaner import text_cleaner

def natural_sort_key(s: str):
    """Sắp xếp tên file theo thứ tự số tự nhiên (1, 2, ... 10, ... 100)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def read_text_file(filepath: str) -> str:
    """Đọc file text với tự động thử các bảng mã phổ biến."""
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
    def __init__(self, translator: NovelTranslator, llm_translator=None, dict_manager=None):
        self.translator = translator
        self.llm_translator = llm_translator
        self.dict_manager = dict_manager
        self.is_running = False
        self.should_stop = False
        self.lock = threading.Lock()

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
        model_name: str = "",
        beam_size: int = 2,
        batch_size: int = 16,
        opencc_enabled: bool = True,
        prefix_output: str = "",
        suffix_output: str = "_viet",
        concurrency: int = 3,
        auto_clean_censor: bool = True,
        status_callback: Optional[Callable[[str, float, int, int], None]] = None
    ) -> List[str]:
        """
        Dịch toàn bộ file .txt trong input_folder và lưu vào output_folder.
        Hỗ trợ đa luồng (Multi-threading), tự động lưu từng chương (Auto-save) và khử rác kiểm duyệt.
        """
        self.is_running = True
        self.should_stop = False
        
        input_files = self.get_txt_files(input_folder)
        total_files = len(input_files)
        
        if total_files == 0:
            if status_callback:
                status_callback("Không tìm thấy file .txt nào trong thư mục nguồn!", 0.0, 0, 0)
            self.is_running = False
            return []

        os.makedirs(output_folder, exist_ok=True)
        is_custom = False
        if self.llm_translator:
            for cm in self.llm_translator.get_custom_models(mask_keys=False):
                if cm.get("id") == model_name or cm.get("name") in model_name or cm.get("model") in model_name:
                    is_custom = True
                    break

        is_llm = is_custom or "(custom ai)" in model_name.lower() or "gemini" in model_name.lower() or "deepseek" in model_name.lower()

        # Chuẩn bị model offline nếu không dùng LLM
        if not is_llm:
            self.translator.opencc_enabled = opencc_enabled
            if self.translator.current_model_key != model_name or self.translator.translator is None:
                self.translator.load_model(model_name)

        completed_count = 0
        start_time = time.time()

        def translate_single_file(filepath: str) -> Optional[str]:
            if self.should_stop:
                return None

            filename = os.path.basename(filepath)
            base_name, ext = os.path.splitext(filename)
            out_filename = f"{prefix_output}{base_name}{suffix_output}{ext}"
            out_filepath = os.path.join(output_folder, out_filename)

            # Đọc nội dung
            raw_text = read_text_file(filepath).strip()
            if not raw_text:
                return None

            # Khử rác kiểm duyệt (c·hết -> chết, g·iết -> giết...)
            if auto_clean_censor:
                raw_text, _ = text_cleaner.clean_all(raw_text)

            translated_text = ""
            if is_llm and self.llm_translator:
                # Dịch bằng LLM kèm cơ chế tự động thử lại (Retry & Exponential Backoff)
                max_retries = 3
                for attempt in range(max_retries):
                    if self.should_stop:
                        return None
                    try:
                        dict_entries = self.dict_manager.entries if self.dict_manager else []
                        translated_text = self.llm_translator.translate(
                            raw_text,
                            engine=model_name,
                            dict_entries=dict_entries
                        )
                        if translated_text:
                            break
                    except Exception as err:
                        if "429" in str(err) or "quota" in str(err).lower():
                            time.sleep(2 ** (attempt + 1))
                        else:
                            time.sleep(1)
            else:
                # Dịch bằng mô hình offline CTranslate2
                translated_text = self.translator.translate_text(
                    raw_text,
                    beam_size=beam_size,
                    batch_size=batch_size
                )

            if translated_text:
                # Auto-save ngay lập tức từng chương
                with open(out_filepath, "w", encoding="utf-8") as f:
                    f.write(translated_text)
                return out_filepath
            return None

        actual_concurrency = max(1, min(concurrency, 5))
        # Nếu dùng CTranslate2 trên CPU, giới hạn concurrency ở mức 2-3 để tránh nghẽn CPU
        if not is_llm:
            actual_concurrency = min(actual_concurrency, 2)

        with ThreadPoolExecutor(max_workers=actual_concurrency) as executor:
            futures = {executor.submit(translate_single_file, fpath): fpath for fpath in input_files}
            for future in as_completed(futures):
                if self.should_stop:
                    break
                fpath = futures[future]
                fname = os.path.basename(fpath)
                try:
                    res = future.result()
                    if res:
                        with self.lock:
                            completed_files.append(res)
                            completed_count += 1
                            elapsed = time.time() - start_time
                            speed = round((completed_count / max(elapsed, 1)) * 60, 1) # chương/phút
                            pct = round((completed_count / total_files) * 100, 1)
                            msg = f"[{completed_count}/{total_files}] Đã dịch & lưu: {fname} ({pct}% - {speed} ch/phút)"
                            if status_callback:
                                status_callback(msg, pct, completed_count, total_files)
                except Exception as e:
                    with self.lock:
                        completed_count += 1
                        pct = round((completed_count / total_files) * 100, 1)
                        msg = f"⚠️ Lỗi dịch file {fname}: {e}"
                        if status_callback:
                            status_callback(msg, pct, completed_count, total_files)

        self.is_running = False
        if not self.should_stop and status_callback:
            status_callback(f"Hoàn thành xuất sắc! Đã dịch xong {len(completed_files)}/{total_files} file.", 100.0, len(completed_files), total_files)

        return completed_files

    def stop(self):
        self.should_stop = True
