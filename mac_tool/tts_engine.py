#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hệ thống Tổng hợp Giọng nói Tiếng Việt (Text-to-Speech Engine)
Tích hợp từ điển chuẩn hóa phát âm 17,800+ từ của TTS_XUAN_AN_VN_v6.4.0
Hỗ trợ Microsoft Neural Voices (Nam Minh, Hoài My) & macOS Native Say (Linh)
"""

import os
import re
import json
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Callable

try:
    from text_cleaner import text_cleaner
except ImportError:
    from mac_tool.text_cleaner import text_cleaner

BASE_DIR = Path(__file__).resolve().parent
NORMALIZE_MAP_PATH = BASE_DIR / "normalize_map.json"
AUDIO_CACHE_DIR = BASE_DIR / "audio_cache"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PIPER_MODELS_DIR = BASE_DIR / "models" / "tts"
PIPER_MODELS_DIR.mkdir(parents=True, exist_ok=True)


class VietnamesePhoneticNormalizer:
    """
    Chuẩn hóa phát âm từ mượn, tiếng Anh, tên riêng sang âm tiếng Việt tự nhiên
    Sử dụng kho dữ liệu 17,839 từ của XuanAn TTS
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(VietnamesePhoneticNormalizer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, map_path: Path = NORMALIZE_MAP_PATH):
        if getattr(self, "_initialized", False):
            return

        self.mapping: Dict[str, str] = {}
        self.pattern = None
        self._load_mapping(map_path)
        self._initialized = True

    def _load_mapping(self, map_path: Path):
        if not map_path.exists():
            print(f"[TTS Normalizer] Cảnh báo: Không tìm thấy {map_path}")
            return

        try:
            with open(map_path, "r", encoding="utf-8") as f:
                self.mapping = json.load(f)

            # Sắp xếp các từ dài nhất lên trước để match cụm từ trước từ đơn
            sorted_keys = sorted(self.mapping.keys(), key=len, reverse=True)
            if sorted_keys:
                pattern_str = r"\b(" + "|".join(map(re.escape, sorted_keys)) + r")\b"
                self.pattern = re.compile(pattern_str, re.IGNORECASE)
            print(f"[TTS Normalizer] Đã nạp thành công {len(self.mapping):,} từ chuẩn hóa phát âm.")
        except Exception as e:
            print(f"[TTS Normalizer] Lỗi nạp từ điển: {e}")

    def clean_text_for_speech(self, text: str) -> str:
        """Làm sạch các ký tự rác, dấu phân cách không cần đọc"""
        if not text:
            return ""

        # Khử ký tự rác né kiểm duyệt (c·hết -> chết, g·iết -> giết, b·ạo đ·ộng -> bạo động)
        text, _ = text_cleaner.clean_censored_words(text)

        # Bỏ URL
        text = re.sub(r"https?://\S+", "", text)
        # Bỏ thẻ HTML nếu có
        text = re.sub(r"<[^>]+>", "", text)
        # Bỏ chuỗi phân cách lặp như =================, ------------, ********
        text = re.sub(r"[-=_*~]{3,}", " ", text)
        # Chuẩn hóa khoảng trắng
        text = re.sub(r"[ \t]+", " ", text)
        # Giữ lại tối đa 2 dòng trống liên tiếp
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def normalize(self, text: str) -> str:
        """Thay thế từ ngoại lai bằng phiên âm tiếng Việt"""
        cleaned = self.clean_text_for_speech(text)
        if not cleaned:
            return ""

        if self.pattern and self.mapping:
            return self.pattern.sub(
                lambda m: self.mapping.get(m.group(0).lower(), m.group(0)),
                cleaned
            )
        return cleaned


class TTSEngine:
    """Bộ máy đọc giọng nói tiếng Việt chuyên dụng cho truyện audio (Hỗ trợ mô hình tự train offline & Cloud)"""

    def __init__(self):
        self.normalizer = VietnamesePhoneticNormalizer()

    def get_voices(self) -> List[Dict]:
        return [
            {
                "id": "vi-VN-NamMinhNeural",
                "name": "Nam Minh (Giọng Nam - Truyền Cảm / Tiên Hiệp)",
                "gender": "male",
                "type": "neural",
                "sample_rate": "48000Hz"
            },
            {
                "id": "vi-VN-HoaiMyNeural",
                "name": "Hoài My (Giọng Nữ - Truyền Cảm / Ngôn Tình)",
                "gender": "female",
                "type": "neural",
                "sample_rate": "48000Hz"
            },
            {
                "id": "macos-linh",
                "name": "Linh (macOS Native - Offline 100%)",
                "gender": "female",
                "type": "macos",
                "sample_rate": "22050Hz"
            }
        ]

    def _split_into_chunks(self, text: str, max_chunk_chars: int = 2500) -> List[str]:
        """Chia văn bản dài thành các đoạn nhỏ theo dấu câu ngắt dòng tự nhiên"""
        if len(text) <= max_chunk_chars:
            return [text]

        paragraphs = text.split("\n")
        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_len + len(para) > max_chunk_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [para]
                current_len = len(para)
            else:
                current_chunk.append(para)
                current_len += len(para) + 1

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        final_chunks = []
        for ch in chunks:
            if len(ch) <= max_chunk_chars:
                final_chunks.append(ch)
            else:
                sentences = re.split(r"([.?!;]+[\s\n]+)", ch)
                sub_chunk = ""
                for s in sentences:
                    if len(sub_chunk) + len(s) > max_chunk_chars and sub_chunk:
                        final_chunks.append(sub_chunk.strip())
                        sub_chunk = s
                    else:
                        sub_chunk += s
                if sub_chunk.strip():
                    final_chunks.append(sub_chunk.strip())

        return [c for c in final_chunks if c.strip()]

    async def _synthesize_edge_chunk(self, text: str, voice: str, rate_str: str, pitch_str: str, output_path: str):
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
        await communicate.save(output_path)

    def _synthesize_macos_say(self, text: str, output_path: str, speed_multiplier: float = 1.0):
        """Dùng lệnh say của macOS (Offline 100%)"""
        wpm = int(round(185 * speed_multiplier))
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp_aiff:
            aiff_path = tmp_aiff.name

        try:
            cmd = ["say", "-v", "Linh", "-r", str(wpm), "-o", aiff_path, text]
            subprocess.run(cmd, check=True)

            cmd_conv = [
                "ffmpeg", "-y", "-i", aiff_path,
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                output_path
            ]
            subprocess.run(cmd_conv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            if os.path.exists(aiff_path):
                try:
                    os.remove(aiff_path)
                except Exception:
                    pass

    async def synthesize(
        self,
        text: str,
        voice: str = "vi-VN-NamMinhNeural",
        speed: float = 1.0,
        output_path: Optional[str] = None,
        normalize: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> str:
        """
        Tổng hợp giọng nói từ văn bản và lưu ra file MP3
        Hỗ trợ Edge TTS (Neural chất lượng cao), macOS Linh và 80+ giọng nhân vật clone
        """
        if not text or not text.strip():
            raise ValueError("Văn bản cần đọc không được để trống!")

        processed_text = self.normalizer.normalize(text) if normalize else self.normalizer.clean_text_for_speech(text)
        if not processed_text:
            raise ValueError("Văn bản sau khi làm sạch bị trống!")

        if not output_path:
            with tempfile.NamedTemporaryFile(suffix=".mp3", dir=AUDIO_CACHE_DIR, delete=False) as tmp:
                output_path = tmp.name

        output_path = str(Path(output_path).resolve())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        from clone_manager import clone_manager
        clone_voice_id = voice[6:].strip() if voice.startswith("clone:") else voice
        clone_profile = clone_manager.get_voice_by_id(clone_voice_id)

        actual_voice = voice
        pitch_str = "+0Hz"
        rate_offset = 0

        if clone_profile:
            actual_voice = clone_profile.get("base_voice", "vi-VN-NamMinhNeural")
            pitch_str = clone_profile.get("pitch", "+0Hz")
            try:
                rate_offset = int(clone_profile.get("rate", "0%").replace("%", "").replace("+", ""))
            except Exception:
                rate_offset = 0
        elif voice.startswith("clone:") or voice.startswith("offline:"):
            actual_voice = "vi-VN-NamMinhNeural"

        raw_output_path = output_path
        has_filter = bool(clone_profile and clone_profile.get("filter"))
        if has_filter:
            with tempfile.NamedTemporaryFile(suffix="_raw.mp3", dir=AUDIO_CACHE_DIR, delete=False) as tmp_raw:
                raw_output_path = tmp_raw.name

        # 1. macOS say (nếu chọn)
        if actual_voice == "macos-linh":
            if progress_callback:
                progress_callback(50, 100, "Đang đọc qua macOS Say...")
            self._synthesize_macos_say(processed_text, raw_output_path, speed_multiplier=speed)
        else:
            # 2. Microsoft Neural (Chuẩn)
            rate_pct = int(round((speed - 1.0) * 100)) + rate_offset
            rate_str = f"{rate_pct:+d}%"

            chunks = self._split_into_chunks(processed_text, max_chunk_chars=3000)

            if len(chunks) == 1:
                if progress_callback:
                    progress_callback(1, 1, "Đang tổng hợp giọng Neural...")
                await self._synthesize_edge_chunk(chunks[0], actual_voice, rate_str, pitch_str, raw_output_path)
            else:
                chunk_files = []
                try:
                    for idx, chunk in enumerate(chunks):
                        if progress_callback:
                            progress_callback(idx + 1, len(chunks), f"Đang tổng hợp đoạn {idx + 1}/{len(chunks)}")
                        with tempfile.NamedTemporaryFile(suffix=f"_chunk_{idx}.mp3", dir=AUDIO_CACHE_DIR, delete=False) as tmp_chunk:
                            cpath = tmp_chunk.name
                        chunk_files.append(cpath)
                        await self._synthesize_edge_chunk(chunk, actual_voice, rate_str, pitch_str, cpath)

                    concat_list_path = os.path.join(AUDIO_CACHE_DIR, f"concat_{os.path.basename(output_path)}.txt")
                    with open(concat_list_path, "w", encoding="utf-8") as f:
                        for cf in chunk_files:
                            f.write(f"file '{cf}'\n")

                    cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", concat_list_path,
                        "-c", "copy", raw_output_path
                    ]
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    try:
                        os.remove(concat_list_path)
                    except Exception:
                        pass
                finally:
                    for cf in chunk_files:
                        if os.path.exists(cf):
                            try:
                                os.remove(cf)
                            except Exception:
                                pass

        # Áp dụng bộ lọc âm thanh clone nếu có
        if has_filter:
            if progress_callback:
                progress_callback(100, 100, "Đang áp dụng hiệu ứng âm thanh...")
            try:
                clone_manager.apply_profile_effects(raw_output_path, output_path, clone_profile)
            finally:
                if os.path.exists(raw_output_path) and raw_output_path != output_path:
                    try:
                        os.remove(raw_output_path)
                    except Exception:
                        pass

        if progress_callback:
            progress_callback(100, 100, "Hoàn tất!")

        return output_path


# Khởi tạo singleton
tts_engine = TTSEngine()
