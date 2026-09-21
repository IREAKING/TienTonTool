"""fanqie_decoder.py - Giải mã font và trích xuất nội dung từ Fanqie Novel (番茄小说 - fanqienovel.com).

Bao gồm:
- Bảng đối chiếu Glyph ID -> Ký tự thực (362 ký tự)
- Tải font woff2 động và phân tích bảng cmap (PUA -> Glyph ID)
- Cache bộ font theo URL để tối ưu tốc độ cào hàng loạt
- Trích xuất cấu trúc window.__INITIAL_STATE__ cho cả mục lục (TOC) và nội dung chương
"""

import io
import re
import json
import threading
from typing import Dict, List, Tuple, Optional, Any
import requests

# Bảng tra cứu Glyph ID -> Ký tự thực tế của 番茄小说 (Fanqie Novel)
# Tổng cộng 362 glyphs được ánh xạ vào vùng Unicode Private Use Area (PUA \ue000 - \uf8ff)
FONT_MAP = {
    '58670': '0', '58413': '1', '58678': '2', '58371': '3', '58353': '4',
    '58480': '5', '58359': '6', '58449': '7', '58540': '8', '58692': '9',
    '58712': 'a', '58542': 'b', '58575': 'c', '58626': 'd', '58691': 'e',
    '58561': 'f', '58362': 'g', '58619': 'h', '58430': 'i', '58531': 'j',
    '58588': 'k', '58440': 'l', '58681': 'm', '58631': 'n', '58376': 'o',
    '58429': 'p', '58555': 'q', '58498': 'r', '58518': 's', '58453': 't',
    '58397': 'u', '58356': 'v', '58435': 'w', '58514': 'x', '58482': 'y',
    '58529': 'z', '58515': 'A', '58688': 'B', '58709': 'C', '58344': 'D',
    '58656': 'E', '58381': 'F', '58576': 'G', '58516': 'H', '58463': 'I',
    '58649': 'J', '58571': 'K', '58558': 'L', '58433': 'M', '58517': 'N',
    '58387': 'O', '58687': 'P', '58537': 'Q', '58541': 'R', '58458': 'S',
    '58390': 'T', '58466': 'U', '58386': 'V', '58697': 'W', '58519': 'X',
    '58511': 'Y', '58634': 'Z', '58611': '的', '58590': '一', '58398': '是',
    '58422': '了', '58657': '我', '58666': '不', '58562': '人', '58345': '在',
    '58510': '他', '58496': '有', '58654': '这', '58441': '个', '58493': '上',
    '58714': '们', '58618': '来', '58528': '到', '58620': '时', '58403': '大',
    '58461': '地', '58481': '为', '58700': '子', '58708': '中', '58503': '你',
    '58442': '说', '58639': '生', '58506': '国', '58663': '年', '58436': '着',
    '58563': '就', '58391': '那', '58357': '和', '58354': '要', '58695': '她',
    '58372': '出', '58696': '也', '58551': '得', '58445': '里', '58408': '后',
    '58599': '自', '58424': '以', '58394': '会', '58348': '家', '58426': '可',
    '58673': '下', '58417': '而', '58556': '过', '58603': '天', '58565': '去',
    '58604': '能', '58522': '对', '58632': '小', '58622': '多', '58350': '然',
    '58605': '于', '58617': '心', '58401': '学', '58637': '么', '58684': '之',
    '58382': '都', '58464': '好', '58487': '看', '58693': '起', '58608': '发',
    '58392': '当', '58474': '没', '58601': '成', '58355': '只', '58573': '如',
    '58499': '事', '58469': '把', '58361': '还', '58698': '用', '58489': '第',
    '58711': '样', '58457': '道', '58635': '想', '58492': '作', '58647': '种',
    '58623': '开', '58521': '美', '58609': '总', '58530': '从', '58665': '无',
    '58652': '情', '58676': '己', '58456': '面', '58581': '最', '58509': '女',
    '58488': '但', '58363': '现', '58685': '前', '58396': '些', '58523': '所',
    '58471': '同', '58485': '日', '58613': '手', '58533': '又', '58589': '行',
    '58527': '意', '58593': '动', '58699': '方', '58707': '期', '58414': '它',
    '58596': '头', '58570': '经', '58660': '长', '58364': '儿', '58526': '回',
    '58501': '位', '58638': '分', '58404': '爱', '58677': '老', '58535': '因',
    '58629': '很', '58577': '给', '58606': '名', '58497': '法', '58662': '间',
    '58479': '斯', '58532': '知', '58380': '世', '58385': '什', '58405': '两',
    '58644': '次', '58578': '使', '58505': '身', '58564': '者', '58412': '被',
    '58686': '高', '58624': '已', '58667': '亲', '58607': '其', '58616': '进',
    '58368': '此', '58427': '话', '58423': '常', '58633': '与', '58525': '活',
    '58543': '正', '58418': '感', '58597': '见', '58683': '明', '58507': '问',
    '58621': '力', '58703': '理', '58438': '尔', '58536': '点', '58384': '文',
    '58484': '几', '58539': '定', '58554': '本', '58421': '公', '58347': '特',
    '58569': '做', '58710': '外', '58574': '孩', '58375': '相', '58645': '西',
    '58592': '果', '58572': '走', '58388': '将', '58370': '月', '58399': '十',
    '58651': '实', '58546': '向', '58504': '声', '58419': '车', '58407': '全',
    '58672': '信', '58675': '重', '58538': '三', '58465': '机', '58374': '工',
    '58579': '物', '58402': '气', '58702': '每', '58553': '并', '58360': '别',
    '58389': '真', '58560': '打', '58690': '太', '58473': '新', '58512': '比',
    '58653': '才', '58704': '便', '58545': '夫', '58641': '再', '58475': '书',
    '58583': '部', '58472': '水', '58478': '像', '58664': '眼', '58586': '等',
    '58568': '体', '58674': '却', '58490': '加', '58476': '电', '58346': '主',
    '58630': '界', '58595': '门', '58502': '利', '58713': '海', '58587': '受',
    '58548': '听', '58351': '表', '58547': '德', '58443': '少', '58460': '克',
    '58636': '代', '58585': '员', '58625': '许', '58694': '稜', '58428': '先',
    '58640': '口', '58628': '由', '58612': '死', '58446': '安', '58468': '写',
    '58410': '性', '58508': '马', '58594': '光', '58483': '白', '58544': '或',
    '58495': '住', '58450': '难', '58643': '望', '58486': '教', '58406': '命',
    '58447': '花', '58669': '结', '58415': '乐', '58444': '色', '58549': '更',
    '58494': '拉', '58409': '东', '58658': '神', '58557': '记', '58602': '处',
    '58559': '让', '58610': '母', '58513': '父', '58500': '应', '58378': '直',
    '58680': '字', '58352': '场', '58383': '平', '58454': '报', '58671': '友',
    '58668': '关', '58452': '放', '58627': '至', '58400': '张', '58455': '认',
    '58416': '接', '58552': '告', '58614': '入', '58582': '笑', '58534': '内',
    '58701': '英', '58349': '军', '58491': '候', '58467': '民', '58365': '岁',
    '58598': '往', '58425': '何', '58462': '度', '58420': '山', '58661': '觉',
    '58615': '路', '58648': '带', '58470': '万', '58377': '男', '58520': '边',
    '58646': '风', '58600': '解', '58431': '叫', '58715': '任', '58524': '金',
    '58439': '快', '58566': '原', '58477': '吃', '58642': '妈', '58437': '变',
    '58411': '通', '58451': '师', '58395': '立', '58369': '象', '58706': '数',
    '58705': '四', '58379': '失', '58567': '满', '58373': '战', '58448': '远',
    '58659': '格', '58434': '士', '58679': '音', '58432': '轻', '58689': '目',
    '58591': '条', '58682': '呢',
}

_CACHE_LOCK = threading.Lock()
_FANQIE_FONT_CACHE: Dict[str, Dict[str, str]] = {}

FANQIE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def is_fanqie_url(url: str) -> bool:
    """Kiểm tra xem URL có thuộc về番茄小说 (fanqienovel.com) không."""
    return bool(re.search(r"fanqie(?:novel)?\.com", url.lower()))


def extract_fanqie_id(url: str) -> Tuple[str, str]:
    """Phân tích URL, trả về ('page'/'reader', id)."""
    m = re.search(r"fanqie(?:novel)?\.com/(reader|page)/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    # Thử tìm id số đơn thuần trong url
    m_num = re.search(r"/(\d{10,})", url)
    if m_num:
        return "reader" if "reader" in url else "page", m_num.group(1)
    return "", ""


def extract_initial_state(html: str) -> dict:
    """Trích xuất đối tượng JSON window.__INITIAL_STATE__ từ mã nguồn HTML."""
    marker = "window.__INITIAL_STATE__="
    start = html.find(marker)
    if start == -1:
        return {}
    start += len(marker)
    depth = 0
    end = start
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    try:
        return json.loads(html[start:end])
    except Exception:
        return {}


def get_font_mapping_for_html(html: str) -> Dict[str, str]:
    """Tải font woff2 từ trang Fanqie và xây dựng mapping PUA Char -> Real Char.

    Có cache theo URL font để không phải tải lại cùng một font nhiều lần.
    """
    # Tìm woff2 URL trong HTML hoặc CSS
    font_url = ""
    font_match = re.search(r'url\((https://[^)]+\.woff2)\)', html)
    if font_match:
        font_url = font_match.group(1)
    else:
        all_woff = re.findall(r'https?://[^\s"\'()]+\.woff2', html)
        if all_woff:
            font_url = all_woff[0]

    if not font_url:
        # Thử tìm trong __INITIAL_STATE__
        state = extract_initial_state(html)
        css = state.get("common", {}).get("css", "")
        if css:
            css_match = re.search(r'url\((https://[^)]+\.woff2)\)', css)
            if css_match:
                font_url = css_match.group(1)

    if not font_url:
        return {}

    with _CACHE_LOCK:
        if font_url in _FANQIE_FONT_CACHE:
            return _FANQIE_FONT_CACHE[font_url]

    try:
        from fontTools.ttLib import TTFont
        resp = requests.get(font_url, headers=FANQIE_HEADERS, timeout=15)
        resp.raise_for_status()

        font = TTFont(io.BytesIO(resp.content))
        cmap = font.getBestCmap()
        if not cmap:
            return {}

        mapping = {}
        for pua_codepoint, glyph_name in cmap.items():
            gid = glyph_name.replace("gid", "")
            if gid in FONT_MAP:
                mapping[chr(pua_codepoint)] = FONT_MAP[gid]

        with _CACHE_LOCK:
            _FANQIE_FONT_CACHE[font_url] = mapping
        return mapping
    except Exception:
        return {}


def decrypt_fanqie_text(text: str, mapping: Dict[str, str]) -> str:
    """Thay thế tất cả các ký tự mã hóa PUA bằng chữ Hán thực tế."""
    if not mapping or not text:
        return text
    return "".join(mapping.get(ch, ch) for ch in text)


def clean_fanqie_html(html_content: str) -> str:
    """Chuyển đổi thẻ HTML đoạn văn của Fanqie thành văn bản xuống dòng sạch."""
    text = html_content
    text = re.sub(r"<p[^>]*>", "", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n\n".join(lines)


def parse_fanqie_chapter(html: str, current_url: str) -> Dict[str, Any]:
    """Phân tích và giải mã một chương từ reader page của Fanqie."""
    state = extract_initial_state(html)
    font_mapping = get_font_mapping_for_html(html)

    reader = state.get("reader", {})
    chapter_data = reader.get("chapterData", {})

    raw_title = chapter_data.get("title", "")
    raw_content = chapter_data.get("content", "")
    next_item_id = chapter_data.get("nextItemId")

    # Nếu không trích xuất được từ state, fallback tìm thẻ html
    if not raw_content:
        m_content = re.search(r'<div[^>]*class="[^"]*muye-reader-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if m_content:
            raw_content = m_content.group(1)

    if not raw_title:
        m_title = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m_title:
            raw_title = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()

    title = decrypt_fanqie_text(raw_title, font_mapping).strip()
    clean_content = clean_fanqie_html(raw_content)
    clean_content = decrypt_fanqie_text(clean_content, font_mapping)

    next_url = ""
    if next_item_id and str(next_item_id) not in ["0", "", "None"]:
        next_url = f"https://fanqienovel.com/reader/{next_item_id}"

    return {
        "title": title or "Chương không tên",
        "content": clean_content,
        "next_url": next_url
    }


def extract_fanqie_toc(url: str, fetch_page_func=None) -> List[Dict[str, Any]]:
    """Trích xuất toàn bộ mục lục chương của truyện Fanqie từ URL sách hoặc reader."""
    url_type, target_id = extract_fanqie_id(url)
    if not target_id:
        return []

    def _fetch(u: str) -> str:
        if fetch_page_func:
            return fetch_page_func(u)
        r = requests.get(u, headers=FANQIE_HEADERS, timeout=15)
        return r.text

    book_id = target_id
    # Nếu truyền vào reader URL, lấy bookId từ chapterData
    if url_type == "reader":
        reader_html = _fetch(f"https://fanqienovel.com/reader/{target_id}")
        state = extract_initial_state(reader_html)
        b_id = state.get("reader", {}).get("chapterData", {}).get("bookId")
        if b_id:
            book_id = str(b_id)

    page_url = f"https://fanqienovel.com/page/{book_id}"
    page_html = _fetch(page_url)
    state = extract_initial_state(page_html)

    font_mapping = get_font_mapping_for_html(page_html)
    page_data = state.get("page", {})
    volumes = page_data.get("chapterListWithVolume", [])

    chapters = []
    idx = 1
    for volume in volumes:
        for ch in volume:
            item_id = ch.get("itemId")
            if not item_id:
                continue
            raw_title = ch.get("title", f"Chương {idx}")
            dec_title = decrypt_fanqie_text(raw_title, font_mapping).strip()
            ch_url = f"https://fanqienovel.com/reader/{item_id}"
            chapters.append({
                "index": idx,
                "title": dec_title,
                "url": ch_url,
                "is_locked": ch.get("isChapterLock", False)
            })
            idx += 1

    return chapters


def resolve_fanqie_first_chapter(url: str, fetch_page_func=None) -> str:
    """Tự động chuyển URL /page/<book_id> thành link chương 1 /reader/<item_id>."""
    url_type, target_id = extract_fanqie_id(url)
    if url_type == "reader":
        return url
    if not target_id:
        return url

    chapters = extract_fanqie_toc(url, fetch_page_func)
    if chapters:
        return chapters[0]["url"]
    return url
