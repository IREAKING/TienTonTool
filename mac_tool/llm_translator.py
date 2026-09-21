import os
import re
import json
import time
import requests
from typing import Optional, Dict, Any, List

SYSTEM_PROMPT = """Bạn là một dịch giả văn học chuyên nghiệp, bậc thầy dịch tiểu thuyết từ tiếng Trung sang tiếng Việt (đặc biệt là thể loại tiên hiệp, kiếm hiệp, huyền huyễn, đô thị, ngôn tình).
Nhiệm vụ của bạn: Dịch chính xác, tự nhiên và chau chuốt đoạn văn bản tiếng Trung được cung cấp sang tiếng Việt.

CÁC NGUYÊN TẮC BẮT BUỘC:
1. Văn phong: Mượt mà, chuẩn văn phong truyện mạng tiếng Việt, không bị dịch gượng hay dịch thô theo cấu trúc ngữ pháp tiếng Trung.
2. Danh từ riêng: Tên người, môn phái, địa danh, công pháp, cảnh giới tu luyện phải giữ nguyên theo âm Hán Việt chuẩn xác.
3. Đại từ xưng hô: Dùng đúng ngữ cảnh kiếm hiệp/tiên hiệp (hắn, nàng, y, lão, tiền bối, vãn bối, sư huynh, sư muội, bổn toạ...).
4. Đoạn hội thoại: Giữ nguyên trong ngoặc kép "" hoặc các dấu ngoặc gốc.
5. Định dạng: Giữ nguyên các đoạn ngắt dòng và cấu trúc đoạn văn bản gốc.
6. CHỈ trả về duy nhất nội dung bản dịch tiếng Việt, KHÔNG thêm lời mở đầu, giải thích hay ghi chú của dịch giả.
"""

class LLMTranslator:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "gemini_api_key": "",
            "deepseek_api_key": "",
            "openai_api_key": "",
            "openai_base_url": "",
            "active_engine": "offline"
        }

    def save_config(self, new_config: Dict[str, Any]) -> bool:
        self.config.update(new_config)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Lỗi lưu config: {e}")
            return False

    def _build_dict_prompt(self, dict_entries: Optional[Dict[str, str]] = None) -> str:
        if not dict_entries:
            return ""
        # Chỉ lấy tối đa 50 từ đầu để tránh quá dài prompt
        items = list(dict_entries.items())[:50]
        lines = ["\nDANH TỪ / TÊN RIÊNG BẮT BUỘC TUÂN THỦ:"]
        for src, tgt in items:
            lines.append(f"- {src} => {tgt}")
        return "\n".join(lines) + "\n"

    def translate_gemini(
        self,
        text: str,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        key = api_key or self.config.get("gemini_api_key", "").strip()
        if not key:
            raise ValueError("Chưa thiết lập Google Gemini API Key. Vui lòng cấu hình trong Cài Đặt.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}

        dict_hint = self._build_dict_prompt(dict_entries)
        prompt = f"{SYSTEM_PROMPT}\n{dict_hint}\nNội dung tiếng Trung cần dịch:\n\n{text}"

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            err_detail = resp.text
            try:
                err_json = resp.json()
                err_detail = err_json.get("error", {}).get("message", err_detail)
            except Exception:
                pass
            raise RuntimeError(f"Lỗi Gemini API ({resp.status_code}): {err_detail}")

        data = resp.json()
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini không trả về nội dung dịch.")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise RuntimeError("Gemini trả về kết quả rỗng.")
            return parts[0].get("text", "").strip()
        except Exception as e:
            raise RuntimeError(f"Lỗi phân tích phản hồi từ Gemini: {e}")

    def translate_deepseek(
        self,
        text: str,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        key = api_key or self.config.get("deepseek_api_key", "").strip()
        if not key:
            raise ValueError("Chưa thiết lập DeepSeek API Key. Vui lòng cấu hình trong Cài Đặt.")

        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }

        dict_hint = self._build_dict_prompt(dict_entries)
        sys_prompt = f"{SYSTEM_PROMPT}\n{dict_hint}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Dịch nội dung sau sang tiếng Việt:\n\n{text}"}
            ],
            "temperature": 0.3,
            "stream": False
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            err_detail = resp.text
            try:
                err_json = resp.json()
                err_detail = err_json.get("error", {}).get("message", err_detail)
            except Exception:
                pass
            raise RuntimeError(f"Lỗi DeepSeek API ({resp.status_code}): {err_detail}")

        data = resp.json()
        try:
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("DeepSeek không trả về nội dung dịch.")
            return choices[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            raise RuntimeError(f"Lỗi phân tích phản hồi từ DeepSeek: {e}")

    def translate(
        self,
        text: str,
        engine: str = "gemini",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        if "gemini" in engine.lower():
            model = "gemini-2.0-flash" if "2.0" in engine else "gemini-1.5-flash"
            return self.translate_gemini(text, api_key=api_key, model=model, dict_entries=dict_entries)
        elif "deepseek" in engine.lower():
            return self.translate_deepseek(text, api_key=api_key, model="deepseek-chat", dict_entries=dict_entries)
        else:
            raise ValueError(f"Engine LLM '{engine}' không được hỗ trợ.")
