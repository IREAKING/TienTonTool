# ⚡ Tiên Tôn Tool - AI Cyber Pro

Bộ công cụ dịch thuật, làm sạch và biên tập truyện chữ Trung - Việt tối thượng trên macOS, xây dựng trên nền tảng **Wails (Go + Web Tech)** và backend **Python (CTranslate2 & AI LLM)**.

---

## 🌟 Tính năng nổi bật

### 1. 📝 Dịch Văn Bản Đơn & Hàng Loạt
- Hỗ trợ dịch **Offline bằng CTranslate2** (mô hình MarianMT tốc độ cao, tiết kiệm tài nguyên).
- Hỗ trợ dịch **Online bằng AI** (Gemini 2.5 Flash, DeepSeek Chat).
- Quản lý từ điển tên riêng, xưng hô (`names.txt`) với tính năng tìm kiếm, thêm, sửa, xóa trực tiếp trên giao diện.
- Tự động chuẩn hóa phồn thể sang giản thể (OpenCC).

### 2. 🧹 Làm Sạch & Biên Tập Văn Bản
- Tự động xử lý và làm sạch các từ bị kiểm duyệt, chèn ký tự lạ (ví dụ: `c·hết` $\rightarrow$ `chết`, `g·iết` $\rightarrow$ `giết`, `b·ạo đ·ộng` $\rightarrow$ `bạo động`).
- Chuẩn hóa dấu câu, xuống dòng đoạn văn sạch sẽ.

### 3. ✨ Dịch Truyện Convert thành Truyện Dịch
- Chuyển đổi văn bản Convert thô (QuickTranslate) thành văn phong truyện dịch mượt mà bằng AI thông minh hoặc bộ quy tắc tu từ.

### 4. 🕷️ Cào Truyện Tự Động (Web Scraper)
- **Hỗ trợ 番茄小说 (Fanqie Novel - fanqienovel.com)**: Tự động giải mã bảng mã Font PUA Glyph của ByteDance sang chữ Hán chuẩn xác 100%.
- **Hỗ trợ SangTacViet (sangtacviet.app)**: Tự động phân tích và chuyển đổi URL SangTacViet sang nguồn gốc trực tiếp (Fanqie, 69shu, UUkanShu...).
- Các preset có sẵn: `fanqienovel.com`, `sangtacviet.app`, `69shu.me`, `tvtruyen.live`, `truyenhoan.com`, `ihuliwang.net`, `biquge`, `uukanshu`...
- Hỗ trợ cả 2 chế độ:
  - Cào tuần tự (theo dõi nút Next chương).
  - Cào đa luồng siêu tốc theo danh sách mục lục (TOC).

### 5. 📦 Đóng Gói Xuất Bản
- Gộp các chương `.txt` thành một file sách hoàn chỉnh.
- Xuất file **EPUB** chuẩn để đọc trên Apple Books, Kindle, Kobo...

---

## 🚀 Cài đặt & Khởi chạy

### Yêu cầu hệ thống:
- macOS (Apple Silicon M1/M2/M3/M4 hoặc Intel x86_64).
- Python 3.10+ (khuyên dùng môi trường Conda `dichtruyen`).
- CTranslate2, Requests, BeautifulSoup4, FontTools, Brotli, Edge-TTS.

### Khởi chạy nhanh:
1. Mở ứng dụng [**`TienTonTool.app`**](./TienTonTool.app) hoặc chạy file [`start.command`](./start.command).
2. Backend Python bridge server sẽ tự động được khởi động trên cổng `58231`.

---

## 📁 Cấu trúc thư mục

```text
├── TienTonTool.app/         # Gói ứng dụng macOS Native
├── start.command            # File khởi chạy nhanh
├── mac_tool/                # Backend Python
│   ├── bridge.py            # Local HTTP Bridge API
│   ├── translator.py        # Module dịch Offline CTranslate2
│   ├── llm_translator.py    # Module dịch AI (Gemini, DeepSeek)
│   ├── scraper.py           # Bộ cào truyện đa luồng
│   ├── fanqie_decoder.py    # Giải mã font PUA Fanqie Novel
│   ├── sangtacviet_resolver.py # Bộ giải mã link SangTacViet
│   ├── text_cleaner.py      # Làm sạch từ lách kiểm duyệt
│   ├── convert_polisher.py  # Đánh bóng Convert -> Dịch
│   └── dictionary.py        # Quản lý từ điển names.txt
└── wails_dichtruyen/        # Mã nguồn Frontend & Go Wails
    ├── main.go
    ├── app.go
    └── frontend/src/        # Giao diện Cyberpunk Glassmorphism
```

---

## 📜 Giấy phép
Phát triển bởi Tiên Tôn. Bản quyền © 2026.
