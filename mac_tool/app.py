import os
import sys
import time
import gradio as gr
from dictionary import DictionaryManager
from translator import NovelTranslator, AVAILABLE_MODELS
from file_processor import BatchFileProcessor

# Khởi tạo các thành phần cốt lõi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

dict_mgr = DictionaryManager(os.path.join(BASE_DIR, "names.txt"))
translator = NovelTranslator(models_dir=MODELS_DIR, dict_manager=dict_mgr)
batch_proc = BatchFileProcessor(translator=translator)

# Mặc định nạp mô hình khuyên dùng nếu đã tải, hoặc đợi user nạp
DEFAULT_MODEL = list(AVAILABLE_MODELS.keys())[0]

def ensure_model_loaded(model_name: str, progress=gr.Progress()):
    if translator.current_model_key != model_name or translator.translator is None:
        def update_prog(msg):
            progress(0.2, desc=msg)
        translator.load_model(model_name, progress_callback=update_prog)
    return f"Đã sẵn sàng mô hình: {model_name}"

def translate_single_text(
    text: str,
    model_name: str,
    beam_size: int,
    batch_size: int,
    opencc_enabled: bool,
    progress=gr.Progress(track_tqdm=True)
):
    if not text.strip():
        return "", "Vui lòng nhập văn bản tiếng Trung cần dịch."

    start_time = time.time()
    try:
        progress(0.1, desc="Đang kiểm tra và nạp mô hình...")
        translator.opencc_enabled = opencc_enabled
        ensure_model_loaded(model_name, progress)
        
        def prog_cb(pct, status_str):
            progress(pct, desc=status_str)

        translated = translator.translate_text(
            text,
            beam_size=int(beam_size),
            batch_size=int(batch_size),
            progress_callback=prog_cb
        )
        elapsed = time.time() - start_time
        return translated, f"Hoàn thành trong {elapsed:.2f} giây."
    except Exception as e:
        return "", f"Lỗi: {str(e)}"

def check_files_in_folder(input_folder: str):
    if not input_folder or not os.path.isdir(input_folder):
        return "Thư mục không tồn tại hoặc không hợp lệ.", ""
    files = batch_proc.get_txt_files(input_folder)
    if not files:
        return "Không tìm thấy file .txt nào trong thư mục!", ""
    file_list_preview = "\n".join([f"{i+1}. {os.path.basename(f)}" for i, f in enumerate(files[:30])])
    if len(files) > 30:
        file_list_preview += f"\n... và còn {len(files) - 30} file khác."
    return f"Tìm thấy {len(files)} file .txt hợp lệ sẵn sàng dịch.", file_list_preview

def start_batch_translation(
    input_folder: str,
    output_folder: str,
    suffix: str,
    model_name: str,
    beam_size: int,
    batch_size: int,
    opencc_enabled: bool,
    progress=gr.Progress(track_tqdm=True)
):
    if not input_folder or not os.path.isdir(input_folder):
        yield "Thư mục nguồn không hợp lệ!", ""
        return

    if not output_folder.strip():
        output_folder = EXPORTS_DIR

    try:
        translator.opencc_enabled = opencc_enabled
        ensure_model_loaded(model_name, progress)
    except Exception as e:
        yield f"Lỗi nạp mô hình: {str(e)}", ""
        return

    logs = []
    
    def status_cb(msg: str, pct: float):
        logs.append(msg)
        progress(pct, desc=msg)
    
    # Chạy dịch
    completed = batch_proc.process_folder(
        input_folder=input_folder,
        output_folder=output_folder,
        beam_size=int(beam_size),
        batch_size=int(batch_size),
        suffix_output=suffix,
        status_callback=status_cb
    )
    
    final_log = "\n".join(logs[-50:])
    res_msg = f"Đã hoàn thành! Đã dịch {len(completed)} file vào: {output_folder}"
    yield res_msg, final_log

def stop_batch_translation():
    batch_proc.stop()
    return "Đã gửi lệnh dừng tiến trình dịch!"

def add_name_entry(src: str, tgt: str):
    if not src.strip() or not tgt.strip():
        return "Vui lòng nhập cả từ gốc tiếng Trung và từ dịch tiếng Việt!", dict_mgr.get_all_text()
    success = dict_mgr.add_entry(src, tgt)
    if success:
        return f"Đã thêm thành công: {src} -> {tgt}", dict_mgr.get_all_text()
    return "Thêm từ điển thất bại.", dict_mgr.get_all_text()

def save_dict_content(content: str):
    count = dict_mgr.update_from_text(content)
    return f"Đã lưu thành công! Tổng cộng {count} mục từ điển."

def reload_dict_content():
    dict_mgr.load()
    return dict_mgr.get_all_text(), f"Đã tải lại từ điển. Hiện có {len(dict_mgr.entries)} mục."

# Tạo giao diện Gradio
custom_css = """
footer {visibility: hidden}
.gradio-container {max-width: 1200px !important; margin: auto;}
"""

with gr.Blocks(title="Tool Dịch Truyện Trung - Việt (macOS)", theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown(
        """
        # 📚 Tool Dịch Truyện Trung - Việt (Bản macOS)
        **Chạy Cục Bộ 100% Trên Máy Mac (CTranslate2)** • Tốc độ cao • Văn phong truyện tự nhiên • Không cần mạng • Không giới hạn
        """
    )

    with gr.Tabs():
        # TAB 1: Dịch Văn Bản Trực Tiếp
        with gr.TabItem("📝 Dịch Nhanh Văn Bản"):
            with gr.Row():
                with gr.Column(scale=1):
                    input_text = gr.Textbox(
                        label="Văn bản tiếng Trung (gốc)",
                        placeholder="Dán văn bản tiếng Trung cần dịch vào đây (chương truyện, đoạn văn)...",
                        lines=15
                    )
                    with gr.Row():
                        btn_clear = gr.Button("Xóa")
                        btn_translate = gr.Button("🚀 Bắt Đầu Dịch", variant="primary")
                
                with gr.Column(scale=1):
                    output_text = gr.Textbox(
                        label="Văn bản tiếng Việt (kết quả)",
                        placeholder="Bản dịch tiếng Việt sẽ xuất hiện ở đây...",
                        lines=15,
                        interactive=True
                    )
                    status_text = gr.Markdown("Sẵn sàng.")

            btn_clear.click(lambda: ("", "", "Đã xóa."), outputs=[input_text, output_text, status_text])

        # TAB 2: Dịch Hàng Loạt Theo Thư Mục
        with gr.TabItem("📁 Dịch Hàng Loạt File / Thư Mục"):
            gr.Markdown("### Dịch hàng loạt các chương truyện (.txt) trong một thư mục")
            with gr.Row():
                input_folder = gr.Textbox(
                    label="Đường dẫn thư mục nguồn (chứa các file .txt tiếng Trung)",
                    placeholder="/Users/macbook-pro/Downloads/truyen_goc",
                    lines=1
                )
                output_folder = gr.Textbox(
                    label="Đường dẫn thư mục xuất kết quả (để trống sẽ lưu vào thư mục exports)",
                    value=EXPORTS_DIR,
                    lines=1
                )
            
            with gr.Row():
                suffix_input = gr.Textbox(
                    label="Hậu tố tên file kết quả",
                    value="_viet",
                    info="Ví dụ: 100.txt -> 100_viet.txt"
                )
                btn_check_folder = gr.Button("🔍 Kiểm tra số file trong thư mục")

            folder_check_status = gr.Markdown("")
            folder_preview = gr.Textbox(label="Danh sách file tìm thấy", lines=5, interactive=False)

            with gr.Row():
                btn_batch_start = gr.Button("⚡ Bắt Đầu Dịch Hàng Loạt", variant="primary", scale=2)
                btn_batch_stop = gr.Button("🛑 Dừng Lại", variant="stop", scale=1)

            batch_status_msg = gr.Markdown("")
            batch_log = gr.Textbox(label="Nhật ký xử lý (Real-time)", lines=8, interactive=False)

            btn_check_folder.click(
                check_files_in_folder,
                inputs=[input_folder],
                outputs=[folder_check_status, folder_preview]
            )

        # TAB 3: Quản Lý Từ Điển & Tên Riêng
        with gr.TabItem("📖 Từ Điển & Tên Riêng (Names)"):
            gr.Markdown("### Quản lý danh từ riêng (Tên nhân vật, công pháp, môn phái, địa danh)")
            with gr.Row():
                src_term = gr.Textbox(label="Từ gốc tiếng Trung", placeholder="VD: 苏阳")
                tgt_term = gr.Textbox(label="Từ dịch tiếng Việt", placeholder="VD: Tô Dương")
                btn_add_term = gr.Button("➕ Thêm vào từ điển", variant="primary")

            dict_status = gr.Markdown("")
            dict_editor = gr.Textbox(
                label="Nội dung file names.txt (Định dạng: TừGốc=TừDịch)",
                value=dict_mgr.get_all_text(),
                lines=15
            )
            with gr.Row():
                btn_save_dict = gr.Button("💾 Lưu Nội Dung Từ Điển", variant="primary")
                btn_reload_dict = gr.Button("🔄 Tải Lại Từ File")

            btn_add_term.click(add_name_entry, inputs=[src_term, tgt_term], outputs=[dict_status, dict_editor])
            btn_save_dict.click(save_dict_content, inputs=[dict_editor], outputs=[dict_status])
            btn_reload_dict.click(reload_dict_content, outputs=[dict_editor, dict_status])

        # TAB 4: Cài Đặt & Mô Hình
        with gr.TabItem("⚙️ Cài Đặt Mô Hình"):
            model_selector = gr.Dropdown(
                label="Chọn Mô Hình Dịch",
                choices=list(AVAILABLE_MODELS.keys()),
                value=DEFAULT_MODEL
            )
            with gr.Row():
                beam_slider = gr.Slider(minimum=1, maximum=5, value=2, step=1, label="Beam Size (Độ chuẩn xác)")
                batch_slider = gr.Slider(minimum=4, maximum=64, value=16, step=4, label="Batch Size (Kích thước mẻ dịch)")
            
            opencc_checkbox = gr.Checkbox(
                label="Bật OpenCC (Tự động chuyển Hán Phồn thể sang Giản thể trước khi dịch)",
                value=True
            )
            btn_load_model = gr.Button("📥 Tải / Nạp Mô Hình Này Vào RAM")
            model_status = gr.Markdown("Mô hình sẽ tự động được tải và nạp khi bắt đầu dịch lần đầu tiên.")

            btn_load_model.click(
                ensure_model_loaded,
                inputs=[model_selector],
                outputs=[model_status]
            )

    # Kết nối sự kiện dịch văn bản
    btn_translate.click(
        translate_single_text,
        inputs=[input_text, model_selector, beam_slider, batch_slider, opencc_checkbox],
        outputs=[output_text, status_text]
    )

    # Kết nối sự kiện dịch hàng loạt
    btn_batch_start.click(
        start_batch_translation,
        inputs=[input_folder, output_folder, suffix_input, model_selector, beam_slider, batch_slider, opencc_checkbox],
        outputs=[batch_status_msg, batch_log]
    )
    btn_batch_stop.click(stop_batch_translation, outputs=[batch_status_msg])

if __name__ == "__main__":
    # Khởi chạy Gradio server cục bộ
    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        share=False
    )
