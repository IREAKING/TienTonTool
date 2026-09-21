import os
import re
import html
import zipfile
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

def natural_sort_key(s: str):
    """Sắp xếp tự nhiên để chương 2 đứng trước chương 10 (thay vì 1, 10, 2)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_chapters_from_folder(folder_path: str) -> List[Dict[str, str]]:
    """Đọc toàn bộ file .txt trong thư mục và sắp xếp theo thứ tự tự nhiên."""
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {folder_path}")

    files = [f for f in os.listdir(folder_path) if f.endswith(".txt") and not f.startswith(".")]
    files.sort(key=natural_sort_key)

    chapters = []
    for f in files:
        full_path = os.path.join(folder_path, f)
        # Bỏ qua file gộp đã có
        if "FULL" in f or "hop_nhat" in f.lower() or "tong_hop" in f.lower():
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                lines = [line.strip() for line in fp.readlines() if line.strip()]
            if not lines:
                continue
            
            # Dòng đầu thường là tiêu đề nếu chứa "Chương" hoặc "Hồi", nếu không lấy tên file
            first_line = lines[0]
            if any(k in first_line.lower() for k in ["chương", "chuong", "hồi", "hoi", "tiết", "đệ", "第"]):
                title = first_line
                content_lines = lines[1:]
            else:
                # Lấy tên file bỏ đuôi .txt và số thứ tự đầu nếu có (0001_xxx -> xxx)
                base_name = os.path.splitext(f)[0]
                cleaned_title = re.sub(r'^\d+[\s_-]*', '', base_name).strip()
                title = cleaned_title if cleaned_title else base_name
                content_lines = lines

            content = "\n\n".join(content_lines)
            chapters.append({
                "filename": f,
                "title": title,
                "content": content
            })
        except Exception as e:
            print(f"Lỗi khi đọc file {f}: {e}")

    return chapters

def merge_txt(
    folder_path: str,
    output_path: Optional[str] = None,
    novel_title: str = "Truyện Tổng Hợp",
    author: str = "Tác Giả Khuyết Danh"
) -> Dict[str, Any]:
    """Gộp toàn bộ các file .txt chương thành 1 file .txt duy nhất."""
    chapters = load_chapters_from_folder(folder_path)
    if not chapters:
        return {"success": False, "error": "Không tìm thấy file chương .txt nào trong thư mục."}

    folder_name = os.path.basename(os.path.abspath(folder_path))
    if not output_path:
        output_filename = f"{novel_title.replace('/', '_')}_FULL.txt"
        output_path = os.path.join(folder_path, output_filename)

    lines = []
    lines.append(f"{'=' * 50}")
    lines.append(f"TÊN TRUYỆN: {novel_title}")
    lines.append(f"TÁC GIẢ: {author}")
    lines.append(f"TỔNG SỐ CHƯƠNG: {len(chapters)}")
    lines.append(f"NGÀY ĐÓNG GÓI: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lines.append(f"{'=' * 50}\n\n")

    for i, ch in enumerate(chapters, 1):
        lines.append(f"\n\n{'=' * 40}\n{ch['title']}\n{'=' * 40}\n\n")
        lines.append(ch['content'])

    full_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as fp:
        fp.write(full_text)

    file_size_kb = round(os.path.getsize(output_path) / 1024, 1)
    return {
        "success": True,
        "output_path": output_path,
        "filename": os.path.basename(output_path),
        "total_chapters": len(chapters),
        "size_kb": file_size_kb
    }

def export_epub(
    folder_path: str,
    output_path: Optional[str] = None,
    novel_title: str = "Truyện Dịch",
    author: str = "Tác Giả Khuyết Danh",
    description: str = "Được đóng gói tự động bởi DichTruyen Tool"
) -> Dict[str, Any]:
    """Xuất toàn bộ chương truyện sang file EPUB tiêu chuẩn cho Apple Books và Kindle."""
    chapters = load_chapters_from_folder(folder_path)
    if not chapters:
        return {"success": False, "error": "Không tìm thấy file chương .txt nào để tạo EPUB."}

    if not output_path:
        safe_title = re.sub(r'[\\/*?:"<>|]', '', novel_title).strip()
        output_filename = f"{safe_title}.epub"
        output_path = os.path.join(folder_path, output_filename)

    book_uuid = str(uuid.uuid4())
    pub_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    # CSS phong cách tiểu thuyết mượt mà, hỗ trợ cả Dark Mode
    css_content = """
@charset "utf-8";
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Times New Roman", serif;
    font-size: 1.1em;
    line-height: 1.7;
    margin: 5% 7%;
    text-align: justify;
    color: #1a1a1a;
    background-color: #fcfbf9;
}
h1, h2 {
    text-align: center;
    font-size: 1.5em;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 1.2em;
    color: #0b3954;
    line-height: 1.3;
}
p {
    margin-top: 0;
    margin-bottom: 0.8em;
    text-indent: 1.8em;
}
.chapter-divider {
    text-align: center;
    margin: 2em 0;
    color: #888;
    font-size: 0.9em;
}
@media (prefers-color-scheme: dark) {
    body {
        color: #e4e4e7;
        background-color: #121214;
    }
    h1, h2 {
        color: #60a5fa;
    }
}
"""

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. mimetype (bắt buộc phải lưu không nén - ZIP_STORED)
        zf.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""
        zf.writestr("META-INF/container.xml", container_xml)

        # 3. Ghi CSS
        zf.writestr("OEBPS/style.css", css_content)

        # 4. Ghi từng chương xhtml
        manifest_items = [
            '<item id="style" href="style.css" media-type="text/css"/>',
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        ]
        spine_items = []
        ncx_navpoints = []
        nav_li_items = []

        for idx, ch in enumerate(chapters, 1):
            ch_id = f"chapter_{idx:04d}"
            ch_filename = f"{ch_id}.xhtml"
            manifest_items.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch_id}"/>')

            clean_title = html.escape(ch["title"])
            ncx_navpoints.append(f"""
        <navPoint id="np_{idx}" playOrder="{idx}">
            <navLabel><text>{clean_title}</text></navLabel>
            <content src="{ch_filename}"/>
        </navPoint>""")
            nav_li_items.append(f'<li><a href="{ch_filename}">{clean_title}</a></li>')

            # Nội dung chương thành thẻ <p>
            paragraphs = ch["content"].split("\n\n")
            p_html = "\n".join([f"<p>{html.escape(p.strip())}</p>" for p in paragraphs if p.strip()])

            ch_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="vi">
<head>
    <title>{clean_title}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <h2>{clean_title}</h2>
    <div class="chapter-content">
        {p_html}
    </div>
</body>
</html>"""
            zf.writestr(f"OEBPS/{ch_filename}", ch_html)

        # 5. OEBPS/nav.xhtml (EPUB 3 Navigation)
        nav_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="vi">
<head>
    <title>Mục Lục - {html.escape(novel_title)}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>MỤC LỤC</h1>
        <ol>
            {"".join(nav_li_items)}
        </ol>
    </nav>
</body>
</html>"""
        zf.writestr("OEBPS/nav.xhtml", nav_html)

        # 6. OEBPS/toc.ncx (EPUB 2 Table of Contents)
        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_uuid}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{html.escape(novel_title)}</text></docTitle>
    <docAuthor><text>{html.escape(author)}</text></docAuthor>
    <navMap>
        {"".join(ncx_navpoints)}
    </navMap>
</ncx>"""
        zf.writestr("OEBPS/toc.ncx", toc_ncx)

        # 7. OEBPS/content.opf
        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookID">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>{html.escape(novel_title)}</dc:title>
        <dc:creator>{html.escape(author)}</dc:creator>
        <dc:language>vi</dc:language>
        <dc:identifier id="BookID">urn:uuid:{book_uuid}</dc:identifier>
        <dc:date>{pub_date}</dc:date>
        <dc:description>{html.escape(description)}</dc:description>
        <meta property="dcterms:modified">{pub_date}</meta>
    </metadata>
    <manifest>
        {"".join(manifest_items)}
    </manifest>
    <spine toc="ncx">
        {"".join(spine_items)}
    </spine>
</package>"""
        zf.writestr("OEBPS/content.opf", content_opf)

    file_size_kb = round(os.path.getsize(output_path) / 1024, 1)
    return {
        "success": True,
        "output_path": output_path,
        "filename": os.path.basename(output_path),
        "total_chapters": len(chapters),
        "size_kb": file_size_kb
    }

def strip_titles_and_export_catalog(
    input_folder: str,
    output_folder: Optional[str] = None,
    in_place: bool = False
) -> Dict[str, Any]:
    """
    Tách dòng tiêu đề dính chùm (ví dụ: 'Hoàn Mỹ Thế Giới: Ta, Trùm Try HardChương 1: Bạch Nhất Tâm'):
    - Trích xuất tên chương và lưu toàn bộ danh sách vào 'danh_sach_chuong.txt'.
    - Cắt bỏ hoàn toàn dòng tiêu đề này khỏi file truyện, chỉ giữ lại nội dung thuần túy.
    """
    if not os.path.exists(input_folder):
        raise FileNotFoundError(f"Thư mục không tồn tại: {input_folder}")

    if in_place:
        target_folder = input_folder
    else:
        target_folder = output_folder or os.path.join(input_folder, "noi_dung_thuan")
    os.makedirs(target_folder, exist_ok=True)

    files = [f for f in os.listdir(input_folder) if f.endswith(".txt") and not f.startswith(".")]
    files.sort(key=natural_sort_key)

    catalog_lines = []
    detected_book_titles = []
    processed_count = 0

    chapter_pattern = re.compile(
        r'(Chương\s*\d+.*|Đệ\s*[\d一二三四五六七八九十百千万]+\s*(?:chương|hồi|tiết).*|第\s*[\d一二三四五六七八九十百千万]+\s*[章回节].*|Hồi\s*\d+.*|Tiết\s*\d+.*)',
        re.IGNORECASE
    )

    for f in files:
        if f in ["danh_sach_chuong.txt", "muc_luc.txt", "FULL.txt"]:
            continue
        full_path = os.path.join(input_folder, f)
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                lines = [line.strip() for line in fp.readlines() if line.strip()]

            if not lines:
                continue

            first_line = lines[0]
            m = chapter_pattern.search(first_line)

            if m:
                chap_title = m.group(1).strip()
                book_title = first_line[:m.start()].strip()
                if book_title and book_title not in detected_book_titles:
                    detected_book_titles.append(book_title)
                catalog_lines.append(chap_title)
                content_start = 1
                if len(lines) > 1:
                    second_line = lines[1].strip()
                    if second_line.lower() == chap_title.lower() or chapter_pattern.fullmatch(second_line):
                        content_start = 2
                pure_content_lines = lines[content_start:]
            else:
                if any(k in first_line.lower() for k in ["chương", "hồi", "tiết", "đệ", "第"]):
                    catalog_lines.append(first_line)
                    pure_content_lines = lines[1:]
                else:
                    pure_content_lines = lines

            out_path = os.path.join(target_folder, f)
            with open(out_path, "w", encoding="utf-8") as fp:
                fp.write("\n\n".join(pure_content_lines))

            processed_count += 1
        except Exception as e:
            print(f"Lỗi xử lý file {f}: {e}")

    catalog_path = os.path.join(target_folder, "danh_sach_chuong.txt")
    with open(catalog_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(catalog_lines))

    return {
        "success": True,
        "processed_count": processed_count,
        "target_folder": target_folder,
        "catalog_file": catalog_path,
        "total_chapters": len(catalog_lines),
        "detected_novel_title": detected_book_titles[0] if detected_book_titles else ""
    }

