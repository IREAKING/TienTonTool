import os
import re
import sys
from typing import Tuple, List, Optional, Callable

# Các mẫu website chèn link watermark / quảng cáo
WATERMARK_PATTERNS = [
    r'bạn\s+đang\s+đọc\s+truyện\s+(?:tại|trên|ở)\s+[^\n.,;!?]+',
    r'nguồn\s*:\s*https?://[^\s]+',
    r'truyện\s+(?:được\s+)?(?:đăng|chia\s+sẻ|reup)\s+(?:tại|trên)\s+[^\n.,;!?]+',
    r'chúc\s+bạn\s+đọc\s+truyện\s+vui\s+vẻ[^\n]*',
    r'xem\s+bản\s+dịch\s+sớm\s+nhất\s+tại[^\n]*',
    r'ủng\s+hộ\s+(?:nhóm\s+dịch|dịch\s+giả|tác\s+giả)[^\n]*',
    r'theo\s+dõi\s+(?:fanpage|kênh|website)[^\n]*',
    r'(?:truyenfull|tangthuvien|metruyenchu|truyencv|sstruyen|nettruyen|bachngocsach|wikidich|thichdoctruyen)\.(?:vn|com|net|org|xyz|cc)',
    r'\(本章完\)',
    r'\(第\s*\d+\s*页\)',
    r'69\s*书吧',
    r'69shuba\.(?:cx|com|pro|me|cc)',
    r'69xinshu\.(?:com|net)',
    r'请收藏本站[^\n]*',
    r'最快更新[^\n]*',
    r'天才一秒记住[^\n]*',
    r'本章未完[^\n]*',
    r'点击下一页[^\n]*',
    r'wap\.faloo\.com[^\n]*',
    r'b\.faloo\.com[^\n]*',
]

# Các từ nhạy cảm hay bị website truyện chèn dấu cách (c h ế t, g i ế t...)
SPACED_WORDS_MAP = {
    "c h ế t": "chết",
    "g i ế t": "giết",
    "b ạ o  đ ộ n g": "bạo động",
    "b ạ o  l ự c": "bạo lực",
    "c ư ỡ n g  b ứ c": "cưỡng bức",
    "d â m": "dâm",
    "d ụ c": "dục",
    "s á t  n h â n": "sát nhân",
    "s á t": "sát",
    "t h i  t h ể": "thi thể",
    "m á u  m e": "máu me",
    "đ ẫ m  m á u": "đẫm máu",
    "k h ỏ a  t h â n": "khỏa thân",
    "t ự  s á t": "tự sát",
    "đ ộ c  d ư ợ c": "độc dược",
    "h ã m  h ạ i": "hãm hại",
}

class TextCleaner:
    def __init__(self):
        # 1. Ký tự ẩn / zero-width unicode
        self.re_zero_width = re.compile(r'[\u200b\u200c\u200d\ufeff\u00ad\u2060\u200e\u200f]')

        # 2. Middle dot, bullet, sao, gạch chéo, caret, ngã chèn giữa các chữ cái
        # Ví dụ: c·hết, g·iết, b·ạo, đ·ộng, s*á*t, đ/ộc, b_ắ_n, c•hết, c‧hết
        self.re_intra_censor = re.compile(
            r'(?<=[a-zA-ZÀ-ỹ0-9])\s*[·•‧∙・･\*\~^\/|_]+\s*(?=[a-zA-ZÀ-ỹ0-9])'
        )

        # 3. Dấu chấm hoặc gạch nối chèn giữa các chữ cái tiếng Việt
        # Ví dụ: c.hết, g.iết, d.â.m, b-ắ-n
        self.re_dot_inside_word = re.compile(
            r'(?<=[a-zA-ZÀ-ỹ])\.(?=[a-zA-ZÀ-ỹ])'
        )
        self.re_hyphen_inside_word = re.compile(
            r'(?<=[a-zA-ZÀ-ỹ])-(?=[a-zA-ZÀ-ỹ])'
        )

        # 4. Watermarks & ads
        self.re_watermarks = [re.compile(p, re.IGNORECASE) for p in WATERMARK_PATTERNS]

    def clean_censored_words(self, text: str) -> Tuple[str, int]:
        """
        Khử toàn bộ các dạng chèn ký tự rác né kiểm duyệt:
        c·hết -> chết
        g·iết -> giết
        b·ạo đ·ộng -> bạo động
        s*á*t -> sát
        đ.ộc -> độc
        d.â.m -> dâm
        Trả về (văn_bản_đã_làm_sạch, số_từ_đã_sửa)
        """
        if not text:
            return "", 0

        original_text = text

        # B1: Xóa ký tự tàng hình (zero-width)
        text = self.re_zero_width.sub('', text)

        # B2: Đổi các từ bị tách chữ cái đơn (c h ế t -> chết)
        for spaced, corrected in SPACED_WORDS_MAP.items():
            pattern = re.compile(re.escape(spaced), re.IGNORECASE)
            text = pattern.sub(corrected, text)

        # B3: Xóa middle dots, bullets, asterisks, slashes giữa chữ
        # Ví dụ: c·hết -> chết, g·iết -> giết, b·ạo -> bạo
        text = self.re_intra_censor.sub('', text)

        # B4: Xóa dấu chấm chèn giữa các chữ cái (c.hết -> chết, d.â.m -> dâm)
        text = self.re_dot_inside_word.sub('', text)

        # B5: Xóa gạch nối chèn giữa các chữ cái đơn (b-ắ-n -> bắn)
        # Chỉ áp dụng nếu trước và sau là chữ cái
        text = self.re_hyphen_inside_word.sub('', text)

        # Đếm số lượng thay đổi ước lượng
        # Nếu độ dài thay đổi hoặc khác ban đầu
        diff_count = max(0, len(original_text) - len(text))
        if original_text != text and diff_count == 0:
            diff_count = 1

        return text, diff_count

    def clean_watermarks(self, text: str) -> str:
        """Loại bỏ các đoạn text quảng cáo, watermark của web truyện"""
        if not text:
            return ""

        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line_strip = line.strip()
            # Bỏ qua nếu dòng này trùng khớp với watermark
            is_wm = False
            for pat in self.re_watermarks:
                if pat.search(line_strip):
                    is_wm = True
                    break
            if not is_wm:
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def clean_html_and_spacing(self, text: str) -> str:
        """Làm sạch thực thể HTML và khoảng trắng thừa"""
        if not text:
            return ""

        # HTML entities
        text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&apos;', "'")
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = re.sub(r'</?(?:br|p|div|span|strong|em)[^>]*>', '\n', text, flags=re.IGNORECASE)

        # Khoảng trắng lặp lại
        text = re.sub(r'[ \t]+', ' ', text)
        # Khoảng trắng trước dấu câu
        text = re.sub(r' +([,.;:!?])', r'\1', text)
        # Cách sau dấu câu
        text = re.sub(r'([,.;:!?])(?=[^\s"\'\)])', r'\1 ', text)
        # Dấu chấm lửng
        text = re.sub(r'\.{4,}', '...', text)
        # Xuống dòng thừa
        text = re.sub(r'\n\s*\n+', '\n\n', text)

        return text.strip()

    def clean_all(self, text: str, remove_watermarks: bool = True) -> Tuple[str, int]:
        """Quy trình làm sạch toàn diện: Khử censored + Khử watermark + Chuẩn hóa dấu câu"""
        if not text:
            return "", 0

        # 1. Khử censored
        text, count = self.clean_censored_words(text)

        # 2. Khử watermark nếu yêu cầu
        if remove_watermarks:
            text = self.clean_watermarks(text)

        # 3. Chuẩn hóa khoảng trắng & dấu câu
        text = self.clean_html_and_spacing(text)

        return text, count

    def clean_folder(
        self,
        input_folder: str,
        output_folder: str,
        suffix: str = "_clean",
        remove_watermarks: bool = True,
        status_callback: Optional[Callable[[str, float, str, int, int], None]] = None
    ):
        """Xử lý làm sạch hàng loạt toàn bộ file .txt trong thư mục"""
        self._is_stopped = False
        os.makedirs(output_folder, exist_ok=True)

        files = [
            os.path.join(input_folder, f) for f in os.listdir(input_folder)
            if f.lower().endswith(".txt") and not f.startswith(".")
        ]

        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
        files.sort(key=natural_sort_key)

        total = len(files)
        if total == 0:
            if status_callback:
                status_callback("Không tìm thấy file .txt nào trong thư mục!", 0.0, "", 0, 0)
            return

        total_cleaned_words = 0

        for i, fpath in enumerate(files, 1):
            if getattr(self, '_is_stopped', False):
                if status_callback:
                    status_callback("Đã dừng tiến trình làm sạch!", round((i / total) * 100, 1), os.path.basename(fpath), i, total)
                break

            fname = os.path.basename(fpath)
            pct = round(((i - 1) / total) * 100, 1)
            if status_callback:
                status_callback(f"[{i}/{total}] Đang làm sạch: {fname}...", pct, fname, i, total)

            content = ""
            for enc in ["utf-8", "utf-8-sig", "gb18030", "utf-16", "cp1258", "latin1"]:
                try:
                    with open(fpath, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not content.strip():
                continue

            try:
                cleaned, count = self.clean_all(content, remove_watermarks=remove_watermarks)
                total_cleaned_words += count

                base, ext = os.path.splitext(fname)
                out_path = os.path.join(output_folder, f"{base}{suffix}{ext}")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(cleaned)
            except Exception as e:
                if status_callback:
                    status_callback(f"⚠️ Lỗi {fname}: {str(e)}", pct, fname, i, total)

        if not getattr(self, '_is_stopped', False) and status_callback:
            status_callback(
                f"Hoàn tất làm sạch {total} file! Đã xử lý khử rác thành công.",
                100.0, "", total, total
            )

    def stop(self):
        self._is_stopped = True


text_cleaner = TextCleaner()
