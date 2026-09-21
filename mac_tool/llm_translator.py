import os
import re
import json
import time
import requests
import uuid
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
        cfg = {
            "gemini_api_key": "",
            "deepseek_api_key": "",
            "openai_api_key": "",
            "openai_base_url": "",
            "active_engine": "offline",
            "active_model_id": "",
            "global_system_prompt": "",
            "custom_models": []
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cfg.update(data)
            except Exception as e:
                print(f"Lỗi đọc config.json: {e}")
        return cfg

    def get_default_system_prompt(self) -> str:
        return SYSTEM_PROMPT.strip()

    def get_effective_prompt(self, model_cfg: Optional[Dict[str, Any]] = None) -> str:
        if model_cfg and model_cfg.get("system_prompt", "").strip():
            return model_cfg.get("system_prompt", "").strip()
        global_p = self.config.get("global_system_prompt", "").strip()
        if global_p:
            return global_p
        return SYSTEM_PROMPT.strip()

    def save_config(self, new_config: Dict[str, Any]) -> bool:
        self.config.update(new_config)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Lỗi lưu config: {e}")
            return False

    def get_custom_models(self, mask_keys: bool = True) -> List[Dict[str, Any]]:
        models = self.config.get("custom_models", [])
        if not mask_keys:
            return models

        result = []
        for m in models:
            m_copy = dict(m)
            key = m_copy.get("api_key", "")
            if key:
                if len(key) > 8:
                    m_copy["api_key_masked"] = f"{key[:4]}...{key[-4:]}"
                else:
                    m_copy["api_key_masked"] = "***"
            else:
                m_copy["api_key_masked"] = ""
            result.append(m_copy)
        return result

    def get_custom_model_raw(self, model_id_or_name: str) -> Optional[Dict[str, Any]]:
        models = self.config.get("custom_models", [])
        model_id_or_name = str(model_id_or_name).strip()
        for m in models:
            if m.get("id") == model_id_or_name:
                return m
            if m.get("name") == model_id_or_name:
                return m
            if m.get("model") == model_id_or_name:
                return m
        return None

    def save_custom_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Thêm mới hoặc cập nhật một Model AI tùy chỉnh"""
        models = self.config.get("custom_models", [])
        m_id = model_data.get("id", "").strip()

        # Chuẩn hóa base_url
        base_url = model_data.get("base_url", "").strip().rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"

        entry = {
            "id": m_id or f"custom_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            "name": model_data.get("name", "").strip() or model_data.get("model", "Custom Model"),
            "model": model_data.get("model", "").strip(),
            "base_url": base_url,
            "api_key": model_data.get("api_key", "").strip(),
            "reasoning_effort": model_data.get("reasoning_effort", "none"),
            "system_prompt": model_data.get("system_prompt", "").strip(),
            "temperature": float(model_data.get("temperature", 0.3)),
            "max_tokens": int(model_data.get("max_tokens", 8192))
        }

        # Nếu model_data không có key mới nhưng đang sửa model cũ thì giữ nguyên key cũ
        if not entry["api_key"] and m_id:
            old_model = self.get_custom_model_raw(m_id)
            if old_model:
                entry["api_key"] = old_model.get("api_key", "")

        found = False
        for i, m in enumerate(models):
            if m.get("id") == entry["id"]:
                models[i] = entry
                found = True
                break
        if not found:
            models.append(entry)

        self.config["custom_models"] = models
        self.save_config(self.config)
        return entry

    def delete_custom_model(self, model_id: str) -> bool:
        """Xóa bỏ một model AI tùy chỉnh"""
        models = self.config.get("custom_models", [])
        initial_len = len(models)
        models = [m for m in models if m.get("id") != model_id]
        if len(models) != initial_len:
            self.config["custom_models"] = models
            if self.config.get("active_model_id") == model_id:
                self.config["active_model_id"] = ""
            self.save_config(self.config)
            return True
        return False

    def set_active_model(self, model_id: str) -> bool:
        """Đặt model AI chỉ định làm model mặc định"""
        self.config["active_model_id"] = model_id or ""
        return self.save_config(self.config)

    def test_custom_model(self, model_data: Dict[str, Any]) -> Dict[str, Any]:
        """Kiểm tra kết nối tới Model AI tùy chỉnh với Base URL và API Key"""
        base_url = model_data.get("base_url", "").strip().rstrip("/")
        api_key = model_data.get("api_key", "").strip()
        model_name = model_data.get("model", "").strip()
        reasoning_effort = model_data.get("reasoning_effort", "none")

        if not base_url:
            return {"success": False, "error": "Chưa nhập Base URL"}
        if not model_name:
            return {"success": False, "error": "Chưa nhập Tên mã Model"}

        # Xác định endpoint chat completions
        if base_url.endswith("/chat/completions"):
            endpoint = base_url
        elif base_url.endswith("/v1"):
            endpoint = f"{base_url}/chat/completions"
        elif "/v1/" in base_url:
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = f"{base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a professional translator. Translate directly to Vietnamese. Output translation only."},
                {"role": "user", "content": "Hello world!"}
            ],
            "max_tokens": 100
        }

        # Gửi reasoning_effort nếu nhà cung cấp hỗ trợ
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning_effort"] = reasoning_effort

        t0 = time.time()
        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            latency = round(time.time() - t0, 2)

            if resp.status_code != 200:
                err_msg = resp.text
                try:
                    err_json = resp.json()
                    err_msg = err_json.get("error", {}).get("message", err_msg)
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": f"Lỗi HTTP {resp.status_code}: {err_msg}",
                    "latency": latency
                }

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return {"success": False, "error": "Phản hồi API rỗng (không có choices)", "latency": latency}

            reply = choices[0].get("message", {}).get("content", "").strip()
            # Lọc bỏ tag suy luận <think> nếu có
            clean_reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()

            return {
                "success": True,
                "result": clean_reply or reply,
                "latency": latency,
                "model": model_name
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Hết thời gian chờ (Timeout 30s). Hãy kiểm tra lại Base URL."}
        except requests.exceptions.ConnectionError as ce:
            return {"success": False, "error": f"Không thể kết nối tới Base URL ({ce})"}
        except Exception as e:
            return {"success": False, "error": f"Lỗi: {str(e)}"}

    def _build_dict_prompt(self, dict_entries: Optional[Dict[str, str]] = None) -> str:
        if not dict_entries:
            return ""
        items = list(dict_entries.items())[:50]
        lines = ["\nDANH TỪ / TÊN RIÊNG BẮT BUỘC TUÂN THỦ:"]
        for src, tgt in items:
            lines.append(f"- {src} => {tgt}")
        return "\n".join(lines) + "\n"

    def translate_openai_compatible(
        self,
        model_cfg: Dict[str, Any],
        text: str,
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        """Dịch văn bản qua chuẩn OpenAI-Compatible API với mọi nhà cung cấp AI"""
        base_url = model_cfg.get("base_url", "").strip().rstrip("/")
        api_key = model_cfg.get("api_key", "").strip()
        model = model_cfg.get("model", "").strip()
        reasoning_effort = model_cfg.get("reasoning_effort", "none")
        temperature = float(model_cfg.get("temperature", 0.3))
        max_tokens = int(model_cfg.get("max_tokens", 8192))

        if not model:
            raise ValueError(f"Model ID không được rỗng ({model_cfg.get('name')})")

        # Xác định URL
        if base_url.endswith("/chat/completions"):
            endpoint = base_url
        elif base_url.endswith("/v1"):
            endpoint = f"{base_url}/chat/completions"
        elif "/v1/" in base_url:
            endpoint = f"{base_url}/chat/completions"
        else:
            endpoint = f"{base_url}/v1/chat/completions"

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        dict_hint = self._build_dict_prompt(dict_entries)
        base_prompt = self.get_effective_prompt(model_cfg)
        sys_prompt = f"{base_prompt}\n{dict_hint}" if dict_hint else base_prompt

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Dịch nội dung sau sang tiếng Việt mượt mà, văn phong tiên hiệp tự nhiên:\n\n{text}"}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Cấp độ suy luận nếu được cấu hình
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning_effort"] = reasoning_effort

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_json = resp.json()
                err_msg = err_json.get("error", {}).get("message", err_msg)
            except Exception:
                pass
            raise RuntimeError(f"Lỗi {model_cfg.get('name')} ({resp.status_code}): {err_msg}")

        data = resp.json()
        try:
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("API không trả về nội dung dịch.")
            content = choices[0].get("message", {}).get("content", "").strip()
            # Khử thẻ suy luận <think>...</think> nếu có (như mô hình DeepSeek R1 / Qwen)
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            raise RuntimeError(f"Lỗi đọc kết quả từ {model}: {e}")

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
        base_prompt = self.get_effective_prompt()
        prompt = f"{base_prompt}\n{dict_hint}\nNội dung tiếng Trung cần dịch:\n\n{text}"

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
        base_prompt = self.get_effective_prompt()
        sys_prompt = f"{base_prompt}\n{dict_hint}" if dict_hint else base_prompt

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
            content = choices[0].get("message", {}).get("content", "").strip()
            # Lọc thẻ think nếu có
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            raise RuntimeError(f"Lỗi phân tích phản hồi từ DeepSeek: {e}")

    def translate(
        self,
        text: str,
        engine: str = "gemini",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        engine_str = str(engine).strip()

        # 1. Kiểm tra xem có khớp với Model AI Tùy chỉnh nào không
        custom_model = self.get_custom_model_raw(engine_str)
        if custom_model:
            return self.translate_openai_compatible(custom_model, text, dict_entries=dict_entries)

        # 2. Xử lý các model mặc định
        if "gemini" in engine_str.lower():
            model = "gemini-2.0-flash" if "2.0" in engine_str else "gemini-1.5-flash"
            return self.translate_gemini(text, api_key=api_key, model=model, dict_entries=dict_entries)
        elif "deepseek" in engine_str.lower():
            model = "deepseek-reasoner" if "reasoner" in engine_str.lower() or "r1" in engine_str.lower() else "deepseek-chat"
            return self.translate_deepseek(text, api_key=api_key, model=model, dict_entries=dict_entries)
        else:
            # Thử tìm model tùy chỉnh active nếu có
            active_id = self.config.get("active_model_id")
            if active_id:
                active_m = self.get_custom_model_raw(active_id)
                if active_m:
                    return self.translate_openai_compatible(active_m, text, dict_entries=dict_entries)

            raise ValueError(f"Không tìm thấy cấu hình cho Engine LLM '{engine}'. Vui lòng kiểm tra lại Cài Đặt Model AI.")
