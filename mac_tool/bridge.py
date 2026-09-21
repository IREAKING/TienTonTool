import os
import sys
import json
import time
import uuid
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Thêm đường dẫn hiện tại vào sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dictionary import DictionaryManager
from translator import NovelTranslator, AVAILABLE_MODELS
from file_processor import BatchFileProcessor
from scraper import NovelScraper, POPULAR_PRESETS
from exporter import merge_txt, export_epub, strip_titles_and_export_catalog
from llm_translator import LLMTranslator
from tts_engine import tts_engine, AUDIO_CACHE_DIR
from clone_manager import clone_manager
from convert_polisher import convert_polisher
from text_cleaner import text_cleaner
from glossary_extractor import glossary_extractor
import urllib.parse
import asyncio

PORT = 58231

# Khởi tạo translator, batch processor, scraper, exporter và LLM translator
MODELS_DIR = os.path.join(BASE_DIR, "models")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

dict_mgr = DictionaryManager(os.path.join(BASE_DIR, "names.txt"))
translator = NovelTranslator(models_dir=MODELS_DIR, dict_manager=dict_mgr)
llm_trans = LLMTranslator()
batch_proc = BatchFileProcessor(translator=translator, llm_translator=llm_trans, dict_manager=dict_mgr)
scraper = NovelScraper(translator=translator)

# Tiến trình batch Convert sang Dịch
batch_convert_state = {
    "is_running": False,
    "current_file": "",
    "current_index": 0,
    "total_files": 0,
    "progress": 0.0,
    "logs": [],
    "status_msg": "Sẵn sàng"
}
batch_convert_lock = threading.Lock()

# Tiến trình làm sạch file hàng loạt
clean_folder_state = {
    "is_running": False,
    "current_file": "",
    "current_index": 0,
    "total_files": 0,
    "progress": 0.0,
    "logs": [],
    "status_msg": "Sẵn sàng"
}
clean_folder_lock = threading.Lock()

# Tiến trình batch hiện tại
batch_state = {
    "is_running": False,
    "current_file": "",
    "current_index": 0,
    "total_files": 0,
    "progress": 0.0,
    "logs": [],
    "status_msg": "Sẵn sàng"
}
batch_lock = threading.Lock()

# Tiến trình batch TTS hiện tại
batch_tts_state = {
    "is_running": False,
    "current_file": "",
    "current_index": 0,
    "total_files": 0,
    "progress": 0.0,
    "logs": [],
    "status_msg": "Sẵn sàng"
}
batch_tts_lock = threading.Lock()

# Quản lý task TTS bất đồng bộ (tránh timeout trên các đoạn văn dài)
tts_tasks = {}
tts_tasks_lock = threading.Lock()

class BridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def _serve_audio_file(self, fpath, mime_type="audio/mpeg"):
        if not fpath or not os.path.isfile(fpath):
            self._send_json({"error": "File audio không tồn tại"}, 404)
            return

        file_size = os.path.getsize(fpath)
        range_header = self.headers.get("Range")

        if range_header and range_header.startswith("bytes="):
            try:
                byte_range = range_header[6:].strip()
                parts = byte_range.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
                content_length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(content_length))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                if self.command != "HEAD":
                    with open(fpath, "rb") as f:
                        f.seek(start)
                        remaining = content_length
                        while remaining > 0:
                            chunk_size = min(remaining, 64 * 1024)
                            data = f.read(chunk_size)
                            if not data:
                                break
                            self.wfile.write(data)
                            remaining -= len(data)
                return
            except Exception:
                pass

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if self.command != "HEAD":
            with open(fpath, "rb") as f:
                while True:
                    data = f.read(64 * 1024)
                    if not data:
                        break
                    self.wfile.write(data)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send_json({"status": "ok", "model": translator.current_model_key})
        elif path == "/models":
            models_data = []
            # 1. Các mô hình offline chất lượng cao
            for name in AVAILABLE_MODELS.keys():
                downloaded = translator.is_model_downloaded(name)
                is_active = (translator.current_model_key == name)
                models_data.append({
                    "name": name,
                    "type": "offline",
                    "downloaded": downloaded,
                    "active": is_active
                })
            # 2. Thêm các mô hình Cloud AI LLM
            models_data.append({
                "name": "Gemini 1.5 Flash (Google AI - Nhanh & Mượt)",
                "type": "llm",
                "downloaded": True,
                "active": False
            })
            models_data.append({
                "name": "DeepSeek-V3 (AI Văn Học - Chuẩn xác cao)",
                "type": "llm",
                "downloaded": True,
                "active": False
            })
            # 3. Thêm các mô hình Custom AI LLM do người dùng cấu hình
            custom_list = llm_trans.get_custom_models(mask_keys=False)
            active_cid = llm_trans.config.get("active_model_id", "")
            for cm in custom_list:
                c_id = cm.get("id", "")
                c_name = cm.get("name", "") or cm.get("model", "")
                reasoning = cm.get("reasoning_effort", "none")
                r_badge = f" [Suy luận: {reasoning}]" if reasoning and reasoning != "none" else ""
                display_label = f"🤖 {c_name}{r_badge} (Custom AI)"
                models_data.append({
                    "name": display_label,
                    "model_id": c_id,
                    "raw_model": cm.get("model", ""),
                    "type": "custom_llm",
                    "downloaded": True,
                    "active": (c_id == active_cid)
                })
            self._send_json({"models": models_data})
        elif path == "/api/custom-models":
            self._send_json({
                "models": llm_trans.get_custom_models(mask_keys=True),
                "active_model_id": llm_trans.config.get("active_model_id", "")
            })
        elif path == "/api/system-prompt":
            self._send_json({
                "default_prompt": llm_trans.get_default_system_prompt(),
                "global_prompt": llm_trans.config.get("global_system_prompt", "")
            })
        elif path == "/convert/prompts":
            from convert_polisher import CONVERT_PROMPTS
            self._send_json({
                "prompts": CONVERT_PROMPTS,
                "saved_prompt": llm_trans.config.get("convert_system_prompt", "")
            })
        elif path == "/settings":
            cfg = llm_trans.load_config()
            gemini_k = cfg.get("gemini_api_key", "")
            deepseek_k = cfg.get("deepseek_api_key", "")
            masked_cfg = {
                "has_gemini_key": bool(gemini_k),
                "gemini_masked": f"{gemini_k[:6]}...{gemini_k[-4:]}" if len(gemini_k) > 10 else ("***" if gemini_k else ""),
                "has_deepseek_key": bool(deepseek_k),
                "deepseek_masked": f"{deepseek_k[:6]}...{deepseek_k[-4:]}" if len(deepseek_k) > 10 else ("***" if deepseek_k else ""),
                "active_engine": cfg.get("active_engine", "offline")
            }
            self._send_json(masked_cfg)
        elif path == "/dict":
            self._send_json({"content": dict_mgr.get_all_text(), "count": len(dict_mgr.entries)})
        elif path == "/batch_status":
            with batch_lock:
                self._send_json(batch_state)
        elif path == "/scraper/presets":
            self._send_json(POPULAR_PRESETS)
        elif path == "/scraper/status":
            with scraper.lock:
                self._send_json(scraper.current_job)
        elif path == "/tts/voices":
            self._send_json({"voices": tts_engine.get_voices()})
        elif path == "/tts/clone_voices":
            self._send_json({"voices": clone_manager.get_all_clone_voices()})
        elif path == "/tts/batch_status":
            with batch_tts_lock:
                self._send_json(batch_tts_state)
        elif path == "/convert/batch_status":
            with batch_convert_lock:
                self._send_json(batch_convert_state)
        elif path == "/clean_folder_status":
            with clean_folder_lock:
                self._send_json(clean_folder_state)
        elif path == "/tts/task_status":
            qs = parse_qs(parsed.query)
            task_id = qs.get("id", [""])[0]
            with tts_tasks_lock:
                task = tts_tasks.get(task_id)
            if task:
                self._send_json(task)
            else:
                self._send_json({"status": "error", "error": "Không tìm thấy tiến trình TTS"}, 404)
        elif path.startswith("/tts/sample_audio/"):
            voice_name = urllib.parse.unquote(path[len("/tts/sample_audio/"):])
            fpath = clone_manager.get_sample_audio_path(voice_name)
            self._serve_audio_file(fpath, "audio/wav" if fpath and fpath.endswith(".wav") else "audio/mpeg")
        elif path.startswith("/tts/audio/"):
            fname = urllib.parse.unquote(os.path.basename(path))
            fpath = os.path.join(AUDIO_CACHE_DIR, fname)
            self._serve_audio_file(fpath, "audio/mpeg")
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        try:
            req = json.loads(post_data)
        except Exception:
            req = {}

        if path == "/settings":
            new_cfg = {}
            if "gemini_api_key" in req and req["gemini_api_key"].strip():
                new_cfg["gemini_api_key"] = req["gemini_api_key"].strip()
            if "deepseek_api_key" in req and req["deepseek_api_key"].strip():
                new_cfg["deepseek_api_key"] = req["deepseek_api_key"].strip()
            if "active_engine" in req:
                new_cfg["active_engine"] = req["active_engine"]
            success = llm_trans.save_config(new_cfg)
            self._send_json({"success": success})

        elif path == "/api/custom-models/save":
            try:
                saved = llm_trans.save_custom_model(req)
                self._send_json({"success": True, "model": saved})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/custom-models/delete":
            m_id = req.get("id", "")
            if not m_id:
                self._send_json({"success": False, "error": "Thiếu ID model"}, 400)
            else:
                ok = llm_trans.delete_custom_model(m_id)
                self._send_json({"success": ok})

        elif path == "/api/custom-models/set-active":
            m_id = req.get("id", "")
            ok = llm_trans.set_active_model(m_id)
            self._send_json({"success": ok})

        elif path == "/api/custom-models/test":
            try:
                test_res = llm_trans.test_custom_model(req)
                self._send_json(test_res)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/system-prompt":
            p = req.get("prompt", "")
            ok = llm_trans.save_config({"global_system_prompt": p.strip()})
            self._send_json({"success": ok})

        elif path == "/translate":
            text = req.get("text", "")
            model_name = req.get("model") or list(AVAILABLE_MODELS.keys())[0]
            beam_size = int(req.get("beam_size", 2))
            batch_size = int(req.get("batch_size", 16))
            opencc_enabled = bool(req.get("opencc", True))

            if not text.strip():
                self._send_json({"result": "", "error": "Văn bản rỗng"})
                return

            start_t = time.time()
            try:
                # Kiểm tra nếu là custom model (theo id, name, model hoặc nhãn chứa Custom AI)
                is_custom = False
                for cm in llm_trans.get_custom_models(mask_keys=False):
                    if cm.get("id") == model_name or cm.get("name") in model_name or cm.get("model") in model_name:
                        is_custom = True
                        break

                # Xử lý nếu chọn dịch bằng LLM hoặc Custom Model
                if is_custom or "(custom ai)" in model_name.lower() or "gemini" in model_name.lower() or "deepseek" in model_name.lower():
                    result = llm_trans.translate(
                        text,
                        engine=model_name,
                        dict_entries=dict_mgr.entries
                    )
                else:
                    translator.opencc_enabled = opencc_enabled
                    if translator.current_model_key != model_name or translator.translator is None:
                        translator.load_model(model_name)
                    result = translator.translate_text(text, beam_size=beam_size, batch_size=batch_size)

                elapsed = time.time() - start_t
                self._send_json({"result": result, "time": round(elapsed, 2)})
            except Exception as e:
                self._send_json({"result": "", "error": str(e)}, 500)

        elif path == "/load_model":
            model_name = req.get("model", "")
            if model_name in AVAILABLE_MODELS:
                try:
                    translator.load_model(model_name)
                    self._send_json({"status": "loaded", "model": model_name})
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
            elif "gemini" in model_name.lower() or "deepseek" in model_name.lower() or "(custom ai)" in model_name.lower() or any(m.get("id") == model_name for m in llm_trans.get_custom_models(mask_keys=False)):
                self._send_json({"status": "loaded", "model": model_name})
            else:
                self._send_json({"error": "Model không hợp lệ"}, 400)

        elif path == "/dict":
            content = req.get("content", "")
            count = dict_mgr.update_from_text(content)
            self._send_json({"status": "saved", "count": count})

        elif path == "/add_dict_entry":
            src = req.get("src", "").strip()
            tgt = req.get("tgt", "").strip()
            if src and tgt:
                dict_mgr.add_entry(src, tgt)
                self._send_json({"status": "added", "content": dict_mgr.get_all_text()})
            else:
                self._send_json({"error": "Từ gốc hoặc từ dịch rỗng"}, 400)

        elif path == "/check_folder":
            folder = req.get("folder", "")
            if os.path.isdir(folder):
                files = batch_proc.get_txt_files(folder)
                self._send_json({"count": len(files), "preview": [os.path.basename(f) for f in files[:20]]})
            else:
                self._send_json({"error": "Thư mục không tồn tại", "count": 0}, 400)

        elif path == "/start_batch":
            input_folder = req.get("input_folder", "")
            output_folder = req.get("output_folder", EXPORTS_DIR)
            suffix = req.get("suffix", "_viet")
            model_name = req.get("model", list(AVAILABLE_MODELS.keys())[0])
            beam_size = int(req.get("beam_size", 2))
            batch_size = int(req.get("batch_size", 16))
            opencc_enabled = bool(req.get("opencc", True))
            concurrency = int(req.get("concurrency", 3))
            auto_clean = bool(req.get("auto_clean", True))
            resume = bool(req.get("resume", True))

            if not os.path.isdir(input_folder):
                self._send_json({"error": "Thư mục nguồn không hợp lệ"}, 400)
                return

            def run_batch():
                with batch_lock:
                    batch_state["is_running"] = True
                    batch_state["logs"] = []
                    batch_state["progress"] = 0.0
                    batch_state["status_msg"] = "Đang chuẩn bị dịch đa luồng..."

                try:
                    def status_cb(msg, pct, cur_cnt=0, total_cnt=0):
                        with batch_lock:
                            batch_state["status_msg"] = msg
                            batch_state["progress"] = pct
                            batch_state["current_index"] = cur_cnt
                            batch_state["total_files"] = total_cnt
                            batch_state["logs"].append(msg)
                            if len(batch_state["logs"]) > 150:
                                batch_state["logs"].pop(0)

                    batch_proc.process_folder(
                        input_folder=input_folder,
                        output_folder=output_folder,
                        model_name=model_name,
                        beam_size=beam_size,
                        batch_size=batch_size,
                        opencc_enabled=opencc_enabled,
                        suffix_output=suffix,
                        concurrency=concurrency,
                        auto_clean_censor=auto_clean,
                        resume=resume,
                        status_callback=status_cb
                    )
                except Exception as e:
                    with batch_lock:
                        batch_state["status_msg"] = f"Lỗi: {str(e)}"
                finally:
                    with batch_lock:
                        batch_state["is_running"] = False

            t = threading.Thread(target=run_batch, daemon=True)
            t.start()
            self._send_json({"status": "started"})

        elif path == "/stop_batch":
            batch_proc.stop()
            with batch_lock:
                batch_state["status_msg"] = "Đang dừng tiến trình dịch..."
            self._send_json({"status": "stopping"})

        elif path == "/scraper/test":
            url = req.get("url", "")
            title_sel = req.get("title_selector", "")
            content_sel = req.get("content_selector", "")
            exclude_sel = req.get("exclude_selector", "")
            next_sel = req.get("next_selector", "")
            res = scraper.test_single_chapter(url, title_sel, content_sel, exclude_sel, next_sel)
            self._send_json(res)

        elif path == "/scraper/toc":
            url = req.get("url", "")
            toc_sel = req.get("toc_selector", "")
            try:
                chapters = scraper.extract_toc(url, toc_selector=toc_sel)
                self._send_json({"chapters": chapters, "count": len(chapters)})
            except Exception as e:
                self._send_json({"error": str(e), "chapters": [], "count": 0}, 500)

        elif path == "/scraper/start":
            url = req.get("url", "")
            save_folder = req.get("save_folder") or os.path.join(BASE_DIR, "crawled_novels")
            title_sel = req.get("title_selector", "")
            content_sel = req.get("content_selector", "")
            exclude_sel = req.get("exclude_selector", "")
            next_sel = req.get("next_selector", "")
            wait_min = float(req.get("wait_min", 0.5))
            wait_max = float(req.get("wait_max", 1.5))
            max_chapters = int(req.get("max_chapters", 0))
            auto_translate = bool(req.get("auto_translate", False))
            trans_model = req.get("model", "")
            trans_beam = int(req.get("beam_size", 2))
            trans_batch = int(req.get("batch_size", 16))
            trans_opencc = bool(req.get("opencc", True))
            mode = req.get("mode", "sequential")
            concurrency = int(req.get("concurrency", 4))
            resume = bool(req.get("resume", True))
            toc_sel = req.get("toc_selector", "")

            res = scraper.start_scraping(
                start_url=url,
                save_folder=save_folder,
                title_sel=title_sel,
                content_sel=content_sel,
                exclude_sel=exclude_sel,
                next_sel=next_sel,
                wait_min=wait_min,
                wait_max=wait_max,
                max_chapters=max_chapters,
                auto_translate=auto_translate,
                trans_model=trans_model,
                trans_beam=trans_beam,
                trans_batch=trans_batch,
                trans_opencc=trans_opencc,
                mode=mode,
                concurrency=concurrency,
                resume=resume,
                toc_sel=toc_sel
            )
            self._send_json(res)

        elif path == "/scraper/stop":
            res = scraper.stop_scraping()
            self._send_json(res)

        elif path == "/export/merge_txt":
            folder = req.get("folder", "")
            title = req.get("title", "Truyện Tổng Hợp")
            author = req.get("author", "Khuyết Danh")
            try:
                res = merge_txt(folder, novel_title=title, author=author)
                self._send_json(res)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/export/epub":
            folder = req.get("folder", "")
            title = req.get("title", "Truyện Dịch")
            author = req.get("author", "Khuyết Danh")
            try:
                res = export_epub(folder, novel_title=title, author=author)
                self._send_json(res)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/export/strip_titles":
            folder = req.get("folder", "")
            in_place = req.get("in_place", False)
            output_folder = req.get("output_folder", None)
            try:
                res = strip_titles_and_export_catalog(folder, output_folder=output_folder, in_place=in_place)
                self._send_json(res)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/tts/task_start":
            text = req.get("text", "")
            voice = req.get("voice", "vi-VN-NamMinhNeural")
            speed = float(req.get("speed", 1.0))
            normalize = bool(req.get("normalize", True))

            if not text.strip():
                self._send_json({"success": False, "error": "Văn bản cần đọc không được để trống"}, 400)
                return

            task_id = f"tts_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            with tts_tasks_lock:
                tts_tasks[task_id] = {
                    "task_id": task_id,
                    "status": "in_progress",
                    "progress": 0,
                    "current_chunk": 0,
                    "total_chunks": 0,
                    "status_msg": "Đang chuẩn bị mô hình...",
                    "audio_url": None,
                    "filename": None,
                    "file_path": None,
                    "error": None
                }

            def run_tts_task():
                def on_prog(cur, total, msg):
                    with tts_tasks_lock:
                        if task_id in tts_tasks:
                            pct = int(round((cur / max(total, 1)) * 100))
                            tts_tasks[task_id]["progress"] = min(pct, 99)
                            tts_tasks[task_id]["current_chunk"] = cur
                            tts_tasks[task_id]["total_chunks"] = total
                            tts_tasks[task_id]["status_msg"] = msg

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    out_path = loop.run_until_complete(
                        tts_engine.synthesize(
                            text, voice=voice, speed=speed, normalize=normalize,
                            progress_callback=on_prog
                        )
                    )
                    loop.close()
                    fname = os.path.basename(out_path)
                    with tts_tasks_lock:
                        if task_id in tts_tasks:
                            tts_tasks[task_id]["status"] = "done"
                            tts_tasks[task_id]["progress"] = 100
                            tts_tasks[task_id]["status_msg"] = "Hoàn tất!"
                            tts_tasks[task_id]["audio_url"] = f"http://127.0.0.1:{PORT}/tts/audio/{fname}"
                            tts_tasks[task_id]["filename"] = fname
                            tts_tasks[task_id]["file_path"] = out_path
                except Exception as exc:
                    with tts_tasks_lock:
                        if task_id in tts_tasks:
                            tts_tasks[task_id]["status"] = "error"
                            tts_tasks[task_id]["error"] = str(exc)

            th = threading.Thread(target=run_tts_task, daemon=True)
            th.start()
            self._send_json({"success": True, "task_id": task_id})

        elif path == "/tts/speak":
            text = req.get("text", "")
            voice = req.get("voice", "vi-VN-NamMinhNeural")
            speed = float(req.get("speed", 1.0))
            normalize = bool(req.get("normalize", True))

            if not text.strip():
                self._send_json({"success": False, "error": "Văn bản cần đọc không được để trống"}, 400)
                return

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                out_path = loop.run_until_complete(
                    tts_engine.synthesize(text, voice=voice, speed=speed, normalize=normalize)
                )
                loop.close()
                fname = os.path.basename(out_path)
                self._send_json({
                    "success": True,
                    "audio_url": f"http://127.0.0.1:{PORT}/tts/audio/{fname}",
                    "filename": fname,
                    "file_path": out_path
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/tts/batch_start":
            input_folder = req.get("input_folder", "")
            output_folder = req.get("output_folder", "") or os.path.join(EXPORTS_DIR, "audiobooks")
            voice = req.get("voice", "vi-VN-NamMinhNeural")
            speed = float(req.get("speed", 1.0))
            normalize = bool(req.get("normalize", True))
            resume = bool(req.get("resume", True))

            if not os.path.isdir(input_folder):
                self._send_json({"success": False, "error": "Thư mục nguồn không hợp lệ"}, 400)
                return

            os.makedirs(output_folder, exist_ok=True)

            def run_batch_tts():
                with batch_tts_lock:
                    batch_tts_state["is_running"] = True
                    batch_tts_state["logs"] = []
                    batch_tts_state["progress"] = 0.0
                    batch_tts_state["status_msg"] = "Đang quét danh sách file .txt..."

                try:
                    import re
                    files = [
                        os.path.join(input_folder, f) for f in os.listdir(input_folder)
                        if f.lower().endswith(".txt") and not f.startswith(".")
                    ]
                    def natural_sort_key(s):
                        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
                    files.sort(key=natural_sort_key)

                    total = len(files)
                    if total == 0:
                        with batch_tts_lock:
                            batch_tts_state["status_msg"] = "Không tìm thấy file .txt nào trong thư mục!"
                            batch_tts_state["is_running"] = False
                        return

                    with batch_tts_lock:
                        batch_tts_state["total_files"] = total

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    for i, fpath in enumerate(files, 1):
                        with batch_tts_lock:
                            if not batch_tts_state["is_running"]:
                                break
                            batch_tts_state["current_file"] = os.path.basename(fpath)
                            batch_tts_state["current_index"] = i
                            pct = round(((i - 1) / total) * 100, 1)
                            batch_tts_state["progress"] = pct
                            batch_tts_state["status_msg"] = f"Đang tạo audio: {os.path.basename(fpath)} ({i}/{total})"

                        base_name = os.path.splitext(os.path.basename(fpath))[0]
                        out_mp3 = os.path.join(output_folder, f"{base_name}.mp3")

                        # Smart Resume: Nếu file audio đã tồn tại và có dung lượng hợp lệ (> 1024 bytes), bỏ qua
                        if resume and os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1024:
                            with batch_tts_lock:
                                batch_tts_state["logs"].append(f"⏩ Đã có audio, bỏ qua: {os.path.basename(fpath)}")
                            continue

                        with batch_tts_lock:
                            batch_tts_state["logs"].append(f"[{i}/{total}] Đang đọc {os.path.basename(fpath)}...")

                        try:
                            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read().strip()
                            if not content:
                                continue

                            loop.run_until_complete(
                                tts_engine.synthesize(
                                    content,
                                    voice=voice,
                                    speed=speed,
                                    output_path=out_mp3,
                                    normalize=normalize
                                )
                            )
                        except Exception as file_err:
                            with batch_tts_lock:
                                batch_tts_state["logs"].append(f"⚠️ Lỗi {os.path.basename(fpath)}: {file_err}")

                    loop.close()
                    with batch_tts_lock:
                        if batch_tts_state["is_running"]:
                            batch_tts_state["status_msg"] = f"Hoàn tất! Đã xuất xong vào: {output_folder}"
                            batch_tts_state["progress"] = 100.0
                except Exception as e:
                    with batch_tts_lock:
                        batch_tts_state["status_msg"] = f"Lỗi tiến trình TTS: {str(e)}"
                finally:
                    with batch_tts_lock:
                        batch_tts_state["is_running"] = False

            t = threading.Thread(target=run_batch_tts, daemon=True)
            t.start()
            self._send_json({"success": True, "status": "started"})

        elif path == "/tts/batch_stop":
            with batch_tts_lock:
                batch_tts_state["is_running"] = False
                batch_tts_state["status_msg"] = "Đang dừng tạo audio..."
            self._send_json({"success": True, "status": "stopping"})

        elif path == "/convert/polish":
            text = req.get("text", "")
            mode = req.get("mode", "rules")
            engine = req.get("engine", "deepseek")
            genre = req.get("genre", "xianxia")
            custom_prompt = req.get("prompt", "").strip()

            if not text.strip():
                self._send_json({"result": "", "error": "Văn bản rỗng"})
                return

            start_t = time.time()
            try:
                result = convert_polisher.polish(
                    text=text,
                    mode=mode,
                    engine=engine,
                    genre=genre,
                    dict_entries=dict_mgr.entries,
                    custom_prompt=custom_prompt
                )
                elapsed = time.time() - start_t
                self._send_json({"result": result, "time": round(elapsed, 2)})
            except Exception as e:
                self._send_json({"result": "", "error": str(e)}, 500)

        elif path == "/convert/batch_start":
            input_folder = req.get("input_folder", "")
            output_folder = req.get("output_folder", os.path.join(EXPORTS_DIR, "dich_convert"))
            mode = req.get("mode", "rules")
            engine = req.get("engine", "deepseek")
            genre = req.get("genre", "xianxia")
            suffix = req.get("suffix", "_dich")
            custom_prompt = req.get("prompt", "").strip()
            resume = bool(req.get("resume", True))

            if not os.path.isdir(input_folder):
                self._send_json({"error": "Thư mục nguồn không hợp lệ"}, 400)
                return

            def run_batch_convert():
                with batch_convert_lock:
                    batch_convert_state["is_running"] = True
                    batch_convert_state["logs"] = []
                    batch_convert_state["progress"] = 0.0
                    batch_convert_state["status_msg"] = "Đang chuẩn bị chuyển đổi convert..."

                def status_cb(msg, pct, cur_f, cur_i, total_f):
                    with batch_convert_lock:
                        batch_convert_state["status_msg"] = msg
                        batch_convert_state["progress"] = pct
                        batch_convert_state["current_file"] = cur_f
                        batch_convert_state["current_index"] = cur_i
                        batch_convert_state["total_files"] = total_f
                        batch_convert_state["logs"].append(msg)
                        if len(batch_convert_state["logs"]) > 100:
                            batch_convert_state["logs"].pop(0)

                try:
                    convert_polisher.batch_polish_folder(
                        input_folder=input_folder,
                        output_folder=output_folder,
                        mode=mode,
                        engine=engine,
                        genre=genre,
                        suffix=suffix,
                        custom_prompt=custom_prompt,
                        resume=resume,
                        status_callback=status_cb
                    )
                except Exception as e:
                    with batch_convert_lock:
                        batch_convert_state["status_msg"] = f"Lỗi: {str(e)}"
                finally:
                    with batch_convert_lock:
                        batch_convert_state["is_running"] = False

            t = threading.Thread(target=run_batch_convert, daemon=True)
            t.start()
            self._send_json({"status": "started"})

        elif path == "/convert/batch_stop":
            convert_polisher.stop_batch()
            with batch_convert_lock:
                batch_convert_state["is_running"] = False
                batch_convert_state["status_msg"] = "Đang dừng chuyển đổi..."
            self._send_json({"status": "stopping"})

        elif path == "/convert/save_prompt":
            p = req.get("prompt", "")
            llm_trans.config["convert_system_prompt"] = p
            llm_trans.save_config(llm_trans.config)
            self._send_json({"success": True})

        elif path == "/clean_text":
            text = req.get("text", "")
            remove_watermarks = bool(req.get("remove_watermarks", True))
            start_t = time.time()
            cleaned, count = text_cleaner.clean_all(text, remove_watermarks=remove_watermarks)
            elapsed = time.time() - start_t
            self._send_json({"result": cleaned, "count": count, "time": round(elapsed, 3)})

        elif path == "/clean_folder":
            input_folder = req.get("input_folder", "")
            output_folder = req.get("output_folder", os.path.join(EXPORTS_DIR, "cleaned_novels"))
            suffix = req.get("suffix", "_clean")
            remove_watermarks = bool(req.get("remove_watermarks", True))

            if not os.path.isdir(input_folder):
                self._send_json({"error": "Thư mục nguồn không hợp lệ"}, 400)
                return

            def run_clean_folder():
                with clean_folder_lock:
                    clean_folder_state["is_running"] = True
                    clean_folder_state["logs"] = []
                    clean_folder_state["progress"] = 0.0
                    clean_folder_state["status_msg"] = "Đang chuẩn bị làm sạch..."

                def status_cb(msg, pct, cur_f, cur_i, total_f):
                    with clean_folder_lock:
                        clean_folder_state["status_msg"] = msg
                        clean_folder_state["progress"] = pct
                        clean_folder_state["current_file"] = cur_f
                        clean_folder_state["current_index"] = cur_i
                        clean_folder_state["total_files"] = total_f
                        clean_folder_state["logs"].append(msg)
                        if len(clean_folder_state["logs"]) > 100:
                            clean_folder_state["logs"].pop(0)

                try:
                    text_cleaner.clean_folder(
                        input_folder=input_folder,
                        output_folder=output_folder,
                        suffix=suffix,
                        remove_watermarks=remove_watermarks,
                        status_callback=status_cb
                    )
                except Exception as e:
                    with clean_folder_lock:
                        clean_folder_state["status_msg"] = f"Lỗi: {str(e)}"
                finally:
                    with clean_folder_lock:
                        clean_folder_state["is_running"] = False

            t = threading.Thread(target=run_clean_folder, daemon=True)
            t.start()
            self._send_json({"status": "started"})

        elif path == "/clean_folder_stop":
            text_cleaner.stop()
            with clean_folder_lock:
                clean_folder_state["is_running"] = False
                clean_folder_state["status_msg"] = "Đang dừng làm sạch..."
            self._send_json({"status": "stopping"})

        elif path == "/glossary/extract":
            text = req.get("text", "")
            method = req.get("method", "auto") # auto, rule, llm
            engine = req.get("engine", "gemini")
            min_count = int(req.get("min_count", 1))

            if not text.strip():
                self._send_json({"entities": [], "count": 0})
                return

            try:
                if method == "llm":
                    entities = glossary_extractor.extract_with_llm(text, engine=engine)
                elif method == "auto":
                    # Tự động: nếu có key thì dùng LLM, nếu không dùng rule
                    cfg = llm_trans.load_config()
                    has_key = bool(cfg.get("gemini_api_key")) or bool(cfg.get("deepseek_api_key"))
                    if has_key:
                        entities = glossary_extractor.extract_with_llm(text, engine=engine)
                    else:
                        entities = glossary_extractor.extract_candidates_rule_based(text, min_count=min_count)
                else:
                    entities = glossary_extractor.extract_candidates_rule_based(text, min_count=min_count)

                self._send_json({"entities": entities, "count": len(entities)})
            except Exception as e:
                self._send_json({"error": str(e), "entities": [], "count": 0}, 500)

        elif path == "/glossary/batch_add":
            entries = req.get("entries", [])
            if not isinstance(entries, list):
                self._send_json({"error": "Dữ liệu không hợp lệ"}, 400)
                return

            added = glossary_extractor.add_to_names(entries)
            # Nạp lại từ điển vào bộ nhớ
            dict_mgr.load()
            self._send_json({"success": True, "added": added, "total": len(dict_mgr.entries)})

        elif path == "/glossary/lookup":
            term = req.get("text", "").strip()
            hv = glossary_extractor.to_hanviet(term)
            in_dict = term in dict_mgr.entries
            val = dict_mgr.entries.get(term, "")
            self._send_json({
                "term": term,
                "hanviet": hv,
                "in_dict": in_dict,
                "dict_val": val
            })

        elif path == "/bilingual/align":
            src_text = req.get("src", "")
            tgt_text = req.get("tgt", "")

            src_paras = [p.strip() for p in src_text.split("\n") if p.strip()]
            tgt_paras = [p.strip() for p in tgt_text.split("\n") if p.strip()]
            max_p = max(len(src_paras), len(tgt_paras))

            pairs = []
            for i in range(max_p):
                s_para = src_paras[i] if i < len(src_paras) else ""
                t_para = tgt_paras[i] if i < len(tgt_paras) else ""
                hv_para = glossary_extractor.to_hanviet(s_para) if s_para else ""
                pairs.append({
                    "index": i + 1,
                    "src": s_para,
                    "hanviet": hv_para,
                    "tgt": t_para
                })
            self._send_json({"pairs": pairs, "count": len(pairs)})

        else:
            self._send_json({"error": "Not found"}, 404)

def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), BridgeHandler)
    server.daemon_threads = True
    print(f"Bridge server running on http://127.0.0.1:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
