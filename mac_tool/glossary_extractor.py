import os
import re
import json
from collections import Counter
from typing import Dict, List, Any, Optional, Tuple

try:
    import jieba
    import jieba.posseg as pseg
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HANVIET_PATH = os.path.join(BASE_DIR, "hanviet_dict.json")
NAMES_PATH = os.path.join(BASE_DIR, "names.txt")
BUILTIN_XIANXIA_PATH = os.path.join(BASE_DIR, "builtin_xianxia.txt")

SINGLE_SURNAMES = set(
    "李王张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文"
)
DOUBLE_SURNAMES = [
    "欧阳", "司徒", "上官", "诸葛", "司马", "皇甫", "独孤", "南宫",
    "令狐", "东方", "西门", "慕容", "尉迟", "轩辕", "宇文", "百里",
    "呼延", "端木", "赫连", "钟离", "闻人", "拓跋", "申屠", "公孙"
]

SECT_SUFFIXES = ["宗", "派", "门", "殿", "阁", "宫", "谷", "峰", "楼", "院", "府", "帮", "会", "盟", "世家", "圣地", "神教", "古族", "王朝", "皇朝"]
PLACE_SUFFIXES = ["城", "界", "域", "大陆", "州", "神山", "古星", "禁区", "深渊", "古道", "圣域", "遗迹", "祖地", "海域"]
ITEM_SUFFIXES = ["剑", "刀", "枪", "戟", "鼎", "钟", "塔", "镜", "印", "炉", "盘", "幡", "经", "诀", "典", "术", "功", "真经", "大阵", "异火", "灵丹", "神药", "圣水"]
TITLE_SUFFIXES = ["宗主", "门主", "长老", "师尊", "师父", "师兄", "师弟", "师姐", "师妹", "弟子", "仙子", "仙尊", "圣子", "圣女", "神子", "神女", "帝尊", "天皇", "大帝", "尊者", "老祖", "宫主", "殿主", "皇子", "公主", "族长", "家主", "掌门", "道友", "前辈", "城主"]

TRAILING_PARTICLES = set("也与和同及并了的着在于中后前出入走到看说笑道深很极甚已即乃又")
PREFIX_PARTICLES = ["的", "了", "在", "于", "是", "有", "一", "把", "个", "前", "后", "与", "和", "到", "被", "从", "向", "自", "中", "上", "下", "及", "乃", "为", "传闻", "名曰", "所谓", "进入", "来到", "只见", "看着", "此时", "手中"]

class GlossaryExtractor:
    def __init__(self):
        self.hanviet_dict: Dict[str, str] = {}
        self.load_hanviet_dict()

    def load_hanviet_dict(self):
        if os.path.isfile(HANVIET_PATH):
            try:
                with open(HANVIET_PATH, "r", encoding="utf-8") as f:
                    self.hanviet_dict = json.load(f)
            except Exception as e:
                print(f"Lỗi tải hanviet_dict.json: {e}")

    def to_hanviet(self, chinese_text: str) -> str:
        """Chuyển một cụm từ tiếng Trung sang phiên âm Hán-Việt viết hoa chuẩn mực."""
        words = []
        for char in chinese_text:
            hv = self.hanviet_dict.get(char)
            if hv:
                words.append(hv.capitalize())
            else:
                words.append(char)
        return " ".join(words)

    def load_existing_names(self) -> set:
        existing = set()
        for p in [NAMES_PATH, BUILTIN_XIANXIA_PATH]:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            src, _ = line.split("=", 1)
                            existing.add(src.strip())
        return existing

    def clean_term(self, t: str) -> str:
        t = t.strip()
        for p in sorted(PREFIX_PARTICLES, key=len, reverse=True):
            if t.startswith(p):
                t = t[len(p):].strip()
        while len(t) > 2 and t[-1] in TRAILING_PARTICLES:
            t = t[:-1]
        return t

    def extract_candidates_rule_based(self, text: str, min_count: int = 1) -> List[Dict[str, Any]]:
        """Trích xuất thực thể bằng jieba POS + quy tắc ngôn ngữ học."""
        existing = self.load_existing_names()
        results: List[Dict[str, Any]] = []
        seen_terms = set()

        person_candidates = Counter()
        sect_candidates = Counter()
        place_candidates = Counter()
        item_candidates = Counter()

        # 1. Quét bằng Jieba nếu có
        if HAS_JIEBA:
            try:
                words = list(pseg.cut(text))
                for i, (w, flag) in enumerate(words):
                    w_clean = self.clean_term(w)
                    if not w_clean or len(w_clean) < 2:
                        continue
                    if flag == "nr":
                        # Tên người
                        if 2 <= len(w_clean) <= 4:
                            person_candidates[w_clean] += 2
                    elif flag in ["ns", "s"]:
                        # Địa danh
                        if 2 <= len(w_clean) <= 6:
                            place_candidates[w_clean] += 1
                    elif flag == "nt":
                        # Tổ chức / Tông môn
                        if 2 <= len(w_clean) <= 6:
                            sect_candidates[w_clean] += 2
                    elif flag == "nz":
                        # Danh từ riêng khác / Bảo vật
                        if 2 <= len(w_clean) <= 6:
                            item_candidates[w_clean] += 1
            except Exception:
                pass

        # 2. Bổ sung bằng Pattern matching nâng cao
        # Họ kép
        for d_sur in DOUBLE_SURNAMES:
            pattern = re.compile(rf"({d_sur}[\u4e00-\u9fa5]{{1,2}})")
            for m in pattern.finditer(text):
                w = self.clean_term(m.group(1))
                if 3 <= len(w) <= 4:
                    person_candidates[w] += 2

        # Họ đơn kèm danh xưng (ví dụ: 叶凡, 萧炎, 陆玄机)
        for sur in SINGLE_SURNAMES:
            for title in TITLE_SUFFIXES:
                pattern = re.compile(rf"({sur}[\u4e00-\u9fa5]{{1,2}})(?:{title})")
                for m in pattern.finditer(text):
                    w = self.clean_term(m.group(1))
                    if 2 <= len(w) <= 3:
                        person_candidates[w] += 3

        # Quét họ đơn trong câu (chặn ký tự nối)
        for sur in SINGLE_SURNAMES:
            pattern = re.compile(rf"(?<=[\s，。！？、“”\n\r])({sur}[\u4e00-\u9fa5]{{1,2}})(?=[\s，。！？、“”\n\r与和同说看道走笑来去])")
            for m in pattern.finditer(text):
                w = self.clean_term(m.group(1))
                if 2 <= len(w) <= 3:
                    person_candidates[w] += 1

        # Tông môn
        for suf in SECT_SUFFIXES:
            pattern = re.compile(rf"([\u4e00-\u9fa5]{{2,4}}{suf})")
            for m in pattern.finditer(text):
                w = self.clean_term(m.group(1))
                if 2 <= len(w) <= 6:
                    sect_candidates[w] += 1

        # Địa danh
        for suf in PLACE_SUFFIXES:
            pattern = re.compile(rf"([\u4e00-\u9fa5]{{2,4}}{suf})")
            for m in pattern.finditer(text):
                w = self.clean_term(m.group(1))
                if 2 <= len(w) <= 6:
                    place_candidates[w] += 1

        # Pháp bảo / Công pháp
        for suf in ITEM_SUFFIXES:
            pattern = re.compile(rf"([\u4e00-\u9fa5]{{2,4}}{suf})")
            for m in pattern.finditer(text):
                w = self.clean_term(m.group(1))
                if 2 <= len(w) <= 6:
                    item_candidates[w] += 1

        stopwords = {
            "什么", "怎么", "可以", "如果", "虽然", "但是", "因为", "所以", "这个时候", "一个",
            "那个", "自己", "知道", "看到", "听到", "说到", "出现", "发现", "明白", "觉得",
            "没有", "不是", "就是", "还有", "然后", "接着", "最后", "开始", "结束", "现在",
            "长老", "宗主", "弟子", "师兄", "师弟", "师姐", "师妹", "仙子", "大帝", "老祖",
            "传闻", "神色", "三人", "各自", "纷纷", "现身", "强者", "修为", "通天", "深吸一口气",
            "凝重", "身后", "眼前", "过来", "手中", "各自", "一把", "走了", "吸了", "一口气"
        }

        def add_category(counter_obj: Counter, category_name: str, threshold: int):
            for raw_term, cnt in counter_obj.most_common(50):
                term = self.clean_term(raw_term)
                if cnt < threshold:
                    continue
                if term in existing or term in seen_terms:
                    continue
                if any(sw == term for sw in stopwords):
                    continue
                if len(term) < 2 or len(term) > 6:
                    continue
                seen_terms.add(term)
                results.append({
                    "src": term,
                    "tgt": self.to_hanviet(term),
                    "category": category_name,
                    "count": cnt,
                    "exists": False
                })

        add_category(person_candidates, "Nhân vật", threshold=min_count)
        add_category(sect_candidates, "Tông môn / Thế lực", threshold=min_count)
        add_category(place_candidates, "Địa danh / Cõi", threshold=min_count)
        add_category(item_candidates, "Bảo vật / Công pháp", threshold=min_count)

        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    def extract_with_llm(self, text: str, engine: str = "gemini") -> List[Dict[str, Any]]:
        """Trích xuất thực thể bằng AI LLM (Gemini / DeepSeek) với độ chính xác tuyệt đối."""
        from llm_translator import LLMTranslator
        llm = LLMTranslator()
        existing = self.load_existing_names()

        sample_text = text[:4000]

        system_prompt = (
            "Bạn là chuyên gia phân tích văn học tiên hiệp, huyền huyễn, kiếm hiệp Trung Quốc.\n"
            "Nhiệm vụ: Trích xuất các thực thể riêng (Nhân vật, Tông môn, Địa danh, Bảo vật/Công pháp) xuất hiện trong đoạn văn bản sau.\n"
            "Chỉ trả về JSON thuần túy theo định dạng mảng (Array of Objects):\n"
            "[\n"
            "  {\"src\": \"叶凡\", \"tgt\": \"Diệp Phàm\", \"category\": \"Nhân vật\"},\n"
            "  {\"src\": \"青云宗\", \"tgt\": \"Thanh Vân Tông\", \"category\": \"Tông môn\"},\n"
            "  {\"src\": \"斩龙剑\", \"tgt\": \"Trảm Long Kiếm\", \"category\": \"Bảo vật\"},\n"
            "  {\"src\": \"东荒南域\", \"tgt\": \"Đông Hoang Nam Vực\", \"category\": \"Địa danh\"}\n"
            "]\n"
            "Không thêm lời giải thích nào ngoài khối JSON. 'tgt' phải là phiên âm Hán-Việt viết hoa từng chữ."
        )

        user_prompt = f"Văn bản trích xuất:\n\n{sample_text}"

        try:
            cfg = llm.load_config()
            if "gemini" in engine.lower():
                import google.generativeai as genai
                api_key = cfg.get("gemini_api_key", "")
                if not api_key:
                    raise ValueError("Chưa thiết lập Gemini API Key trong tab Mô hình AI")
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_prompt)
                resp = model.generate_content(user_prompt)
                raw_json = resp.text.strip()
            else:
                import openai
                api_key = cfg.get("deepseek_api_key", "")
                if not api_key:
                    raise ValueError("Chưa thiết lập DeepSeek API Key trong tab Mô hình AI")
                client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                resp = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2
                )
                raw_json = resp.choices[0].message.content.strip()

            m = re.search(r"\[.*\]", raw_json, re.DOTALL)
            if m:
                raw_json = m.group(0)
            items = json.loads(raw_json)

            filtered = []
            for item in items:
                src = item.get("src", "").strip()
                tgt = item.get("tgt", "").strip()
                cat = item.get("category", "Chung")
                if src and tgt:
                    cnt = text.count(src)
                    filtered.append({
                        "src": src,
                        "tgt": tgt,
                        "category": cat,
                        "count": cnt if cnt > 0 else 1,
                        "exists": src in existing
                    })
            filtered.sort(key=lambda x: x["count"], reverse=True)
            return filtered
        except Exception as e:
            print(f"LLM extract error, fallback to rules: {e}")
            return self.extract_candidates_rule_based(text)

    def add_to_names(self, entries: List[Dict[str, str]]) -> int:
        """Ghi các mục đã duyệt vào names.txt."""
        if not entries:
            return 0
        existing = self.load_existing_names()
        added_count = 0
        new_lines = []

        for e in entries:
            src = e.get("src", "").strip()
            tgt = e.get("tgt", "").strip()
            if src and tgt and src not in existing:
                new_lines.append(f"{src}={tgt}\n")
                existing.add(src)
                added_count += 1

        if new_lines:
            with open(NAMES_PATH, "a", encoding="utf-8") as f:
                f.writelines(new_lines)

        return added_count

glossary_extractor = GlossaryExtractor()
