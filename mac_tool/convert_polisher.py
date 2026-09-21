import os
import sys
import re
import time
import threading
from typing import Optional, Dict, Any, List, Callable

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from llm_translator import LLMTranslator
from text_cleaner import text_cleaner

# ==============================================================================
# HỆ THỐNG QUY TẮC CHUYỂN CONVERT SANG TRUYỆN DỊCH (RULE-BASED POLISHER)
# 100% Offline, tức thì, không tốn token, giải quyết 80% tật convert
# ==============================================================================

class ConvertRulesEngine:
    def __init__(self):
        self._init_rules()

    def _init_rules(self):
        # 1. Các cụm từ cố định đặc trưng của Convert -> Dịch mượt
        # Sắp xếp theo độ dài giảm dần để match cụm dài trước
        raw_phrase_mappings = [
            # Thời gian & Chuyển tiếp
            ("nói thì chậm mà xảy ra thì nhanh", "tả thì chậm nhưng diễn ra chớp nhoáng"),
            ("nói thì chậm khi đó thì nhanh", "tả thì chậm nhưng diễn ra chớp nhoáng"),
            ("thời gian dần qua", "dần dần"),
            ("sau một khắc", "khoảnh khắc tiếp theo"),
            ("ngay sau đó một khắc", "ngay khoảnh khắc tiếp theo"),
            ("trong nháy mắt ở giữa", "trong nháy mắt"),
            ("trong chớp mắt ở giữa", "trong chớp mắt"),
            ("đột nhiên ở giữa", "bất chợt"),
            ("bất tri bất giác", "không biết từ lúc nào"),
            ("chỉ chốc lát sau", "chỉ một lát sau"),
            ("trong lúc nhất thời", "nhất thời"),
            ("không bao lâu sau đó", "không lâu sau đó"),
            ("hô hấp ở giữa", "trong vài nhịp thở"),
            ("qua hồi lâu", "hồi lâu sau"),
            ("thật lâu không nói", "im lặng hồi lâu"),
            ("lời còn chưa dứt", "lời còn chưa dứt"),
            ("nói xong câu đó", "dứt lời"),
            ("nói xong lời này", "dứt lời"),
            ("nói xong lời này", "dứt lời"),
            ("vừa dứt lời", "vừa dứt lời"),
            ("cùng lúc đó", "cùng lúc đó"),
            ("đúng lúc này", "đúng lúc này"),
            ("vào lúc này", "vào lúc này"),

            # Liên từ & ngữ khí
            ("nương theo lấy", "cùng với"),
            ("nương theo", "cùng với"),
            ("đến tột cùng là", "rốt cuộc là"),
            ("đến cùng là", "rốt cuộc là"),
            ("đến tột cùng", "rốt cuộc"),
            ("đến cùng", "rốt cuộc"),
            ("chẳng lẽ là", "chẳng lẽ lại là"),
            ("làm sao có thể", "sao có thể chứ"),
            ("vì sao lại như thế", "tại sao lại như thế"),
            ("sao lại như thế", "sao lại thế này"),
            ("như vậy sao", "thế sao?"),
            ("vô luận như thế nào", "dù thế nào đi nữa"),
            ("vô luận là", "bất kể là"),
            ("bất luận kẻ nào", "bất kỳ ai"),
            ("bất luận cái gì", "bất cứ thứ gì"),
            ("không có bất kỳ cái gì", "không có bất cứ"),
            ("hoàn toàn không có bất kỳ cái gì", "hoàn toàn không có bất cứ"),
            ("không có bất kỳ", "không hề có bất kỳ"),
            ("căn bản cũng không", "hoàn toàn không"),
            ("căn bản không có", "hoàn toàn không có"),
            ("không thể không nói", "phải công nhận rằng"),
            ("không thể không thừa nhận", "buộc phải thừa nhận"),
            ("không nói hai lời", "không nói hai lời"),
            ("không nói ra được", "không sao tả xiết"),
            ("không chút do dự", "không hề do dự"),
            ("chút nào không", "chẳng hề"),
            ("mảy may không", "mảy may không"),
            ("tơ hào không", "chẳng hề"),
            ("không có nửa điểm", "không có lấy một chút"),
            ("không có chút nào", "không hề có chút"),
            ("không chút nào dây dưa", "không hề dây dưa"),
            ("liền xem như", "cho dù là"),
            ("đồng dạng", "tương tự"),
            ("đích thật là", "quả thật là"),
            ("rõ ràng chính là", "rõ ràng là"),
            ("thật sự là", "quả thực là"),
            ("sở dĩ như vậy", "nguyên do là"),
            ("cho nên mới", "vì thế mới"),

            # Hành động & Biểu cảm
            ("nghĩ thầm nói", "thầm nghĩ:"),
            ("thầm nghĩ nói", "thầm nghĩ:"),
            ("mở miệng nói ra", "lên tiếng:"),
            ("chậm rãi nói ra", "chậm rãi nói:"),
            ("nhàn nhạt mở miệng", "thản nhiên nói:"),
            ("nhàn nhạt nói ra", "thản nhiên nói:"),
            ("lạnh lùng thốt", "lạnh lùng nói:"),
            ("âm thanh lạnh lùng nói", "lạnh giọng nói:"),
            ("trầm giọng nói", "trầm giọng:"),
            ("lắc đầu nói", "lắc đầu nói:"),
            ("gật đầu nói", "gật đầu nói:"),
            ("cười lạnh nói", "cười lạnh:"),
            ("nhếch miệng cười một tiếng", "nhe răng cười:"),
            ("kinh hô một tiếng", "thốt lên kinh hãi:"),
            ("hít sâu một hơi khí lạnh", "hít một hơi khí lạnh"),
            ("hít vào một ngụm khí lạnh", "hít một hơi khí lạnh"),
            ("hít sâu một ngụm khí lạnh", "hít một hơi khí lạnh"),
            ("chậm rãi phun ra một ngụm trọc khí", "chậm rãi thở ra một ngụm trọc khí"),
            ("phun ra một ngụm máu tươi", "phun ra một búng máu tươi"),
            ("khóe miệng tràn ra máu tươi", "khóe miệng rỉ máu tươi"),
            ("khóe miệng hơi nhếch lên", "khóe miệng khẽ nhếch"),
            ("đồng tử co rụt lại", "đồng tử co thắt lại"),
            ("sắc mặt biến hóa", "sắc mặt biến đổi"),
            ("sắc mặt biến đổi lớn", "sắc mặt đại biến"),
            ("sắc mặt âm trầm như nước", "sắc mặt âm trầm như sắp rỉ nước"),
            ("sắc mặt tái nhợt như tờ giấy", "sắc mặt trắng bệch như tờ giấy"),
            ("vẻ mặt khó có thể tin", "vẻ mặt không thể tin nổi"),
            ("ánh mắt lộ ra thần sắc kinh ngạc", "ánh mắt hiện rõ vẻ kinh ngạc"),
            ("lộ ra một nụ cười khổ", "nở nụ cười cay đắng"),
            ("thân thể run lên một cái", "thân mình khẽ run rẩy"),
            ("thân thể run lên", "toàn thân run lên"),
            ("toàn thân chấn động", "toàn thân chấn động"),
            ("tâm thần kịch chấn", "tâm thần rung chuyển dữ dội"),
            ("trong lòng chấn động", "trong lòng dâng lên sóng lớn"),
            ("nhịn không được", "không kìm được"),
            ("cịn không được", "không kìm được"),
            ("dưới chân một cái lảo đảo", "chân loạng choạng một bước"),
            ("thân hình thoắt một cái", "thân hình thoắt lóe"),
            ("thân hình khẽ động", "thân hình khẽ nhúc nhích"),

            # Chiến đấu & Tiên hiệp
            ("đấm ra một quyền", "tung ra một quyền"),
            ("chém ra một kiếm", "vung ra một kiếm"),
            ("đánh ra một chưởng", "tung ra một chưởng"),
            ("đá ra một cước", "tung ra một cước"),
            ("phá không mà đi", "xé gió bay đi"),
            ("gào thét mà ra", "gầm thét lao ra"),
            ("hóa thành tro bụi", "tan thành tro bụi"),
            ("hóa thành hư vô", "tan thành hư vô"),
            ("biến mất không thấy gì nữa", "biến mất không tăm tích"),
            ("biến mất vô tung vô ảnh", "biến mất không còn tăm tích"),
            ("không thấy bóng dáng", "bặt vô âm tín"),
            ("yên lặng như tờ", "tĩnh lặng như tờ"),
            ("tĩnh mịch một mảnh", "một mảnh tĩnh mịch"),
            ("châm rơi có thể nghe", "im ắng đến mức rơi kim cũng nghe thấy"),
            ("chết không thể chết lại", "chết đến mức không thể chết hơn"),
            ("hồn phi phách tán", "hồn bay phách lạc"),
            ("thất khiếu chảy máu", "bảy lỗ chảy máu"),
            ("lôi đình vạn quân", "như sấm sét vạn quân"),
            ("dứt khoát lưu loát", "gọn gàng dứt khoát"),
            ("sạch sẽ lưu loát", "gọn gàng lưu loát"),
            ("sát khí ngút trời", "sát khí ngợp trời"),
            ("chiến ý dạt dào", "chiến ý sôi trào"),
            ("máu tươi bắn tung tóe", "máu tươi văng tung tóe"),
            ("máu chảy thành sông", "máu chảy thành sông"),
            ("thây chất thành núi", "xác chất thành núi"),

            # Khẩu khí & Xưng hô
            ("muốn chết!", "tìm chết!"),
            ("muốn chết sao?", "muốn tìm chết sao?"),
            ("làm càn!", "to gan!"),
            ("càn rỡ!", "hỗn xược!"),
            ("tiểu tử thúi", "thằng nhóc ranh"),
            ("lão gia hỏa", "lão già"),
            ("lão thất phu", "lão già khọm"),
            ("tiểu tức phụ", "cô vợ nhỏ"),
            ("lão bà tử", "bà lão"),
            ("cố sự", "câu chuyện"),

            # Lượng từ & Khí thế
            ("một cỗ uy áp", "một luồng uy áp"),
            ("một cỗ ba động", "một làn sóng dao động"),
            ("một cỗ sát khí", "một luồng sát khí"),
            ("một cỗ lực lượng", "một luồng sức mạnh"),
            ("một cỗ nhiệt lưu", "một dòng nhiệt lưu"),
            ("một cỗ khí tức", "một luồng khí tức"),
            ("từng đạo từng đạo", "từng đạo từng đạo"),
        ]

        # Biên dịch từ điển cố định (sắp xếp giảm dần theo chiều dài chuỗi)
        raw_phrase_mappings.sort(key=lambda x: len(x[0]), reverse=True)
        self.phrase_mappings = raw_phrase_mappings

        # 2. Các mẫu Regex xử lý cấu trúc ngữ pháp lộn ngược của tiếng Trung
        self.regex_patterns = [
            # Cấu trúc: tại ... bên trong / trong đó -> trong ...
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,40}?)\s+(?:bên trong|trong đó)\b', re.IGNORECASE), r'trong \1'),
            # Cấu trúc: tại ... bên ngoài / ngoài đó -> ngoài ...
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,40}?)\s+(?:bên ngoài|ngoài đó)\b', re.IGNORECASE), r'ngoài \1'),
            # Cấu trúc: tại ... phía trên -> trên ...
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,40}?)\s+phía trên\b', re.IGNORECASE), r'trên \1'),
            # Cấu trúc: tại ... phía dưới -> dưới ...
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,40}?)\s+phía dưới\b', re.IGNORECASE), r'dưới \1'),
            # Cấu trúc: tại ... trước đó -> trước khi ...
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,30}?)\s+trước đó\b', re.IGNORECASE), r'trước khi \1'),
            # Cấu trúc: tại ... về sau -> sau khi ...
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,30}?)\s+về sau\b', re.IGNORECASE), r'sau khi \1'),

            # Cấu trúc hướng/hướng phía ... mà đi/bay đi/lao tới
            (re.compile(r'\bhướng phía\s+([^,.\n!?:;]{2,30}?)\s+mà đi\b', re.IGNORECASE), r'tiến về phía \1'),
            (re.compile(r'\bhướng\s+([^,.\n!?:;]{2,30}?)\s+mà đi\b', re.IGNORECASE), r'hướng về \1'),
            (re.compile(r'\bhướng phía\s+([^,.\n!?:;]{2,30}?)\s+bay đi\b', re.IGNORECASE), r'bay về phía \1'),
            (re.compile(r'\bhướng phía\s+([^,.\n!?:;]{2,30}?)\s+lao đi\b', re.IGNORECASE), r'lao về phía \1'),
            (re.compile(r'\bhướng phía\s+([^,.\n!?:;]{2,30}?)\s+đánh tới\b', re.IGNORECASE), r'đánh về phía \1'),
            (re.compile(r'\bhướng phía\s+([^,.\n!?:;]{2,30}?)\s+chém tới\b', re.IGNORECASE), r'chém thẳng về phía \1'),

            # Cấu trúc: cái này một cái / cái này một màn
            (re.compile(r'\bcái này một màn\b', re.IGNORECASE), 'cảnh tượng này'),
            (re.compile(r'\bmột màn này\b', re.IGNORECASE), 'cảnh tượng này'),
            (re.compile(r'\bcái kia một khắc\b', re.IGNORECASE), 'khoảnh khắc đó'),
            (re.compile(r'\bcái này một khắc\b', re.IGNORECASE), 'khoảnh khắc này'),
            (re.compile(r'\bcái này một cái\s+([a-zA-ZÀ-ỹ0-9_]+)\b', re.IGNORECASE), r'chiếc \1 này'),
            (re.compile(r'\bcái này một\s+([a-zA-ZÀ-ỹ0-9_]+)\b', re.IGNORECASE), r'\1 này'),
            (re.compile(r'\bcái kia một\s+([a-zA-ZÀ-ỹ0-9_]+)\b', re.IGNORECASE), r'\1 kia'),
            (re.compile(r'\bcái này loại\s+([a-zA-ZÀ-ỹ0-9_]+)\b', re.IGNORECASE), r'loại \1 này'),
            (re.compile(r'\bcái kia loại\s+([a-zA-ZÀ-ỹ0-9_]+)\b', re.IGNORECASE), r'loại \1 kia'),

            # Bị động convert "bị người ..."
            (re.compile(r'\bbị người\s+(đánh|giết|hãm hại|phát hiện|ngăn cản|coi thường|bắt lấy|khinh thị)\b', re.IGNORECASE), r'bị kẻ khác \1'),
            (re.compile(r'\bbị người\b', re.IGNORECASE), 'bị người khác'),

            # Đại từ nhân xưng convert
            (re.compile(r'\bhắn chính mình\b', re.IGNORECASE), 'chính hắn'),
            (re.compile(r'\bnàng chính mình\b', re.IGNORECASE), 'chính nàng'),
            (re.compile(r'\by chính mình\b', re.IGNORECASE), 'chính y'),
            (re.compile(r'\bngươi chính mình\b', re.IGNORECASE), 'chính bản thân ngươi'),
            (re.compile(r'\bhắn nhóm\b', re.IGNORECASE), 'bọn họ'),
            (re.compile(r'\bnàng nhóm\b', re.IGNORECASE), 'các nàng'),
            (re.compile(r'\bngươi nhóm\b', re.IGNORECASE), 'các ngươi'),
            (re.compile(r'\bchúng ta nhóm\b', re.IGNORECASE), 'chúng ta'),

            # Nhìn nhận / Cảm quan
            (re.compile(r'\btại trong mắt hắn\b', re.IGNORECASE), 'trong mắt hắn'),
            (re.compile(r'\btại trong mắt nàng\b', re.IGNORECASE), 'trong mắt nàng'),
            (re.compile(r'\btại trong lòng hắn\b', re.IGNORECASE), 'trong lòng hắn'),
            (re.compile(r'\btại trong lòng nàng\b', re.IGNORECASE), 'trong lòng nàng'),
            (re.compile(r'\btại trong đầu hắn\b', re.IGNORECASE), 'trong đầu hắn'),
            (re.compile(r'\btại trong đầu nàng\b', re.IGNORECASE), 'trong đầu nàng'),
            (re.compile(r'\btại hắn nhìn lại\b', re.IGNORECASE), 'theo hắn thấy'),
            (re.compile(r'\btại nàng nhìn lại\b', re.IGNORECASE), 'theo nàng thấy'),
            (re.compile(r'\btại người ngoài nhìn lại\b', re.IGNORECASE), 'trong mắt người ngoài'),

            # Vị trí convert
            (re.compile(r'\bphía sau hắn\b', re.IGNORECASE), 'sau lưng hắn'),
            (re.compile(r'\bphía sau nàng\b', re.IGNORECASE), 'sau lưng nàng'),
            (re.compile(r'\bphía trước hắn\b', re.IGNORECASE), 'trước mặt hắn'),
            (re.compile(r'\bphía trước nàng\b', re.IGNORECASE), 'trước mặt nàng'),
            (re.compile(r'\bbên tai hắn truyền đến\b', re.IGNORECASE), 'bên tai hắn vang lên'),
            (re.compile(r'\bbên tai truyền đến\b', re.IGNORECASE), 'bên tai vang lên'),
            (re.compile(r'\brơi vào trên thân\b', re.IGNORECASE), 'rơi trên người'),
            (re.compile(r'\brơi vào trên người\b', re.IGNORECASE), 'rơi trên người'),

            # Loại bỏ các phụ từ thừa thãi lặp lại
            (re.compile(r'\b(nói|hỏi|quát|kêu|hét|cười|thầm nghĩ)\s+ra tiếng\b', re.IGNORECASE), r'\1'),
            (re.compile(r'\bkinh khủng khí tức\b', re.IGNORECASE), 'khí tức khủng bố'),
            (re.compile(r'\bkinh khủng uy áp\b', re.IGNORECASE), 'uy áp kinh hoàng'),
        ]

    def _capitalize_sentences(self, text: str) -> str:
        lines = text.split('\n')
        cap_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                cap_lines.append('')
                continue

            def repl_cap(m):
                prefix = m.group(1)
                char = m.group(2)
                return prefix + char.upper()

            # Viết hoa chữ cái đầu dòng (kể cả sau ngoặc kép)
            line = re.sub(r'^([“"\'«(]?\s*)([a-zA-ZÀ-ỹ])', repl_cap, line)
            # Viết hoa chữ cái sau dấu chấm, chấm than, hỏi chấm
            line = re.sub(r'([.!?]["\'”»)]?\s+)([a-zA-ZÀ-ỹ])', repl_cap, line)
            cap_lines.append(line)
        return '\n\n'.join([l for l in cap_lines if l])

    def polish(self, text: str) -> str:
        if not text:
            return ""

        # Chuẩn hóa dấu câu tiếng Trung còn sót lại (nếu có trong convert)
        result = text.replace("，", ", ").replace("。", ". ").replace("！", "! ")
        result = result.replace("？", "? ").replace("：", ": ").replace("；", "; ")
        result = result.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        result = result.replace("（", " (").replace("）", ") ")

        # Áp dụng các mẫu Regex ngữ pháp
        for pattern, repl in self.regex_patterns:
            result = pattern.sub(repl, result)

        # Áp dụng từ điển cụm từ convert -> dịch
        for src, tgt in self.phrase_mappings:
            pattern = re.compile(re.escape(src), re.IGNORECASE)
            result = pattern.sub(tgt, result)

        # Xóa dấu hai chấm bị lặp lại (ví dụ : : hoặc : : )
        result = re.sub(r':\s*:', ':', result)
        result = re.sub(r':\s*,', ':', result)
        result = re.sub(r',\s*:', ':', result)

        # Làm sạch khoảng trắng thừa và dấu câu lệch
        result = re.sub(r'[ \t]+', ' ', result)
        result = re.sub(r' +([,.;:!?])', r'\1', result)
        # Khử ký tự rác chèn né kiểm duyệt (c·hết -> chết, g·iết -> giết, b·ạo đ·ộng -> bạo động)
        result, _ = text_cleaner.clean_all(result)

        # Viết hoa đầu câu và chuẩn hóa đoạn văn
        result = self._capitalize_sentences(result)

        return result.strip()


# ==============================================================================
# HỆ THỐNG AI VĂN HỌC (LLM CONVERT-TO-DỊCH ENGINE)
# Dùng DeepSeek-V3 hoặc Gemini với Prompt chuyên sâu cho Convert
# ==============================================================================

CONVERT_PROMPTS = {
    "xianxia": """Bạn là một đại dịch giả văn học kỳ cựu chuyên dịch và biên tập tiểu thuyết Tiên Hiệp, Kiếm Hiệp, Cổ Phong Trung Quốc sang tiếng Việt.
NHIỆM VỤ: Chuyển đổi đoạn văn bản CONVERT (bản dịch thô / Vietphrase / Hán Việt khô cứng) bên dưới thành một BẢN DỊCH TIỂU THUYẾT VĂN HỌC MƯỢT MÀ, HÀO SẢNG, ĐẬM CHẤT TIÊN HIỆP.

YÊU CẦU BẮT BUỘC:
1. Triệt để xóa bỏ cấu trúc câu ngữ pháp lai căng tiếng Trung (như: "tại... bên trong", "nương theo lấy", "thời gian dần qua", "cái này một cái", "bị người...").
2. Giọng văn hào sảng, cổ phong, uy vũ, câu từ trau chuốt, giàu hình tượng, nhịp văn dứt khoát trong cảnh chiến đấu và sâu lắng trong cảnh tâm trạng.
3. Tuyệt đối giữ chuẩn xác các danh từ riêng: tên nhân vật, địa danh, môn phái, công pháp bí tịch, linh đan, pháp bảo, cảnh giới tu luyện (Luyện Khí, Trúc Cơ, Kim Đan, Nguyên Anh...).
4. Giữ đúng xưng hô Hán Việt: hắn, nàng, y, lão nhân gia, bổn tọa, tiền bối, vãn bối, sư huynh, sư muội, đạo hữu...
5. Giữ nguyên cấu trúc đoạn văn bản và toàn bộ lời thoại.
6. CHỈ TRẢ VỀ NỘI DUNG BẢN DỊCH, không thêm bất kỳ lời bình luận hay giải thích nào.""",

    "fantasy": """Bạn là một đại dịch giả văn học chuyên nghiệp về tiểu thuyết Huyền Huyễn, Dị Giới, Ma Huyễn Tây Phương.
NHIỆM VỤ: Chuyển đổi đoạn văn bản CONVERT thô cứng bên dưới thành một BẢN DỊCH TIỂU THUYẾT KỊCH TÍNH, MƯỢT MÀ VÀ CUỐN HÚT.

YÊU CẦU BẮT BUỘC:
1. Biến các câu cú convert khô cứng thành câu văn tiếng Việt trôi chảy, tự nhiên, sinh động.
2. Tiết tấu dồn dập, gay cấn, khắc họa rõ nét các cảnh ma pháp, đấu khí, triệu hoán thú và chiến trường khốc liệt.
3. Giữ nguyên tên nhân vật, cấp bậc chức nghiệp, trang bị ma pháp.
4. Giữ nguyên đoạn hội thoại và ngắt dòng.
5. CHỈ TRẢ VỀ DUY NHẤT BẢN DỊCH ĐÃ BIÊN TẬP.""",

    "urban": """Bạn là một dịch giả tiểu thuyết Đô Thị, Hiện Đại, Dị Năng chuyên nghiệp.
NHIỆM VỤ: Chuyển đổi đoạn văn bản CONVERT bên dưới thành BẢN DỊCH VĂN PHONG HIỆN ĐẠI, TỰ NHIÊN, MƯỢT MÀ.

YÊU CẦU BẮT BUỘC:
1. Ngôn từ gần gũi, văn phong hiện đại, đối thoại tự nhiên như người Việt nói chuyện hàng ngày, không còn chút dấu vết convert thô.
2. Giữ nguyên tên nhân vật, địa danh, chức vụ, tình tiết truyện.
3. Giữ nguyên định dạng đoạn văn.
4. CHỈ TRẢ VỀ DUY NHẤT BẢN DỊCH TIẾNG VIỆT.""",

    "romance": """Bạn là một dịch giả tiểu thuyết Ngôn Tình, Cổ Đại, Nữ Tần xuất sắc.
NHIỆM VỤ: Chuyển đổi văn bản CONVERT bên dưới thành BẢN DỊCH NGÔN TÌNH TINH TẾ, MỀM MẠI VÀ GIÀU CẢM XÚC.

YÊU CẦU BẮT BUỘC:
1. Văn phong uyển chuyển, tinh tế, giàu nhạc điệu và cảm xúc chân thật.
2. Lời thoại tình cảm, phù hợp với tính cách nhân vật (dịu dàng, bá đạo, ngạo kiều, bi thương...).
3. Giữ nguyên xưng hô và các chi tiết cổ phong/hiện đại.
4. CHỈ TRẢ VỀ DUY NHẤT BẢN DỊCH HOÀN CHỈNH."""
}

class ConvertPolisher:
    def __init__(self, llm_translator: Optional[LLMTranslator] = None):
        self.rules_engine = ConvertRulesEngine()
        self.llm = llm_translator or LLMTranslator()

    def polish_rules(self, text: str) -> str:
        """Xử lý siêu tốc bằng bộ quy tắc offline (0s, 0 token)"""
        return self.rules_engine.polish(text)

    def polish_ai(
        self,
        text: str,
        engine: str = "deepseek",
        genre: str = "xianxia",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        """Xử lý bằng AI LLM (DeepSeek / Gemini) với prompt văn học chuyên sâu"""
        system_prompt = CONVERT_PROMPTS.get(genre, CONVERT_PROMPTS["xianxia"])
        
        # Thêm từ điển tùy chọn nếu có
        dict_hint = ""
        if dict_entries:
            items = list(dict_entries.items())[:50]
            lines = ["\nDANH TỪ / TÊN RIÊNG BẮT BUỘC GIỮ CHUẨN XÁC:"]
            for s, t in items:
                lines.append(f"- {s} => {t}")
            dict_hint = "\n".join(lines) + "\n"

        full_prompt = f"{system_prompt}\n{dict_hint}\nĐoạn văn bản Convert cần chuyển sang truyện dịch:\n\n{text}"

        if "gemini" in engine.lower():
            key = api_key or self.llm.config.get("gemini_api_key", "").strip()
            if not key:
                raise ValueError("Chưa thiết lập Gemini API Key. Vui lòng cấu hình trong Cài Đặt.")
            import requests
            model = "gemini-2.0-flash" if "2.0" in engine else "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192}
            }
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(f"Lỗi Gemini API ({resp.status_code}): {resp.text}")
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif "deepseek" in engine.lower():
            key = api_key or self.llm.config.get("deepseek_api_key", "").strip()
            if not key:
                raise ValueError("Chưa thiết lập DeepSeek API Key. Vui lòng cấu hình trong Cài Đặt.")
            import requests
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt + dict_hint},
                    {"role": "user", "content": f"Chuyển đoạn văn bản convert sau thành truyện dịch văn học hoàn chỉnh:\n\n{text}"}
                ],
                "temperature": 0.4,
                "stream": False
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(f"Lỗi DeepSeek API ({resp.status_code}): {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        else:
            raise ValueError(f"Không hỗ trợ AI Engine '{engine}'")

    def polish_hybrid(
        self,
        text: str,
        engine: str = "deepseek",
        genre: str = "xianxia",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        """Chế độ Hybrid: Lọc thô bằng Rules Engine -> Trau chuốt đỉnh cao bằng AI"""
        cleaned_text = self.rules_engine.polish(text)
        return self.polish_ai(
            text=cleaned_text,
            engine=engine,
            genre=genre,
            api_key=api_key,
            dict_entries=dict_entries
        )

    def polish(
        self,
        text: str,
        mode: str = "rules",
        engine: str = "deepseek",
        genre: str = "xianxia",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None
    ) -> str:
        """Hàm điều hướng tổng quát: rules, ai hoặc hybrid"""
        if mode == "rules":
            return self.polish_rules(text)
        elif mode == "ai":
            return self.polish_ai(text, engine=engine, genre=genre, api_key=api_key, dict_entries=dict_entries)
        elif mode == "hybrid":
            return self.polish_hybrid(text, engine=engine, genre=genre, api_key=api_key, dict_entries=dict_entries)
        else:
            return self.polish_rules(text)

    def stop_batch(self):
        self._is_stopped = True

    def batch_polish_folder(
        self,
        input_folder: str,
        output_folder: str,
        mode: str = "rules",
        engine: str = "deepseek",
        genre: str = "xianxia",
        suffix: str = "_dich",
        status_callback: Optional[Callable[[str, float, str, int, int], None]] = None
    ):
        self._is_stopped = False
        os.makedirs(output_folder, exist_ok=True)

        files = [
            os.path.join(input_folder, f) for f in os.listdir(input_folder)
            if f.lower().endswith(".txt") and not f.startswith(".")
        ]

        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]
        files.sort(key=natural_sort_key)

        total = len(files)
        if total == 0:
            if status_callback:
                status_callback("Không tìm thấy file .txt nào trong thư mục!", 0.0, "", 0, 0)
            return

        for i, fpath in enumerate(files, 1):
            if self._is_stopped:
                if status_callback:
                    status_callback("Đã dừng tiến trình chuyển đổi!", round((i / total) * 100, 1), os.path.basename(fpath), i, total)
                break

            fname = os.path.basename(fpath)
            pct = round(((i - 1) / total) * 100, 1)
            if status_callback:
                status_callback(f"[{i}/{total}] Đang xử lý: {fname}...", pct, fname, i, total)

            # Đọc file với đa mã hóa
            content = ""
            for enc in ["utf-8", "utf-8-sig", "gb18030", "utf-16", "cp1258", "latin1"]:
                try:
                    with open(fpath, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not content.strip():
                continue

            try:
                polished = self.polish(
                    text=content,
                    mode=mode,
                    engine=engine,
                    genre=genre
                )
                base, ext = os.path.splitext(fname)
                out_path = os.path.join(output_folder, f"{base}{suffix}{ext}")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(polished)
            except Exception as file_err:
                if status_callback:
                    status_callback(f"⚠️ Lỗi {fname}: {str(file_err)}", pct, fname, i, total)

        if not self._is_stopped and status_callback:
            status_callback(f"Hoàn tất chuyển đổi {total} chương sang truyện dịch!", 100.0, "", total, total)


# Khởi tạo instance toàn cục
convert_polisher = ConvertPolisher()
