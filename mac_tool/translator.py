import os
import re
import sys
from typing import List, Optional, Callable, Tuple, Dict
from huggingface_hub import hf_hub_download
import sentencepiece as spm
import ctranslate2
from opencc import OpenCC
from dictionary import DictionaryManager

# Danh sách mô hình dịch tiếng Trung -> tiếng Việt chuyên truyện
AVAILABLE_MODELS = {
    "DanVP/MoxhiMT-60 (Đỉnh Cao Tiên Hiệp - Văn phong đỉnh cao)": {
        "repo_id": "DanVP/MoxhiMT-60",
        "subfolder": "ct2-int8",
        "files": [
            "config.json",
            "model.bin",
            "shared_vocabulary.json",
            "source.spm",
            "target.spm"
        ]
    },
    "robebo116/60-zh-vi (Văn phong mượt - Khuyên dùng)": {
        "repo_id": "robebo116/60-zh-vi",
        "subfolder": "ct2-int8_float32",
        "files": [
            "config.json",
            "model.bin",
            "shared_vocabulary.json",
            "source.spm",
            "target.spm"
        ]
    },
    "ngocdang83/HachimiMT-60-QT (Convert Phong Cách QuickTranslator Chuẩn)": {
        "repo_id": "ngocdang83/HachimiMT-60-QT",
        "subfolder": "ct2-int8_float32",
        "files": [
            "config.json",
            "model.bin",
            "shared_vocabulary.json",
            "source.spm",
            "target.spm"
        ]
    },
    "robebo116/QT (Phong cách QuickTranslator / Convert)": {
        "repo_id": "robebo116/QT",
        "subfolder": "ct2-int8_float32",
        "files": [
            "config.json",
            "model.bin",
            "shared_vocabulary.json",
            "source.spm",
            "target.spm"
        ]
    },
    "ngocdang83/HachimiMT-60-zh-vi": {
        "repo_id": "ngocdang83/HachimiMT-60-zh-vi",
        "subfolder": "ct2-int8_float32",
        "files": [
            "config.json",
            "model.bin",
            "shared_vocabulary.json",
            "source.spm",
            "target.spm"
        ]
    }
}

class NovelTranslator:
    def __init__(self, models_dir: str = "models", dict_manager: Optional[DictionaryManager] = None):
        self.models_dir = os.path.abspath(models_dir)
        os.makedirs(self.models_dir, exist_ok=True)
        self.dict_manager = dict_manager or DictionaryManager()
        
        self.current_model_key = None
        self.translator = None
        self.sp_source = None
        self.sp_target = None
        
        # Bộ chuyển đổi Hán phồn thể -> Hán giản thể
        self.cc_t2s = OpenCC("t2s")
        self.opencc_enabled = True

    def is_model_downloaded(self, model_key: str) -> bool:
        if model_key not in AVAILABLE_MODELS:
            return False
        model_info = AVAILABLE_MODELS[model_key]
        clean_name = model_info["repo_id"].replace("/", "_")
        target_dir = os.path.join(self.models_dir, clean_name)
        
        if not os.path.exists(target_dir):
            return False
        
        for fname in model_info["files"]:
            if not os.path.exists(os.path.join(target_dir, fname)):
                return False
        return True

    def download_model(self, model_key: str, progress_callback: Optional[Callable[[str], None]] = None) -> str:
        if model_key not in AVAILABLE_MODELS:
            raise ValueError(f"Model {model_key} không tồn tại.")
        
        model_info = AVAILABLE_MODELS[model_key]
        repo_id = model_info["repo_id"]
        subfolder = model_info.get("subfolder", "")
        clean_name = repo_id.replace("/", "_")
        target_dir = os.path.join(self.models_dir, clean_name)
        os.makedirs(target_dir, exist_ok=True)

        for fname in model_info["files"]:
            target_path = os.path.join(target_dir, fname)
            if not os.path.exists(target_path):
                if progress_callback:
                    progress_callback(f"Đang tải {fname} từ {repo_id}...")
                
                remote_filename = f"{subfolder}/{fname}" if subfolder else fname
                downloaded_file = hf_hub_download(
                    repo_id=repo_id,
                    filename=remote_filename,
                    local_dir=target_dir
                )
                expected_path = os.path.join(target_dir, remote_filename)
                if os.path.exists(expected_path) and expected_path != target_path:
                    os.rename(expected_path, target_path)

        if progress_callback:
            progress_callback(f"Đã tải xong model {repo_id}!")
        return target_dir

    def load_model(self, model_key: str, progress_callback: Optional[Callable[[str], None]] = None, inter_threads: int = 2, intra_threads: int = 4):
        if self.current_model_key == model_key and self.translator is not None:
            return

        if not self.is_model_downloaded(model_key):
            self.download_model(model_key, progress_callback)

        model_info = AVAILABLE_MODELS[model_key]
        clean_name = model_info["repo_id"].replace("/", "_")
        target_dir = os.path.join(self.models_dir, clean_name)

        if progress_callback:
            progress_callback("Đang nạp mô hình vào bộ nhớ RAM...")

        # Nạp SentencePiece
        sp_src_path = os.path.join(target_dir, "source.spm")
        sp_tgt_path = os.path.join(target_dir, "target.spm")
        
        self.sp_source = spm.SentencePieceProcessor()
        self.sp_source.load(sp_src_path)

        self.sp_target = spm.SentencePieceProcessor()
        if os.path.exists(sp_tgt_path):
            self.sp_target.load(sp_tgt_path)
        else:
            self.sp_target.load(sp_src_path)

        # Nạp CTranslate2
        self.translator = ctranslate2.Translator(
            target_dir,
            device="cpu",
            compute_type="int8",
            inter_threads=inter_threads,
            intra_threads=intra_threads
        )
        self.current_model_key = model_key
        if progress_callback:
            progress_callback(f"Đã nạp thành công mô hình: {model_key}")

    def split_into_chunks(self, text: str, max_chunk_len: int = 350) -> List[Tuple[str, str]]:
        """
        Tách văn bản thành các dòng/câu, giữ nguyên cấu trúc dòng trống để không mất định dạng đoạn văn.
        Trả về danh sách tuple: (loại_dòng, nội_dung)
        loại_dòng: 'text' hoặc 'newline'
        """
        lines = text.split("\n")
        chunks = []
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                chunks.append(("newline", "\n"))
                continue
            
            # Nếu dòng quá dài, tách theo dấu câu tiếng Trung (。！？；…)
            if len(line_str) > max_chunk_len:
                sentences = re.split(r'([。！？；…\?!]+)', line_str)
                current_sub = ""
                for s in sentences:
                    if not s:
                        continue
                    if len(current_sub) + len(s) <= max_chunk_len:
                        current_sub += s
                    else:
                        if current_sub.strip():
                            chunks.append(("text", current_sub.strip()))
                        current_sub = s
                if current_sub.strip():
                    chunks.append(("text", current_sub.strip()))
            else:
                chunks.append(("text", line_str))
            
            chunks.append(("newline", "\n"))
            
        return chunks

    def _clean_quotes(self, text: str) -> Tuple[str, Optional[Tuple[str, str]]]:
        """
        Kiểm tra nếu câu được bao bọc bởi dấu ngoặc kép (tránh hallucination lặp đối thoại).
        Trả về (câu_đã_bỏ_ngoặc, (ngoặc_mở, ngoặc_đóng))
        """
        quote_pairs = [
            ("“", "”"),
            ('"', '"'),
            ("「", "」"),
            ("『", "』"),
            ("‘", "’")
        ]
        s = text.strip()
        for q_open, q_close in quote_pairs:
            if s.startswith(q_open) and s.endswith(q_close) and len(s) >= 2:
                inner = s[len(q_open):-len(q_close)].strip()
                return inner, (q_open, q_close)
        return s, None

    def _clean_repetitions_by_source(self, vi_text: str, zh_text: str) -> str:
        """
        Khử lặp thông minh dựa trên câu gốc tiếng Trung:
        - Nếu tiếng Trung CÓ lặp lại (VD: '快跑！快跑！', '杀！杀！杀！'):
          Giữ nguyên đúng số lần lặp tương ứng trong tiếng Việt.
        - Nếu tiếng Trung KHÔNG lặp lại (VD: '这么多！', '当然。', '楚执事离去。'):
          Loại bỏ hoàn toàn các câu lặp dư thừa/ảo giác của mô hình.
        """
        # 0. Chuẩn hóa dấu câu lặp (ví dụ !! -> !)
        vi_text = re.sub(r'([.!?…])\1+', r'\1', vi_text)

        # 1. Đếm số câu/vế trong tiếng Trung (loại bỏ ngoặc kép ở 2 đầu trước khi đếm)
        clean_zh = re.sub(r'^[“"「『‘\s]+|[”"」』’\s]+$', '', zh_text.strip())
        zh_puncts = re.findall(r'[。！？!\?…]+', clean_zh)
        zh_sentences = [s.strip() for s in re.split(r'[。！？!\?…]+', clean_zh) if s.strip()]
        num_zh_sentences = max(len(zh_sentences), len(zh_puncts), 1)

        # 2. Tách các câu trong tiếng Việt (kèm dấu câu)
        vi_tokens = re.split(r'([.!?…]+)', vi_text)
        vi_sentences = []
        for i in range(0, len(vi_tokens) - 1, 2):
            sent = vi_tokens[i].strip()
            punct = vi_tokens[i+1].strip()
            if sent:
                vi_sentences.append(sent + punct)
        if len(vi_tokens) % 2 == 1 and vi_tokens[-1].strip():
            vi_sentences.append(vi_tokens[-1].strip())

        if not vi_sentences:
            return vi_text.strip()

        # 3. Nếu số câu tiếng Việt nhiều hơn tiếng Trung:
        if len(vi_sentences) > num_zh_sentences:
            kept = vi_sentences[:num_zh_sentences]
            return ' '.join(kept)
        else:
            return re.sub(r'([^.!?]+[.!?])(\s*\1)+', r'\1', vi_text, flags=re.IGNORECASE).strip()

    def translate_batch(self, texts: List[str], beam_size: int = 2) -> List[str]:
        """Dịch một mẻ danh sách các câu tiếng Trung sang tiếng Việt."""
        if not texts:
            return []

        processed_data = []
        for t in texts:
            # 1. Chuyển đổi OpenCC nếu bật
            if self.opencc_enabled:
                t = self.cc_t2s.convert(t)
            
            # 2. Xử lý dấu ngoặc kép để tránh lặp câu
            inner_text, quote_pair = self._clean_quotes(t)
            
            # 3. Mask từ điển tên nhân vật / thuật ngữ
            if self.dict_manager:
                inner_text, p_map = self.dict_manager.mask_text(inner_text)
            else:
                p_map = {}

            processed_data.append((inner_text, quote_pair, p_map))

        # Tokenize bằng SentencePiece
        tokens = [self.sp_source.encode_as_pieces(item[0]) for item in processed_data]

        # Tính độ dài decoding động theo câu nguồn để triệt tiêu triệt để hallucination loop
        max_in_tokens = max(len(t) for t in tokens) if tokens else 10
        dynamic_max_len = min(512, max(35, int(max_in_tokens * 3.5)))

        # Dịch bằng CTranslate2 với tham số giải mã tối ưu hóa cao cấp
        results = self.translator.translate_batch(
            tokens,
            beam_size=beam_size,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
            max_decoding_length=dynamic_max_len,
            length_penalty=0.8,
            coverage_penalty=0.2,
            disable_unk=True,
            replace_unknowns=True,
            batch_type="examples"
        )

        # Decode & phục hồi từ điển, ngoặc kép
        translated_texts = []
        for res, (inner_text, quote_pair, p_map), orig_text in zip(results, processed_data, texts):
            hypo = res.hypotheses[0]
            vi_text = self.sp_target.decode_pieces(hypo).strip()
            
            # Phục hồi từ điển
            if p_map:
                vi_text = self.dict_manager.unmask_text(vi_text, p_map)
            
            # Xử lý khử lặp thông minh đối chiếu với tiếng Trung:
            # Nếu chữ Hán có lặp lại -> giữ nguyên lặp lại
            # Nếu chữ Hán không lặp lại -> loại bỏ lặp lại
            vi_text = self._clean_repetitions_by_source(vi_text, orig_text)

            # Làm mượt văn phong tiếng Việt (xóa bỏ ngữ pháp gượng)
            vi_text = self._polish_vietnamese_text(vi_text)

            # Phục hồi ngoặc kép nếu có
            if quote_pair:
                vi_text = f'"{vi_text}"'
                
            translated_texts.append(vi_text)

        return translated_texts

    def _polish_vietnamese_text(self, text: str) -> str:
        """Làm mượt văn phong tiếng Việt, xử lý ngữ pháp Hán Việt gượng gạo."""
        if not text:
            return ""
        # 1. Khắc phục cấu trúc ngữ pháp Hán: "của hắn kiếm" -> "kiếm của hắn"
        text = re.sub(r'\bcủa (hắn|nàng|ta|ngươi|y) (kiếm|tay|thân thể|ánh mắt|đan điền|nguyên thần|phi kiếm|sư phụ|đồ đệ|chân|đầu|mặt|miệng)\b', r'\2 của \1', text, flags=re.IGNORECASE)
        
        # 2. Làm mượt các cụm từ máy dịch gượng gạo
        replacements = [
            (r'\btrong lòng hơi động\b', 'trong lòng khẽ động'),
            (r'\bcó chút ít\b', 'hơi'),
            (r'\bkhông khỏi đến\b', 'không khỏi'),
            (r'\bkém một chút liền\b', 'suýt chút nữa liền'),
            (r'\bkém một chút\b', 'suýt nữa'),
            (r'\bánh mắt hơi nheo lại\b', 'ánh mắt khẽ nheo lại')
        ]
        for pat, repl in replacements:
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

        # 3. Sửa chữ hoa bất thường giữa câu sau từ mask
        text = re.sub(r'(\b[a-zA-ZÀ-ỹ]+)\s+Bên trong\b', r'\1 bên trong', text)
        text = re.sub(r'(\b[a-zA-ZÀ-ỹ]+)\s+Bên ngoài\b', r'\1 bên ngoài', text)
        text = re.sub(r'(\b[a-zA-ZÀ-ỹ]+)\s+Trong mơ hồ\b', r'\1 trong mơ hồ', text)
        text = re.sub(r'(\b[a-zA-ZÀ-ỹ]+)\s+Trên người\b', r'\1 trên người', text)
        text = re.sub(r'(\b[a-zA-ZÀ-ỹ]+)\s+Dưới chân\b', r'\1 dưới chân', text)

        # 4. Chuẩn hóa dấu câu
        text = re.sub(r'\.{2,}', '...', text)
        text = re.sub(r' +([,.\?!;:])', r'\1', text)
        return text

    def translate_text(
        self,
        text: str,
        beam_size: int = 2,
        batch_size: int = 16,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> str:
        """Dịch toàn bộ văn bản hoặc chương truyện."""
        if not text.strip():
            return ""

        if self.translator is None:
            raise RuntimeError("Chưa nạp mô hình dịch. Hãy gọi load_model() trước.")

        chunks = self.split_into_chunks(text)
        
        # Gom các chunk loại 'text' để dịch theo batch
        text_indices = [i for i, (c_type, _) in enumerate(chunks) if c_type == "text"]
        total_texts = len(text_indices)
        
        translated_map = {}
        for start_idx in range(0, total_texts, batch_size):
            end_idx = min(start_idx + batch_size, total_texts)
            batch_idxs = text_indices[start_idx:end_idx]
            batch_texts = [chunks[i][1] for i in batch_idxs]
            
            translated_batch = self.translate_batch(batch_texts, beam_size=beam_size)
            for idx, trans in zip(batch_idxs, translated_batch):
                translated_map[idx] = trans
                
            if progress_callback and total_texts > 0:
                progress = end_idx / total_texts
                progress_callback(progress, f"Đang dịch: {end_idx}/{total_texts} đoạn ({int(progress*100)}%)")

        # Ghép kết quả lại thành văn bản hoàn chỉnh
        output_lines = []
        for i, (c_type, val) in enumerate(chunks):
            if c_type == "text":
                output_lines.append(translated_map.get(i, val))
            elif c_type == "newline":
                output_lines.append(val)

        return "".join(output_lines)
