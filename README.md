# ⚡ Tiên Tôn Tool - AI Cyber Pro (v2.5)

Bộ công cụ dịch thuật, làm sạch và biên tập truyện chữ Trung - Việt tối thượng trên macOS, xây dựng trên nền tảng **Wails (Go + Web Tech)** và backend **Python (CTranslate2 & AI LLM)**.

---

## 🌟 Tính năng nổi bật & Nâng cấp mới

### 1. 🔍 AI Auto-Glossary (Trích xuất Tên riêng & Thuật ngữ Tự Động) `MỚI`
- Tự động nhận diện thực thể tiếng Trung: **Nhân vật, Tông môn / Thế lực, Bảo vật / Công pháp, Địa danh / Cõi**.
- Thuật toán kết hợp **Jieba POS Segmentation + Quy tắc ngữ nghĩa Tiên hiệp + AI LLM (Gemini / DeepSeek)**.
- Tự động phiên âm sang **Hán-Việt chuẩn xác 100%** dựa trên từ điển hơn 10,000 ký tự chuẩn Unicode Unihan.
- Bảng duyệt trực quan: lọc theo số lần xuất hiện, cho phép sửa trực tiếp Hán-Việt và **thêm vào `names.txt` chỉ với 1-Click**.

### 2. 📑 Studio Biên Tập Song Ngữ (Bilingual Studio) `MỚI`
- Trình biên tập side-by-side chuyên nghiệp 3 cột:
  - **Cột 1**: Tiếng Trung gốc (Hỗ trợ bôi đen tra cứu Hán-Việt tức thì).
  - **Cột 2**: Phiên âm Hán-Việt / Convert từng câu.
  - **Cột 3**: Bản dịch mượt mà (Cho phép chỉnh sửa trực tiếp, tự động cập nhật).
- Tự động căn chỉnh và đồng bộ từng đoạn văn bản từ tab Dịch chỉ bằng 1 nút bấm.
- Xuất file `.txt` bản dịch hoàn chỉnh ngay tại chỗ.

### 3. ⚡ Dịch Hàng Loạt Đa Luồng & Tự Động Lưu (Multi-threading & Auto-Save) `MỚI`
- Tùy chỉnh **1 đến 5 luồng dịch song song (Workers)** giúp tăng tốc độ dịch gấp 3-4 lần.
- **🛡️ Auto-Save từng chương an toàn**: Dịch xong chương nào lưu ngay file `chuong_xxx_viet.txt`, chống mất dữ liệu khi mất mạng hoặc tắt máy.
- Tự động thử lại thông minh (Exponential Backoff Retry) khi gặp giới hạn tần suất API (HTTP 429).
- Tùy chọn **Tự động khử ký tự rác kiểm duyệt** trước khi dịch.

### 4. 🕷️ Mở Rộng Nguồn Cào Truyện (Scraper Expansion) `MỚI`
- **69shuba.cx / 69xinshu.com**: Kho raw tiếng Trung số 1 hiện nay (sạch, không dính font mã hóa, tự động khử watermark `(本章完)`, `69书吧`).
- **b.faloo.com (Phi Lư)**: Cào truyện đồng nhân, sảng văn, hệ thống.
- **truyen.tangthuvien.vn**: Cào và đồng bộ truyện convert về máy để biên tập mượt mà.
- **fanqienovel.com (番茄小说)**: Tự động giải mã bảng mã Font PUA Glyph của ByteDance sang chữ Hán chuẩn 100%.
- **sangtacviet.app**: Tự động giải mã và chuyển hướng link sang nguồn gốc thực tế.

### 5. 🧹 Làm Sạch & Khử Ký Tự Rác Kiểm Duyệt
- Khử sạch các ký tự chèn lách kiểm duyệt (ví dụ: `c·hết` $\rightarrow$ `chết`, `g·iết` $\rightarrow$ `giết`, `b·ạo đ·ộng` $\rightarrow$ `bạo động`).
- Loại bỏ toàn bộ watermark website, ký tự ẩn zero-width Unicode.

### 6. 📦 Đóng Gói Bộ Cài macOS (.DMG) & GitHub Actions CI/CD `MỚI`
- Kèm script [`package_dmg.sh`](./package_dmg.sh) đóng gói thành file installer **`TienTonTool-macOS.dmg`** chuẩn drag-and-drop vào `/Applications`.
- Cấu hình workflow GitHub Actions tự động build và phát hành bộ cài khi gắn thẻ (tag) phiên bản.

---

## 🚀 Cài đặt & Khởi chạy

### Khởi chạy nhanh:
1. Chạy file [`start.command`](./start.command) (Script tự động kiểm tra, khởi chạy AI bridge và mở app).
2. Hoặc đóng gói file cài đặt bằng lệnh:
   ```bash
   ./package_dmg.sh
   ```

---

## 📁 Cấu trúc thư mục

```text
├── TienTonTool.app/            # Ứng dụng macOS Native (Wails)
├── start.command               # File khởi chạy nhanh 1-Click
├── package_dmg.sh              # Script đóng gói bộ cài đặt DMG
├── mac_tool/                   # Backend Python Engine
│   ├── bridge.py               # Local HTTP API Bridge (Port 58231)
│   ├── glossary_extractor.py   # Bộ trích xuất tên riêng AI & Hán-Việt
│   ├── hanviet_dict.json       # Cơ sở dữ liệu 10,900+ âm Hán-Việt
│   ├── file_processor.py       # Dịch hàng loạt đa luồng (Multi-threading)
│   ├── scraper.py              # Bộ cào truyện đa nguồn (69shu, Faloo, Fanqie...)
│   ├── fanqie_decoder.py       # Giải mã font PUA Fanqie Novel
│   ├── sangtacviet_resolver.py # Giải mã link SangTacViet
│   ├── text_cleaner.py         # Khử rác kiểm duyệt & watermark
│   ├── convert_polisher.py     # Chuyển Convert thành Truyện Dịch
│   └── names.txt               # Từ điển tên riêng tùy chỉnh
└── wails_dichtruyen/           # Mã nguồn Frontend & Go Backend
```

---

## 📜 Giấy phép
Phát triển bởi Tiên Tôn. Bản quyền © 2026.
