import os
import re
import json
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable, Dict, Any, List, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

try:
    from llm_translator import LLMTranslator
    from text_cleaner import text_cleaner
    from fanqie_decoder import is_fanqie_url, parse_fanqie_chapter, extract_fanqie_toc, resolve_fanqie_first_chapter
    from sangtacviet_resolver import is_sangtacviet_url, resolve_sangtacviet_url
except ImportError:
    from mac_tool.llm_translator import LLMTranslator
    from mac_tool.text_cleaner import text_cleaner
    from mac_tool.fanqie_decoder import is_fanqie_url, parse_fanqie_chapter, extract_fanqie_toc, resolve_fanqie_first_chapter
    from mac_tool.sangtacviet_resolver import is_sangtacviet_url, resolve_sangtacviet_url

# Presets cho các website truyện phổ biến
POPULAR_PRESETS = {
    "sangtacviet.app": {
        "name": "sangtacviet.app (Tự động chuyển nguồn gốc Fanqie/69shu/UU...)",
        "title_selector": "h1, .chapter-title",
        "content_selector": "#maincontent, .contentbox",
        "exclude_selector": "",
        "next_selector": "",
        "toc_selector": ""
    },
    "fanqienovel.com": {
        "name": "fanqienovel.com (番茄小说 - Fanqie / Cà Chua)",
        "title_selector": "h1, .chapter-title",
        "content_selector": ".muye-reader-content",
        "exclude_selector": "",
        "next_selector": "",
        "toc_selector": ""
    },
    "tvtruyen.live": {
        "name": "tvtruyen.live (Truyện TV - Full Tiếng Việt)",
        "title_selector": "a.chapter-title, .chapter-title, h1",
        "content_selector": "#chapter-content, div.chapter-content",
        "exclude_selector": ".signature, .ads, .highlight-box, ins.adsbygoogle",
        "next_selector": "#next_chap, a#next_chap, a.chapter-modal-next",
        "toc_selector": "#list-chapter a, a[href*='chuong-']"
    },
    "truyenhoan.com": {
        "name": "truyenhoan.com (Truyện Hoàn - Full Tiếng Việt)",
        "title_selector": "a.chapter-title, .chapter-title",
        "content_selector": "#chapter-c, div.chapter-c",
        "exclude_selector": ".ads, .highlight-box, .list-tags, ins.adsbygoogle",
        "next_selector": "#next_chap, a#next_chap",
        "toc_selector": "#list-chapter a, .list-chapter a, a[href*='chuong-']"
    },
    "ihuliwang.net": {
        "name": "ihuliwang.net (Hồ Ly Mạng)",
        "title_selector": "div.pt-read-title > h1, h1",
        "content_selector": "div.pt-read-text, div.size16.color5.pt-read-text",
        "exclude_selector": ".pt-read-text p:last-child",
        "next_selector": "a.pt-nextchapter",
        "toc_selector": ".pt-chapter-cont a, .pt-dir-list a"
    },
    "69shu.me": {
        "name": "69shu (69 Thư Ba)",
        "title_selector": "div.txtnav > h1, h1",
        "content_selector": "div.txtnav, #content",
        "exclude_selector": ".bottom-ad, .read-nav",
        "next_selector": "a:contains('下一章'), a.next, #next_url",
        "toc_selector": ".catalog a, #catalog a, .mulu a"
    },
    "biquge": {
        "name": "biquge (Bút Khúc Các / 5200)",
        "title_selector": ".bookname > h1, h1",
        "content_selector": "#content",
        "exclude_selector": "p.read_btn, .bottem",
        "next_selector": "a:contains('下一章'), #next_url, .bottem2 a:last-child",
        "toc_selector": "#list dd a, #list a"
    },
    "uukanshu": {
        "name": "uukanshu (UU Đọc Sách)",
        "title_selector": "h1#timu, h1",
        "content_selector": "div#contentbox, .readcotent",
        "exclude_selector": ".ad_content",
        "next_selector": "a#next, a:contains('下一章')",
        "toc_selector": "#chapterList a, .chapter-list a"
    },
    "custom": {
        "name": "Tùy chỉnh (Nhập CSS Selector riêng)",
        "title_selector": "",
        "content_selector": "",
        "exclude_selector": "",
        "next_selector": "",
        "toc_selector": ""
    }
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,vi;q=0.6",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def clean_filename(s: str) -> str:
    """Loại bỏ các ký tự không hợp lệ trong tên file của hệ điều hành."""
    s = re.sub(r'[\\/*?:"<>|]', "", s)
    s = s.strip()
    return s[:120] if len(s) > 120 else s

def resolve_first_chapter_url(url: str) -> str:
    """Nếu người dùng dán link trang truyện (thay vì link chương 1), tự động tìm link chương 1."""
    if is_sangtacviet_url(url):
        origin, _, _ = resolve_sangtacviet_url(url)
        if origin != url:
            url = origin
    if is_fanqie_url(url):
        try:
            return resolve_fanqie_first_chapter(url)
        except Exception:
            return url
    if "truyenhoan.com" in url and "chuong-" not in url:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select('a[href*="chuong-"]'):
                href = a.get('href', '')
                if 'chuong-1.' in href or 'chuong-1/' in href:
                    return urljoin(url, href)
            links = [a.get('href') for a in soup.select('a[href*="chuong-"]') if a.get('href')]
            if links:
                return urljoin(url, links[-1])
        except Exception:
            pass
    elif "tvtruyen.live" in url and "chuong-" not in url:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select('a[href*="chuong-"]'):
                href = a.get('href', '')
                text = a.get_text(strip=True)
                if 'chuong-1-' in href or 'chuong-1/' in href or 'chuong-1.' in href or text.startswith('Chương 1') or 'Chương 1' in text:
                    return urljoin(url, href)
            links = [a.get('href') for a in soup.select('a[href*="chuong-"]') if a.get('href')]
            if links:
                return urljoin(url, links[0])
        except Exception:
            pass
    return url

def get_existing_chapter_indices(save_folder: str) -> Set[int]:
    """Tìm các chỉ số chương đã được cào về thư mục."""
    indices = set()
    if not os.path.exists(save_folder):
        return indices
    for f in os.listdir(save_folder):
        if f.endswith(".txt") and not f.startswith("."):
            m = re.match(r"^(\d+)_", f)
            if m:
                indices.add(int(m.group(1)))
    return indices

def save_crawler_state(save_folder: str, state: Dict[str, Any]):
    state_file = os.path.join(save_folder, ".crawler_state.json")
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_crawler_state(save_folder: str) -> Optional[Dict[str, Any]]:
    state_file = os.path.join(save_folder, ".crawler_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

class NovelScraper:
    def __init__(self, translator=None):
        self.translator = translator
        self.llm_translator = LLMTranslator()
        self.is_running = False
        self.should_stop = False
        self.current_job: Dict[str, Any] = {
            "is_running": False,
            "current_chapter": 0,
            "current_title": "",
            "current_url": "",
            "total_scraped": 0,
            "total_chapters": 0,
            "progress": 0.0,
            "status_msg": "Sẵn sàng",
            "logs": []
        }
        self.lock = threading.Lock()

    def _log(self, msg: str):
        with self.lock:
            ts = time.strftime("%H:%M:%S")
            line = f"[{ts}] {msg}"
            self.current_job["logs"].append(line)
            if len(self.current_job["logs"]) > 250:
                self.current_job["logs"].pop(0)
            self.current_job["status_msg"] = msg

    def fetch_page(self, url: str) -> str:
        """Tải mã nguồn HTML với tự động nhận diện bảng mã (GBK/GB18030/UTF-8)."""
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        resp.raise_for_status()

        content_bytes = resp.content
        for enc in ["utf-8", "gb18030", "gbk", "big5", "utf-16"]:
            try:
                return content_bytes.decode(enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return content_bytes.decode("utf-8", errors="ignore")

    def parse_chapter(self, html: str, current_url: str, title_sel: str, content_sel: str, exclude_sel: str = "", next_sel: str = "") -> Dict[str, Any]:
        """Trích xuất tiêu đề, nội dung và link chương tiếp theo từ HTML."""
        if is_sangtacviet_url(current_url):
            origin, _, _ = resolve_sangtacviet_url(current_url)
            if origin != current_url:
                current_url = origin
                try:
                    html = self.fetch_page(current_url)
                except Exception:
                    pass

        if is_fanqie_url(current_url):
            try:
                res = parse_fanqie_chapter(html, current_url)
                if res.get("content"):
                    res["content"], _ = text_cleaner.clean_all(res["content"])
                return res
            except Exception:
                pass

        soup = BeautifulSoup(html, "lxml")

        # 1. Loại bỏ các phần tử rác / quảng cáo
        if exclude_sel:
            for ex in soup.select(exclude_sel):
                ex.decompose()
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # 2. Tiêu đề chương
        title = ""
        if title_sel:
            t_elem = soup.select_one(title_sel)
            if t_elem:
                title = t_elem.get_text().strip()
        if not title:
            h1 = soup.find("h1")
            title = h1.get_text().strip() if h1 else (soup.title.string.strip() if soup.title else "Chương không tên")

        # 3. Nội dung chương
        content_text = ""
        if content_sel:
            c_elem = soup.select_one(content_sel)
            if c_elem:
                for br in c_elem.find_all("br"):
                    br.replace_with("\n")
                for p in c_elem.find_all("p"):
                    p.insert_after("\n\n")
                content_text = c_elem.get_text()

        if not content_text:
            candidate = soup.find(id=re.compile(r"content|chaptercontent|BookText", re.I))
            if candidate:
                content_text = candidate.get_text("\n\n")

        lines = [line.strip() for line in content_text.split("\n")]
        lines = [l for l in lines if l]
        cleaned_content = "\n\n".join(lines)
        cleaned_content, _ = text_cleaner.clean_all(cleaned_content)

        # 4. Link chương tiếp theo
        next_url = ""
        if next_sel:
            if ":contains" in next_sel:
                for a_tag in soup.find_all("a"):
                    if "下一章" in a_tag.get_text() or "下一页" in a_tag.get_text():
                        href = a_tag.get("href")
                        if href and not href.startswith("javascript"):
                            next_url = urljoin(current_url, href)
                            break
            else:
                n_elem = soup.select_one(next_sel)
                if n_elem and n_elem.get("href"):
                    classes = n_elem.get("class", [])
                    if isinstance(classes, str):
                        classes = classes.split()
                    if "disabled" not in classes:
                        href = n_elem.get("href")
                        if href and not href.startswith("javascript"):
                            next_url = urljoin(current_url, href)

        if not next_url:
            for a_tag in soup.find_all("a"):
                text = a_tag.get_text()
                if "下一章" in text or "next" in text.lower() or "chương tiếp" in text.lower():
                    classes = a_tag.get("class", [])
                    if isinstance(classes, str):
                        classes = classes.split()
                    if "disabled" not in classes:
                        href = a_tag.get("href")
                        if href and not href.startswith("javascript"):
                            next_url = urljoin(current_url, href)
                            break

        if next_url:
            parsed_curr = urlparse(current_url)
            parsed_next = urlparse(next_url)
            if parsed_next.path in ["", "/", "/index.html", "/index.php", parsed_curr.path]:
                next_url = ""
            if "chuong-" in parsed_curr.path and "chuong-" not in parsed_next.path:
                next_url = ""

        return {
            "title": title,
            "content": cleaned_content,
            "next_url": next_url
        }

    def extract_toc(self, url: str, toc_selector: str = "") -> List[Dict[str, Any]]:
        """Lấy danh sách các chương từ trang mục lục."""
        if is_sangtacviet_url(url):
            origin, _, _ = resolve_sangtacviet_url(url)
            if origin != url:
                url = origin

        if is_fanqie_url(url):
            try:
                chapters = extract_fanqie_toc(url, fetch_page_func=self.fetch_page)
                if chapters:
                    return chapters
            except Exception:
                pass

        html = self.fetch_page(url)
        soup = BeautifulSoup(html, "lxml")
        chapters = []
        seen_urls = set()

        links = []
        if toc_selector:
            links = soup.select(toc_selector)

        if not links:
            # Tự động dò tìm các thẻ a chứa link chương
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if any(k in href for k in ["chuong-", "read/", ".html", "chapter"]):
                    if any(k in text for k in ["Chương", "chuong", "第", "Hồi", "tiết", "Quyển"]) or re.search(r'^\d+', text):
                        links.append(a)

        idx = 1
        for a in links:
            href = a.get("href")
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            full_url = urljoin(url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            chapters.append({
                "index": idx,
                "title": title,
                "url": full_url
            })
            idx += 1

        return chapters

    def test_single_chapter(self, url: str, title_sel: str, content_sel: str, exclude_sel: str = "", next_sel: str = "") -> Dict[str, Any]:
        """Kiểm tra thử 1 chương trước khi cào hàng loạt."""
        try:
            url = resolve_first_chapter_url(url)
            html = self.fetch_page(url)
            parsed = self.parse_chapter(html, url, title_sel, content_sel, exclude_sel, next_sel)
            sample_content = parsed["content"][:400] + ("..." if len(parsed["content"]) > 400 else "")
            return {
                "success": True,
                "title": parsed["title"],
                "content_preview": sample_content,
                "content_length": len(parsed["content"]),
                "next_url": parsed["next_url"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _translate_chapter(self, text: str, model_name: str, beam: int, batch: int, opencc: bool) -> str:
        """Thực hiện dịch tự động bằng Offline model hoặc LLM."""
        if not text.strip():
            return ""

        # Nếu chọn LLM (Gemini hoặc DeepSeek)
        if "gemini" in model_name.lower() or "deepseek" in model_name.lower():
            dict_entries = self.translator.dict_manager.entries if self.translator and self.translator.dict_manager else None
            return self.llm_translator.translate(text, engine=model_name, dict_entries=dict_entries)

        # Nếu chọn Offline MarianMT
        if self.translator:
            self.translator.opencc_enabled = opencc
            if self.translator.current_model_key != model_name or self.translator.translator is None:
                self.translator.load_model(model_name)
            return self.translator.translate_text(text, beam_size=beam, batch_size=batch)

        return text

    def start_scraping(
        self,
        start_url: str,
        save_folder: str,
        title_sel: str,
        content_sel: str,
        exclude_sel: str = "",
        next_sel: str = "",
        wait_min: float = 0.5,
        wait_max: float = 1.5,
        max_chapters: int = 0,
        auto_translate: bool = False,
        trans_model: str = "",
        trans_beam: int = 2,
        trans_batch: int = 16,
        trans_opencc: bool = True,
        mode: str = "sequential",
        concurrency: int = 4,
        resume: bool = True,
        toc_sel: str = ""
    ):
        """Khởi chạy tiến trình cào truyện (hỗ trợ cả tuần tự và đa luồng TOC)."""
        if self.is_running:
            return {"error": "Tiến trình cào truyện đang chạy"}

        os.makedirs(save_folder, exist_ok=True)
        if auto_translate:
            trans_folder = os.path.join(save_folder, "dich_tieng_viet")
            os.makedirs(trans_folder, exist_ok=True)
        else:
            trans_folder = ""

        self.is_running = True
        self.should_stop = False

        initial_log = f"Bắt đầu tiến trình cào (Chế độ: {mode})"
        if is_sangtacviet_url(start_url):
            origin, host, msg = resolve_sangtacviet_url(start_url)
            if origin != start_url:
                start_url = origin
                initial_log = f"🔗 {msg}"

        with self.lock:
            self.current_job = {
                "is_running": True,
                "current_chapter": 0,
                "current_title": "",
                "current_url": start_url,
                "total_scraped": 0,
                "total_chapters": 0,
                "progress": 0.0,
                "status_msg": "Đang chuẩn bị...",
                "logs": [initial_log]
            }

        target_worker = self._worker_toc if mode == "toc" else self._worker_sequential
        args = (start_url, save_folder, trans_folder, title_sel, content_sel, exclude_sel, next_sel,
                wait_min, wait_max, max_chapters, auto_translate, trans_model, trans_beam, trans_batch,
                trans_opencc, concurrency, resume, toc_sel)

        thread = threading.Thread(target=target_worker, args=args, daemon=True)
        thread.start()
        return {"status": "started"}

    def stop_scraping(self):
        """Yêu cầu dừng tiến trình cào."""
        self.should_stop = True
        self._log("Đã gửi yêu cầu dừng cào truyện...")
        return {"status": "stopping"}

    def _worker_sequential(
        self,
        start_url: str,
        save_folder: str,
        trans_folder: str,
        title_sel: str,
        content_sel: str,
        exclude_sel: str,
        next_sel: str,
        wait_min: float,
        wait_max: float,
        max_chapters: int,
        auto_translate: bool,
        trans_model: str,
        trans_beam: int,
        trans_batch: int,
        trans_opencc: bool,
        concurrency: int,
        resume: bool,
        toc_sel: str
    ):
        """Cào tuần tự qua nút Next Chương (có hỗ trợ Resume tự động)."""
        current_url = start_url
        chapter_idx = 1
        existing_indices = get_existing_chapter_indices(save_folder) if resume else set()

        # Kiểm tra trạng thái đã lưu để tiếp tục
        if resume:
            state = load_crawler_state(save_folder)
            if state and state.get("next_url") and state.get("last_chapter_idx"):
                resumed_url = state["next_url"]
                resumed_idx = state["last_chapter_idx"] + 1
                self._log(f"🔄 Phát hiện tiến trình cũ: Tự động tiếp tục từ chương {resumed_idx} ({resumed_url})")
                current_url = resumed_url
                chapter_idx = resumed_idx

        if not current_url:
            current_url = resolve_first_chapter_url(start_url)

        total_scraped = 0
        try:
            while current_url and not self.should_stop:
                if max_chapters > 0 and chapter_idx > max_chapters:
                    self._log(f"Đã đạt giới hạn {max_chapters} chương. Hoàn tất!")
                    break

                # Bỏ qua nếu chương này đã tải trước đó
                if resume and chapter_idx in existing_indices:
                    self._log(f"⏩ Đã có chương {chapter_idx}, đang tìm chương tiếp theo...")
                    try:
                        html = self.fetch_page(current_url)
                        parsed = self.parse_chapter(html, current_url, title_sel, content_sel, exclude_sel, next_sel)
                        current_url = parsed["next_url"]
                        chapter_idx += 1
                        continue
                    except Exception:
                        pass

                self._log(f"Đang tải chương {chapter_idx}: {current_url}")
                try:
                    html = self.fetch_page(current_url)
                    parsed = self.parse_chapter(html, current_url, title_sel, content_sel, exclude_sel, next_sel)
                except Exception as e:
                    self._log(f"Lỗi tải chương {chapter_idx} ({current_url}): {e}")
                    time.sleep(3)
                    break

                title = parsed["title"] or f"Chương {chapter_idx}"
                content = parsed["content"]
                next_url = parsed["next_url"]

                if not content:
                    self._log(f"Cảnh báo: Chương {chapter_idx} ({title}) không tìm thấy nội dung.")

                # Lưu file gốc
                clean_t = clean_filename(title)
                filename = f"{chapter_idx:04d}_{clean_t}.txt"
                zh_filepath = os.path.join(save_folder, filename)
                full_text = f"{title}\n\n{content}"

                with open(zh_filepath, "w", encoding="utf-8") as f:
                    f.write(full_text)

                total_scraped += 1
                self._log(f"✓ Đã lưu chương {chapter_idx}: {filename} ({len(content)} ký tự)")

                # Dịch tự động nếu được bật
                if auto_translate and content:
                    self._log(f"⚡ Đang dịch chương {chapter_idx} ({trans_model or 'offline'})...")
                    try:
                        trans_text = self._translate_chapter(full_text, trans_model, trans_beam, trans_batch, trans_opencc)
                        vi_filename = f"{chapter_idx:04d}_{clean_t}_viet.txt"
                        vi_filepath = os.path.join(trans_folder, vi_filename)
                        with open(vi_filepath, "w", encoding="utf-8") as f:
                            f.write(trans_text)
                        self._log(f"🇻🇳 Đã dịch xong chương {chapter_idx} -> {vi_filename}")
                    except Exception as te:
                        self._log(f"Lỗi dịch chương {chapter_idx}: {te}")

                # Cập nhật trạng thái và lưu checkpoint
                with self.lock:
                    self.current_job["current_chapter"] = chapter_idx
                    self.current_job["current_title"] = title
                    self.current_job["current_url"] = current_url
                    self.current_job["total_scraped"] = total_scraped

                save_crawler_state(save_folder, {
                    "last_chapter_idx": chapter_idx,
                    "last_url": current_url,
                    "next_url": next_url,
                    "updated_at": time.time()
                })

                if not next_url:
                    self._log("Không tìm thấy link tiếp theo (Đã đến chương cuối hoặc hết truyện).")
                    break

                chapter_idx += 1
                current_url = next_url
                time.sleep(random.uniform(wait_min, wait_max))

            if self.should_stop:
                self._log("Đã dừng tiến trình cào theo yêu cầu người dùng.")
            else:
                self._log(f"Hoàn thành! Đã cào tổng cộng {total_scraped} chương mới.")

        except Exception as e:
            self._log(f"Lỗi trong quá trình cào: {e}")
        finally:
            self.is_running = False
            with self.lock:
                self.current_job["is_running"] = False

    def _worker_toc(
        self,
        start_url: str,
        save_folder: str,
        trans_folder: str,
        title_sel: str,
        content_sel: str,
        exclude_sel: str,
        next_sel: str,
        wait_min: float,
        wait_max: float,
        max_chapters: int,
        auto_translate: bool,
        trans_model: str,
        trans_beam: int,
        trans_batch: int,
        trans_opencc: bool,
        concurrency: int,
        resume: bool,
        toc_sel: str
    ):
        """Cào đa luồng siêu tốc theo danh sách Mục Lục (TOC)."""
        self._log(f"🔍 Đang quét danh sách chương từ mục lục: {start_url}")
        try:
            chapters = self.extract_toc(start_url, toc_selector=toc_sel)
        except Exception as e:
            self._log(f"Lỗi khi đọc mục lục: {e}")
            self.is_running = False
            return

        if not chapters:
            self._log("Không tìm thấy chương nào trong mục lục! Đang chuyển sang cào tuần tự...")
            self._worker_sequential(
                start_url, save_folder, trans_folder, title_sel, content_sel, exclude_sel, next_sel,
                wait_min, wait_max, max_chapters, auto_translate, trans_model, trans_beam, trans_batch,
                trans_opencc, concurrency, resume, toc_sel
            )
            return

        if max_chapters > 0:
            chapters = chapters[:max_chapters]

        total_total = len(chapters)
        self._log(f"📋 Tìm thấy {total_total} chương trong mục lục.")

        existing_indices = get_existing_chapter_indices(save_folder) if resume else set()
        to_download = [c for c in chapters if c["index"] not in existing_indices]

        if resume and len(to_download) < total_total:
            self._log(f"🔄 Đã có {total_total - len(to_download)} chương sẵn có. Cần tải thêm {len(to_download)} chương.")

        with self.lock:
            self.current_job["total_chapters"] = total_total

        def download_single_chapter(item):
            if self.should_stop:
                return None
            idx = item["index"]
            c_url = item["url"]
            try:
                html = self.fetch_page(c_url)
                parsed = self.parse_chapter(html, c_url, title_sel, content_sel, exclude_sel, next_sel)
                t = parsed["title"] or item["title"] or f"Chương {idx}"
                cnt = parsed["content"]

                clean_t = clean_filename(t)
                filename = f"{idx:04d}_{clean_t}.txt"
                zh_path = os.path.join(save_folder, filename)
                full_text = f"{t}\n\n{cnt}"

                with open(zh_path, "w", encoding="utf-8") as f:
                    f.write(full_text)

                if auto_translate and cnt:
                    trans_text = self._translate_chapter(full_text, trans_model, trans_beam, trans_batch, trans_opencc)
                    vi_filename = f"{idx:04d}_{clean_t}_viet.txt"
                    vi_path = os.path.join(trans_folder, vi_filename)
                    with open(vi_path, "w", encoding="utf-8") as f:
                        f.write(trans_text)

                return idx, t, len(cnt)
            except Exception as e:
                return idx, None, str(e)

        completed_count = total_total - len(to_download)
        max_workers = max(1, min(concurrency, 10))
        self._log(f"🚀 Bắt đầu cào đa luồng với {max_workers} worker song song...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {executor.submit(download_single_chapter, item): item for item in to_download}
            for future in as_completed(future_to_item):
                if self.should_stop:
                    break
                res = future.result()
                if res and res[1] is not None:
                    idx, t, length = res
                    completed_count += 1
                    with self.lock:
                        self.current_job["current_chapter"] = idx
                        self.current_job["current_title"] = t
                        self.current_job["total_scraped"] = completed_count
                        self.current_job["progress"] = round((completed_count / total_total) * 100, 1)

                    self._log(f"[{completed_count}/{total_total}] ✓ Hoàn thành chương {idx}: {t} ({length} ký tự)")
                elif res and res[1] is None:
                    idx, _, err = res
                    self._log(f"Lỗi tải chương {idx}: {err}")

        save_crawler_state(save_folder, {
            "last_chapter_idx": completed_count,
            "total_chapters": total_total,
            "updated_at": time.time()
        })

        self.is_running = False
        with self.lock:
            self.current_job["is_running"] = False
        self._log(f"🎉 Hoàn thành cào đa luồng! Tổng cộng {completed_count}/{total_total} chương.")
