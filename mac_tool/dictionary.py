import os
import re
from typing import Dict, List, Tuple

class DictionaryManager:
    """
    Quản lý từ điển tên nhân vật, địa danh, thuật ngữ (VietPhrase / Names).
    Kết hợp Siêu Từ Điển Tiên Hiệp tích hợp sẵn + Từ điển tùy chỉnh của người dùng.
    Áp dụng thuật toán Masking/Unmasking để mô hình dịch chuẩn xác 100% không bị méo tên.
    """
    def __init__(self, dict_path: str = "names.txt"):
        self.dict_path = os.path.abspath(dict_path)
        self.builtin_path = os.path.join(os.path.dirname(self.dict_path), "builtin_xianxia.txt")
        self.builtin_entries: Dict[str, str] = {}
        self.custom_entries: Dict[str, str] = {}
        self.entries: Dict[str, str] = {}
        self.sorted_keys: List[str] = []
        self.load()

    def _parse_file(self, file_path: str) -> Dict[str, str]:
        parsed = {}
        if not os.path.exists(file_path):
            return parsed
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    parts = line.split("=", 1)
                elif "\t" in line:
                    parts = line.split("\t", 1)
                else:
                    continue
                src = parts[0].strip()
                tgt = parts[1].strip()
                if src and tgt:
                    parsed[src] = tgt
        return parsed

    def load(self, path: str = None) -> int:
        if path:
            self.dict_path = os.path.abspath(path)

        # 1. Nạp từ điển Tiên Hiệp tích hợp sẵn
        self.builtin_entries = self._parse_file(self.builtin_path)

        # 2. Tạo default names.txt nếu chưa có
        if not os.path.exists(self.dict_path):
            self._create_default()

        # 3. Nạp từ điển tùy chỉnh của người dùng
        self.custom_entries = self._parse_file(self.dict_path)

        # 4. Gộp: từ điển tùy chỉnh của người dùng luôn ghi đè từ điển tích hợp
        self.entries = {**self.builtin_entries, **self.custom_entries}

        # Sắp xếp theo độ dài giảm dần (từ dài ưu tiên thay thế trước)
        self.sorted_keys = sorted(self.entries.keys(), key=len, reverse=True)
        return len(self.entries)

    def _create_default(self):
        default_content = """# Từ điển tên nhân vật / thuật ngữ tùy chỉnh (Names Dictionary)
# Định dạng: Từ gốc=Từ dịch hoặc Từ gốc[Tab]Từ dịch
# Ví dụ:
# 苏阳=Tô Dương
# 奉神教=Phụng Thần Giáo
# 奉神岛=Phụng Thần Đảo
# 血衍圣者=Huyết Diễn Thánh Giả
# 合体圣者=Hợp Thể Thánh Giả
"""
        with open(self.dict_path, "w", encoding="utf-8") as f:
            f.write(default_content)

    def mask_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Thay thế các từ tiếng Trung trong từ điển bằng placeholder an toàn: <0>, <1>, <2>...
        Trả về text đã mask và mapping để phục hồi sau khi dịch.
        """
        if not text or not self.sorted_keys:
            return text, {}

        placeholder_map: Dict[str, str] = {}
        counter = 0

        for key in self.sorted_keys:
            if key in text:
                token = f" <{counter}> "
                placeholder_map[f"<{counter}>"] = self.entries[key]
                text = text.replace(key, token)
                counter += 1

        return text, placeholder_map

    def unmask_text(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """Phục hồi placeholder <0>, <1> thành từ dịch tiếng Việt."""
        if not text or not placeholder_map:
            return text

        for token, val in placeholder_map.items():
            num = token.strip("<>")
            pattern = re.compile(rf'[<⟨\(\[]\s*{num}\s*[>⟩\)\]]')
            text = pattern.sub(val, text)

        # Dọn dẹp khoảng trắng thừa trước dấu câu
        text = re.sub(r' +([,.\?!;:])', r'\1', text)
        return text

    def add_entry(self, src: str, tgt: str) -> bool:
        src = src.strip()
        tgt = tgt.strip()
        if not src or not tgt:
            return False
        self.custom_entries[src] = tgt
        self.entries[src] = tgt
        self.sorted_keys = sorted(self.entries.keys(), key=len, reverse=True)
        self.save()
        return True

    def save(self):
        """Lưu lại chỉ các từ của người dùng vào names.txt."""
        with open(self.dict_path, "w", encoding="utf-8") as f:
            f.write("# Từ điển tên nhân vật / thuật ngữ tùy chỉnh\n")
            for k in sorted(self.custom_entries.keys(), key=len, reverse=True):
                f.write(f"{k}={self.custom_entries[k]}\n")

    def get_all_text(self) -> str:
        if os.path.exists(self.dict_path):
            with open(self.dict_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def update_from_text(self, text: str) -> int:
        with open(self.dict_path, "w", encoding="utf-8") as f:
            f.write(text)
        return self.load()
