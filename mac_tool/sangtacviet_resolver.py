"""sangtacviet_resolver.py - Bộ phân tích và chuyển đổi URL từ SangTacViet sang nguồn truyện gốc.

SangTacViet (STV) là cổng tổng hợp tự động từ nhiều website truyện chữ Trung Quốc:
- fanqie: 番茄小说 (fanqienovel.com)
- 69shu: 69 Thư Ba (69shu.me / 69shuba.com)
- uukanshu: UU Đọc Sách (uukanshu.com)
- biquge: Bút Khúc Các
- faloo: Phi Lư (faloo.com)
- trxs: Đồng Nhân Tiểu Thuyết (trxs.cc)
- qidian: Khởi Điểm (qidian.com)

Module này tự động bóc tách host, book_id, chapter_id từ link SangTacViet
và chuyển đổi trực tiếp sang link nguồn gốc chính xác nhất để cào mượt mà,
bỏ qua tường lửa chống bot của SangTacViet.
"""

import re
from typing import Optional, Tuple, Dict, Any


def is_sangtacviet_url(url: str) -> bool:
    """Kiểm tra xem URL có thuộc về hệ thống SangTacViet hay không."""
    return bool(re.search(r"sangtacviet\.(?:app|vip|com|me|net|xyz|link)", url.lower()))


def parse_sangtacviet_url(url: str) -> Optional[Dict[str, str]]:
    """Trích xuất thông tin host, book_id, chapter_id từ URL SangTacViet.
    
    Định dạng URL:
    - Sách: https://sangtacviet.app/truyen/<host>/<vol>/<book_id>/
    - Chương: https://sangtacviet.app/truyen/<host>/<vol>/<book_id>/<chapter_id>/
    """
    m = re.search(r"/truyen/([^/]+)/(\d+)/([^/]+)(?:/([^/]+))?", url)
    if not m:
        return None

    host = m.group(1).lower().strip()
    vol = m.group(2).strip()
    book_id = m.group(3).strip()
    chapter_id = m.group(4).strip() if m.group(4) else ""

    # Loại bỏ dấu / hoặc query params nếu có
    book_id = re.sub(r"[^\w\-]", "", book_id)
    if chapter_id:
        chapter_id = re.sub(r"[^\w\-]", "", chapter_id)

    return {
        "host": host,
        "vol": vol,
        "book_id": book_id,
        "chapter_id": chapter_id
    }


def resolve_sangtacviet_url(url: str) -> Tuple[str, str, str]:
    """Chuyển đổi URL SangTacViet sang URL nguồn gốc chính thức.
    
    Trả về: (origin_url, host, message)
    """
    info = parse_sangtacviet_url(url)
    if not info:
        return url, "", ""

    host = info["host"]
    book_id = info["book_id"]
    chapter_id = info["chapter_id"]

    # 1. Nguồn Fanqie (番茄小说 - fanqienovel.com) - Nguồn phổ biến nhất trên STV (chiếm > 85%)
    if host == "fanqie":
        if chapter_id:
            origin = f"https://fanqienovel.com/reader/{chapter_id}"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc Fanqie: {origin}"
        else:
            origin = f"https://fanqienovel.com/page/{book_id}"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện Fanqie: {origin}"
        return origin, host, msg

    # 2. Nguồn 69shu (69 Thư Ba - 69shu.me)
    if host in ["69shu", "69shuba", "69xinshu"]:
        if chapter_id:
            origin = f"https://www.69shu.me/txt/{book_id}/{chapter_id}"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc 69shu: {origin}"
        else:
            origin = f"https://www.69shu.me/book/{book_id}.htm"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện 69shu: {origin}"
        return origin, host, msg

    # 3. Nguồn UUkanShu (UU Đọc Sách - uukanshu.com)
    if host in ["uukanshu", "sj.uukanshu"]:
        if chapter_id:
            origin = f"https://www.uukanshu.com/b/{book_id}/{chapter_id}.html"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc UUkanShu: {origin}"
        else:
            origin = f"https://www.uukanshu.com/b/{book_id}/"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện UUkanShu: {origin}"
        return origin, host, msg

    # 4. Nguồn Biquge (Bút Khúc Các)
    if "biquge" in host:
        if chapter_id:
            origin = f"https://www.biquge.com.cn/book/{book_id}/{chapter_id}.html"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc Biquge: {origin}"
        else:
            origin = f"https://www.biquge.com.cn/book/{book_id}/"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện Biquge: {origin}"
        return origin, host, msg

    # 5. Nguồn Trxs (Đồng Nhân Tiểu Thuyết - trxs.cc)
    if host == "trxs":
        if chapter_id:
            origin = f"https://trxs.cc/tongren/{book_id}/{chapter_id}.html"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc Trxs: {origin}"
        else:
            origin = f"https://trxs.cc/tongren/{book_id}.html"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện Trxs: {origin}"
        return origin, host, msg

    # 6. Nguồn Faloo (Phi Lư - faloo.com)
    if host == "faloo":
        if chapter_id:
            origin = f"https://b.faloo.com/{book_id}_{chapter_id}.html"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc Faloo: {origin}"
        else:
            origin = f"https://b.faloo.com/{book_id}.html"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện Faloo: {origin}"
        return origin, host, msg

    # 7. Nguồn Qidian (Khởi Điểm - qidian.com)
    if host == "qidian":
        if chapter_id:
            origin = f"https://www.qidian.com/chapter/{book_id}/{chapter_id}/"
            msg = f"Đã chuyển đổi link SangTacViet sang chương đọc Qidian: {origin}"
        else:
            origin = f"https://www.qidian.com/book/{book_id}/"
            msg = f"Đã chuyển đổi link SangTacViet sang trang truyện Qidian: {origin}"
        return origin, host, msg

    return url, host, f"Chưa hỗ trợ định dạng tự động cho nguồn '{host}' của SangTacViet"
