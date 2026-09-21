#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tiên Tôn Tool: Bộ chuẩn hóa và tích hợp Thuật Ngữ Truyện Dịch
Tác giả: Antigravity - Tiên Tôn Tool Team
Mục tiêu:
1. Đọc toàn bộ 4,817 thuật ngữ trích xuất từ thuat_ngu_muse_spark.txt
2. Sửa toàn diện các từ dịch thô/lỗi:
   - Tên riêng, nhân vật, địa danh, thần vật bắt buộc chuyển chuẩn Hán Việt:
     + Thần Mưa -> Vũ Thần, Thần Mưa pháp chỉ -> Vũ Thần pháp chỉ
     + trắng lá gan -> Bạch Can, bạch can -> Bạch Can
     + bảy Thần -> Thất Thần, bảy Thần hạ giới -> Thất Thần hạ giới
     + Bốn trưởng lão -> Tứ Trưởng Lão, Vệ gia bốn Hoàng -> Vệ Gia Tứ Hoàng
     + bất hủ con trai -> Bất Hủ Chi Tử, Tiên đạo con trai -> Tiên Đạo Chi Tử
     + cấm khu đứng đầu -> Cấm Khu Chi Chủ
     + Gió Thiên Hành -> Phong Hành Thiên, gãy Hồng -> Đoạn Hồng, Tử Viêm bay -> Tử Viêm Phi
     + thủ Các lão người -> Thủ Các Lão Nhân, Tiên Điện người hầu -> Tiên Điện Bộc Tòng
     + mười động thiên -> Thập Động Thiên, chín tầng trời -> Cửu Trọng Thiên
     + ...
   - Từ lóng game / Try hard / Cày cuốc:
     + lá gan đế -> trùm cày cuốc / Gan Đế
     + nổ lá gan -> bạo gan cày cuốc, mở lá gan -> dốc sức cày cuốc
     + lá gan nhập đạo -> lấy cày cuốc nhập đạo
3. Khử sạch các cảnh báo '# ⚠', chọn bản dịch chuẩn xác nhất.
4. Tích hợp trực tiếp vào mac_tool/convert_dict.json, mac_tool/names.txt và mac_tool/convert_polisher.py
"""

import os
import sys
import re
import json
from typing import Dict, List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLOSSARY_FILE = os.path.join(BASE_DIR, "thuat_ngu_muse_spark.txt")
CHUAN_FILE = os.path.join(BASE_DIR, "thuat_ngu_chuan.txt")
MAC_TOOL_DIR = os.path.join(BASE_DIR, "mac_tool")
CONVERT_DICT_FILE = os.path.join(MAC_TOOL_DIR, "convert_dict.json")
NAMES_TXT_FILE = os.path.join(MAC_TOOL_DIR, "names.txt")

# ==============================================================================
# BẢNG TRA CỨU ĐIỀU CHỈNH THUẬT NGỮ CHUẨN XÁC (MANUAL HIGH-PRIORITY OVERRIDES)
# ==============================================================================
EXPLICIT_CORRECTIONS = {
    # Nhân vật & Danh xưng
    "Thần Mưa": "Vũ Thần",
    "thần mưa": "Vũ Thần",
    "mưa thần": "Vũ Thần",
    "Vũ Tộc Thần Mưa": "Vũ Tộc Vũ Thần",
    "Thần Mưa miếu": "Vũ Thần Miếu",
    "Thần Mưa cung": "Vũ Thần Cung",
    "Thần Mưa pháp chỉ": "Vũ Thần pháp chỉ",
    "thần mưa pháp chỉ": "Vũ Thần pháp chỉ",
    "Thần Mưa pháp tướng": "Vũ Thần pháp tướng",
    "Pháp chỉ Thần Mưa": "Vũ Thần pháp chỉ",
    "trắng lá gan": "Bạch Can",
    "bạch lá gan": "Bạch Can",
    "Bạch can": "Bạch Can",
    "bạch can": "Bạch Can",
    "bạch can tên ma đầu này": "ma đầu Bạch Can này",
    "Bạch Can tên ma đầu này": "ma đầu Bạch Can này",
    "bảy Thần": "Thất Thần",
    "bảy thần": "Thất Thần",
    "bảy Thần hạ giới": "Thất Thần hạ giới",
    "Bảy Thần Hạ Giới": "Thất Thần hạ giới",
    "bảy vị Tiên Vương": "Thất Đại Tiên Vương",
    "Bốn trưởng lão": "Tứ Trưởng Lão",
    "bốn trưởng lão": "Tứ Trưởng Lão",
    "ba Đại Chí Tôn": "Tam Đại Chí Tôn",
    "Vệ gia bốn Hoàng": "Vệ Gia Tứ Hoàng",
    "bất hủ con trai": "Bất Hủ Chi Tử",
    "con trai của bất hủ": "Bất Hủ Chi Tử",
    "Tiên đạo con trai": "Tiên Đạo Chi Tử",
    "tiên đạo con trai": "Tiên Đạo Chi Tử",
    "Con trai của Tiên đạo": "Tiên Đạo Chi Tử",
    "Cấm khu đứng đầu": "Cấm Khu Chi Chủ",
    "cấm khu đứng đầu": "Cấm Khu Chi Chủ",
    "Cấm Khu chi Chủ": "Cấm Khu Chi Chủ",
    "Chúa tể Cấm khu": "Cấm Khu Chi Chủ",
    "Gió Thiên Hành": "Phong Hành Thiên",
    "gió thiên hành": "Phong Hành Thiên",
    "gãy Hồng": "Đoạn Hồng",
    "Hắc Ám Tiên Kim người": "Hắc Ám Tiên Kim Nhân",
    "Người Hắc Ám Tiên Kim": "Hắc Ám Tiên Kim Nhân",
    "Tử Viêm bay": "Tử Viêm Phi",
    "thủ Các lão người": "Thủ Các Lão Nhân",
    "lão già giữ Tàng Kinh Các": "Thủ Các Lão Nhân",
    "thủ thành người": "Thủ Thành Nhân",
    "Tiên Điện người hầu": "Tiên Điện Bộc Tòng",
    "tiên điện người hầu": "Tiên Điện Bộc Tòng",
    "Tiên Điện người thừa kế": "Tiên Điện Truyền Nhân",
    "tiên điện người thừa kế": "Tiên Điện Truyền Nhân",
    "áo xanh người": "Thanh Y Nhân",
    "người áo xanh": "Thanh Y Nhân",
    "người phong ấn": "Phong Ấn Giả",
    "Người phong ấn": "Phong Ấn Giả",
    "con thỏ nhỏ": "Thái Âm Ngọc Thỏ",
    "Con Thỏ Nhỏ": "Thái Âm Ngọc Thỏ",
    "Thái Âm Ngọc Thỏ": "Thái Âm Ngọc Thỏ",
    "cô gái tóc vàng kia": "Kim Phát Thiếu Nữ",
    "cô gái tóc vàng": "Kim Phát Thiếu Nữ",
    "nam tử tóc vàng": "Kim Phát Nam Tử",
    "người hầu lông vàng": "Hoàng Mao Bộc Tòng",
    "lông vàng": "Kim Mao",
    "lông vàng lưu": "Kim Mao Lưu",
    "mây vàng biển": "Kim Vân Hải",
    "Mây vàng Heisen": "Kim Vân Hải",
    "Vân Kim Hải": "Kim Vân Hải",
    "Mặt trời vàng": "Hoàng Kim Thái Dương",
    "thiếu niên tóc xanh": "Thanh Phát Thiếu Niên",
    "tóc đỏ thiếu niên": "Hồng Phát Thiếu Niên",
    "Hồng Phát thiếu niên": "Hồng Phát Thiếu Niên",

    # Địa danh & Thế lực
    "Ba ngàn đạo châu": "Tam Thiên Đạo Châu",
    "ba ngàn đạo châu": "Tam Thiên Đạo Châu",
    "3000 thềm đá": "Tam Thiên Thạch Giai",
    "3000 đá xanh cổ lộ": "Tam Thiên Thanh Thạch Cổ Lộ",
    "3000 đường đá xanh": "Tam Thiên Thanh Thạch Cổ Lộ",
    "hai viện": "Lưỡng Viện",
    "Hai Viện": "Lưỡng Viện",
    "bất diệt đỉnh núi": "Bất Diệt Sơn Đỉnh",
    "chiến trường thứ hai": "Đệ Nhị Chiến Trường",
    "Màu vàng biển": "Hoàng Kim Hải",
    "màu đen giác đấu trường": "Hắc Sắc Giác Đấu Trường",
    "mây đen ma thổ": "Hắc Vân Ma Thổ",
    "Mây Đen Ma Thổ": "Hắc Vân Ma Thổ",
    "mây đen tộc": "Hắc Vân Tộc",
    "Mây Đen tộc": "Hắc Vân Tộc",
    "Núi bạch ngọc": "Bạch Ngọc Sơn",
    "Phân Bảo sườn núi": "Phân Bảo Nhai",
    "thời gian biển": "Thời Gian Chi Hải",
    "Biển Thời Gian": "Thời Gian Chi Hải",

    # Cảnh giới
    "Thần lửa cảnh": "Thần Hỏa Cảnh",
    "Thần Hỏa cảnh": "Thần Hỏa Cảnh",
    "nhóm lửa thần hỏa": "thắp lên Thần Hỏa",
    "nhóm lửa bản thân": "điểm nhiên bản thân",
    "10 đại động thiên": "Thập Đại Động Thiên",
    "mười đại động thiên": "Thập Đại Động Thiên",
    "thập đại động thiên": "Thập Đại Động Thiên",
    "mười động thiên": "Thập Động Thiên",
    "mười Động Thiên cảnh": "Thập Động Thiên Cảnh",
    "mười động thiên cực cảnh": "Thập Động Thiên Cực Cảnh",
    "cực cảnh mười động thiên": "Thập Động Thiên Cực Cảnh",
    "Mười động thiên hóa thần vòng": "Thập Động Thiên Hóa Thần Hoàn",
    "Mười động thiên hóa thần hoàn": "Thập Động Thiên Hóa Thần Hoàn",
    "mười động thiên hóa thần hoàn": "Thập Động Thiên Hóa Thần Hoàn",
    "mười động thiên hợp nhất": "Thập Động Thiên Hợp Nhất",
    "Mười động thiên hợp nhất": "Thập Động Thiên Hợp Nhất",
    "mười động thiên quy nhất": "Thập Động Thiên Quy Nhất",
    "Mười Động Thiên Quy Nhất": "Thập Động Thiên Quy Nhất",
    "thứ mười động thiên": "Đệ Thập Động Thiên",
    "Thứ Mười Động Thiên": "Đệ Thập Động Thiên",
    "chín động thiên": "Cửu Động Thiên",
    "tám động thiên": "Bát Động Thiên",
    "bảy động thiên": "Thất Động Thiên",
    "Bảy Động Thiên": "Thất Động Thiên",
    "Thứ bảy động thiên": "Đệ Thất Động Thiên",
    "Động Thiên thứ bảy": "Đệ Thất Động Thiên",
    "sáu động thiên": "Lục Động Thiên",
    "thứ sáu miệng động thiên": "Đệ Lục Động Thiên",
    "Động Thiên thứ sáu": "Đệ Lục Động Thiên",
    "ba đạo tiên khí": "Tam Đạo Tiên Khí",
    "Hai đạo tiên khí": "Lưỡng Đạo Tiên Khí",
    "đạo thứ ba tiên khí": "Đệ Tam Đạo Tiên Khí",
    "đạo thứ hai tiên khí": "Đệ Nhị Đạo Tiên Khí",
    "đạo thứ hai": "Đệ Nhị Đạo Tiên Khí",
    "100 ngàn cân cực cảnh": "Cực Cảnh Thập Vạn Cân",
    "mười vạn cân cực cảnh": "Cực Cảnh Thập Vạn Cân",
    "duy nhất động thiên": "Duy Nhất Động Thiên",
    "nhục thân động thiên": "Nhục Thân Động Thiên",
    "mười hung": "Thập Hung",
    "Thập Hung": "Thập Hung",
    "chín tầng trời": "Cửu Trọng Thiên",
    "Chín tầng trời": "Cửu Trọng Thiên",
    "trên chín tầng trời": "trên Cửu Trọng Thiên",
    "Trên Chín Tầng Trời": "trên Cửu Trọng Thiên",

    # Công pháp & Kỹ năng
    "3000 cánh đạo sen": "Tam Thiên Cánh Đạo Liên",
    "Đạo Sen Ba Ngàn Cánh": "Tam Thiên Cánh Đạo Liên",
    "3000 Đại Đạo lửa": "Tam Thiên Đạo Hỏa",
    "ba ngàn đạo lửa": "Tam Thiên Đạo Hỏa",
    "ba ngàn đạo hỏa": "Tam Thiên Đạo Hỏa",
    "Ba Ngàn Đạo Hỏa": "Tam Thiên Đạo Hỏa",
    "Ba ngàn đạo lửa - nuốt": "Tam Thiên Đạo Hỏa - Thôn",
    "Ba ngàn đạo lửa - sinh": "Tam Thiên Đạo Hỏa - Sinh",
    "Ba ngàn đạo lửa - sét": "Tam Thiên Đạo Hỏa - Lôi",
    "Ba ngàn đạo lửa - tâm": "Tam Thiên Đạo Hỏa - Tâm",
    "bảy màu thần kiều": "Thất Thải Thần Kiều",
    "cầu thần bảy màu": "Thất Thải Thần Kiều",
    "cầu bảy màu": "Thất Thải Kiều",
    "chín tầng phòng ngự đại trận": "Cửu Tầng Phòng Ngự Đại Trận",
    "Cửu tầng phòng ngự đại trận": "Cửu Tầng Phòng Ngự Đại Trận",
    "chín tầng trời lôi điện": "lôi điện Cửu Trọng Thiên",
    "lôi điện cửu trọng thiên": "lôi điện Cửu Trọng Thiên",
    "chín tầng đại trận": "Cửu Tầng Đại Trận",
    "chín tầng trời lôi kiếp": "Cửu Trọng Thiên lôi kiếp",
    "Tiếng sấm chín tầng trời": "Lôi minh Cửu Trọng Thiên",
    "kêu mưa gọi gió": "hô mưa gọi gió",
    "màu đen thần diễm": "Hắc Sắc Thần Diễm",
    "mưa đao đá": "đá mưa đao",
    "Mưa đạo che trời": "Vũ Đạo Già Thiên",
    "mười động thiên Hóa Thần vòng dị tượng": "Thập Động Thiên Hóa Thần Hoàn dị tượng",
    "Mười Động Thiên Hóa Thần Vòng dị tượng": "Thập Động Thiên Hóa Thần Hoàn dị tượng",
    "Nghiêng gió mưa phùn chém trăng sao!": "Tà Phong Tế Vũ Trảm Tinh Nguyệt!",
    "nhỏ mưa xuống thuật": "Thuật giáng mưa nhỏ",
    "thái cổ Chu Tước mười đánh": "Thái Cổ Chu Tước Thập Kích",
    "hỏa diễm chi hoa": "ngọn lửa chi hoa",

    # Pháp bảo & Vật phẩm
    "9 tầng tiên kim bảo tháp": "Cửu Tầng Tiên Kim Bảo Tháp",
    "bảo tháp tiên kim chín tầng": "Cửu Tầng Tiên Kim Bảo Tháp",
    "chín tầng tháp": "Cửu Tầng Bảo Tháp",
    "Bảo tháp chín tầng": "Cửu Tầng Bảo Tháp",
    "Quỷ gia kiếm": "Đoạn Kiếm Quỷ Gia",
    "Kiếm Gãy Quỷ Gia": "Đoạn Kiếm Quỷ Gia",
    "Quỷ gia kiếm gãy": "Đoạn Kiếm Quỷ Gia",
    "Quỷ gia kiếm mẻ": "Đoạn Kiếm Quỷ Gia",
    "Kiếm Mẻ Quỷ Gia": "Đoạn Kiếm Quỷ Gia",
    "kiếm gãy Quỷ gia": "Đoạn Kiếm Quỷ Gia",
    "kiếm gãy": "đoạn kiếm",
    "Mưa tinh thạch": "Vũ Tinh Thạch",
    "Vũ Tinh Thạch": "Vũ Tinh Thạch",
    "mưa ánh sáng": "quang vũ",
    "quang vũ": "quang vũ",
    "lông ánh sáng": "quang vũ",
    "thánh khiết quang vũ": "thánh khiết quang vũ",
    "lông thần": "thần vũ",
    "ngũ sắc thần Vũ": "Ngũ Sắc Thần Vũ",
    "độc giác": "Độc Giác",
    "Độc Giác": "Độc Giác",
    "sừng đơn": "Độc Giác",
    "màu đen cổ thuyền": "Hắc Sắc Cổ Thuyền",
    "cổ thuyền màu đen": "Hắc Sắc Cổ Thuyền",
    "nhuốm máu cổ thuyền màu đen": "Hắc Sắc Cổ Thuyền Nhuốm Máu",
    "màu đen mai rùa": "Hắc Sắc Quy Giáp",
    "màu đen nguyên thần kiếm thai": "Hắc Sắc Nguyên Thần Kiếm Thai",

    # Dị thú
    "chín đầu Cự Xà": "Cửu Đầu Cự Xà",
    "chín đầu lớn đuôi cáo": "chín chiếc đuôi hồ ly lớn",
    "lửa tằm": "Hỏa Tằm",
    "Tằm lửa": "Hỏa Tằm",
    "lửa đỏ Kim Nghê Thú": "Xích Hỏa Kim Nghê Thú",
    "Kim Nghê Thú lửa đỏ": "Xích Hỏa Kim Nghê Thú",
    "màu vàng Đại Bằng": "Hoàng Kim Đại Bằng",
    "màu đen cá lớn": "Hắc Sắc Cự Ngư",
    "Màu đen độc giác gấu nâu": "Hắc Sắc Độc Giác Hùng",
    "nhện vàng": "Hoàng Kim Chu Thù",
    "thái cổ nhện vàng": "Thái Cổ Kim Chu",
    "Kim Xà": "Kim Xà",
    "Kim Xà kiếm": "Kim Xà Kiếm",
    "màu vàng Hầu Vương": "Hoàng Kim Hầu Vương",
    "màu đỏ thần cầm": "Xích Hỏa Thần Cầm",
    "đỏ thẫm Mãng Ngưu": "Xích Sắc Mãng Ngưu",
    "đỏ vảy heo": "Xích Lân Trư",
    "bốn màu Hạc": "Tứ Sắc Hạc",
    "Hạc Bốn Màu": "Tứ Sắc Hạc",

    # Từ lóng & Game (Try hard / Cày cuốc)
    "can kinh nghiệm": "cày kinh nghiệm",
    "lá gan": "cày cuốc",
    "lá gan bên trên": "cày lên",
    "lá gan kinh nghiệm": "cày kinh nghiệm",
    "lá gan độ thuần thục": "cày độ thành thạo",
    "lá gan nhập đạo": "lấy cày cuốc nhập đạo",
    "Lấy lá gan nhập đạo": "lấy cày cuốc nhập đạo",
    "Lấy lá gan nhập đạo.": "Lấy cày cuốc nhập đạo",
    "lấy lá gan nhập đạo": "lấy cày cuốc nhập đạo",
    "toàn thân đều là lá gan": "khắp người tràn ngập tinh thần cày cuốc",
    "lá gan thành": "cày thành",
    "lá gan xong": "cày xong",
    "lá gan đi lên": "cày lên",
    "Lá gan đế": "Trùm cày cuốc",
    "lá gan đế": "trùm cày cuốc",
    "lá gan đế bổn đế": "Bản đế cày cuốc",
    "lá gan đế thiên phú": "thiên phú cày cuốc",
    "mở lá gan": "dốc sức cày cuốc",
    "nổ lá gan": "bạo gan cày cuốc",
    "nổ lá gan trạng thái": "trạng thái bạo gan cày cuốc",
    "khi tiến vào nổ lá gan trạng thái lúc": "khi bước vào trạng thái bạo gan cày cuốc",
    "tiến vào nổ lá gan trạng thái lúc": "bước vào trạng thái bạo gan cày cuốc",
    "nổ lá gan trạng thái lúc": "trạng thái bạo gan cày cuốc",
    "lá gan trò chơi": "cày game",
    "lá gan đến": "cày lên",
    "lá gan tới": "cày tới",
    "xoát điểm kinh nghiệm": "cày điểm kinh nghiệm",
    "xoát quái": "cày quái",
    "xoát": "cày",
    "bảng trò chơi": "bảng giao diện trò chơi",
    "thương thành nhiệm vụ chờ công năng": "thương thành, nhiệm vụ và các tính năng",
}

def clean_and_normalize_term(src: str, tgt: str, category: str) -> str:
    """Chuẩn hóa thuật ngữ sang Hán Việt văn học hoặc từ thuần Việt mượt mà"""
    src_clean = src.strip()
    tgt_clean = tgt.strip()

    # 1. Kiểm tra bảng ghi đè thủ công ưu tiên cao nhất
    if src_clean in EXPLICIT_CORRECTIONS:
        return EXPLICIT_CORRECTIONS[src_clean]
    if tgt_clean in EXPLICIT_CORRECTIONS:
        return EXPLICIT_CORRECTIONS[tgt_clean]

    # Kiểm tra không phân biệt hoa thường với các từ nhạy cảm
    src_lower = src_clean.lower()
    tgt_lower = tgt_clean.lower()
    for key, val in EXPLICIT_CORRECTIONS.items():
        if key.lower() == src_lower:
            return val

    # 2. Xử lý các tiền tố / hậu tố dịch máy thô lậu
    # "Thần Mưa ..." -> "Vũ Thần ..."
    if "thần mưa" in tgt_lower or "thần mưa" in src_lower:
        tgt_clean = re.sub(r'\bthần mưa\b', 'Vũ Thần', tgt_clean, flags=re.IGNORECASE)
        tgt_clean = re.sub(r'\bThần Mưa\b', 'Vũ Thần', tgt_clean)

    # "lá gan" trong game slang
    if category in ["Từ lóng/Game", "Khác"]:
        if "nổ lá gan" in tgt_lower:
            tgt_clean = re.sub(r'\bnổ lá gan\b', 'bạo gan cày cuốc', tgt_clean, flags=re.IGNORECASE)
        if "lá gan đế" in tgt_lower:
            tgt_clean = re.sub(r'\blá gan đế\b', 'trùm cày cuốc', tgt_clean, flags=re.IGNORECASE)
        if "lá gan" in tgt_lower and not any(w in tgt_lower for w in ["gan ruột", "gan mật", "bảo vệ gan"]):
            tgt_clean = re.sub(r'\blá gan\b', 'cày cuốc', tgt_clean, flags=re.IGNORECASE)

    # "con trai của ..." hoặc "... con trai" -> "... Chi Tử"
    if "con trai của " in tgt_lower:
        base = re.sub(r'^[Cc]on trai của\s+', '', tgt_clean).strip()
        tgt_clean = f"{base} Chi Tử"
    elif tgt_lower.endswith(" con trai"):
        base = tgt_clean[:-9].strip()
        tgt_clean = f"{base} Chi Tử"

    # "chúa tể ...", "... đứng đầu" -> "... Chi Chủ"
    if tgt_lower.endswith(" đứng đầu"):
        base = tgt_clean[:-9].strip()
        tgt_clean = f"{base} Chi Chủ"

    # "người hầu ..." -> "... Bộc Tòng"
    if tgt_lower.startswith("người hầu "):
        base = tgt_clean[10:].strip()
        tgt_clean = f"{base} Bộc Tòng"

    # "người thừa kế ..." -> "... Truyền Nhân"
    if tgt_lower.startswith("người thừa kế "):
        base = tgt_clean[14:].strip()
        tgt_clean = f"{base} Truyền Nhân"
    elif tgt_lower.endswith(" người thừa kế"):
        base = tgt_clean[:-14].strip()
        tgt_clean = f"{base} Truyền Nhân"

    # 3. Chuẩn hóa Title Case cho danh từ riêng
    if category in ["Nhân vật", "Địa danh/Thế lực", "Cảnh giới"]:
        words = tgt_clean.split()
        if len(words) <= 6:
            # Viết hoa các chữ cái đầu từ nếu là tên riêng
            tgt_clean = " ".join([w.capitalize() if not w.isupper() else w for w in words])

    return tgt_clean


def main():
    print("=" * 65)
    print("🚀 BẮT ĐẦU CHUẨN HÓA THUẬT NGỮ TIÊN TÔN TOOL...")
    print(f"📖 File gốc: {GLOSSARY_FILE}")
    print("=" * 65)

    if not os.path.exists(GLOSSARY_FILE):
        print(f"❌ Không tìm thấy file: {GLOSSARY_FILE}")
        return

    with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_entries = []
    convert_dict = {}  # {src: tgt}
    names_dict = {}    # {chinese/name: vietnamese}

    current_sec = ""
    total_raw = 0
    modified_count = 0

    output_lines = []

    for line in lines:
        line_str = line.strip()

        # Giữ nguyên header
        if line_str.startswith("# =") or line_str.startswith("# Ngày:") or line_str.startswith("# Định dạng:") or line_str.startswith("# Trích xuất"):
            output_lines.append(line_str)
            continue

        if line_str.startswith("## "):
            current_sec = line_str
            output_lines.append("\n" + line_str)
            continue

        # Bỏ qua dòng cảnh báo '# ⚠' cũ vì ta sẽ giải quyết triệt để
        if line_str.startswith("# ⚠"):
            continue

        if not line_str or line_str.startswith("#"):
            continue

        if "=>" in line_str:
            total_raw += 1
            parts = line_str.split("=>")
            src = parts[0].strip()
            rest = parts[1].strip()

            subparts = [p.strip() for p in rest.split("|")]
            raw_tgt = subparts[0]
            cat = subparts[1] if len(subparts) > 1 else ""
            note = subparts[2] if len(subparts) > 2 else ""

            # Chuẩn hóa bản dịch
            norm_tgt = clean_and_normalize_term(src, raw_tgt, cat)

            if norm_tgt != raw_tgt:
                modified_count += 1

            # Lưu vào từ điển convert -> dịch
            if src.lower() != norm_tgt.lower():
                convert_dict[src] = norm_tgt
                # Thêm cả biến thể chữ thường nếu từ gốc viết hoa hoặc ngược lại
                if src[0].isupper():
                    convert_dict[src.lower()] = norm_tgt

            cleaned_line = f"{src} => {norm_tgt} | {cat} | {note}".strip()
            output_lines.append(cleaned_line)

    # Thêm toàn bộ các từ trong EXPLICIT_CORRECTIONS vào convert_dict để đảm bảo 100% bao phủ
    for s, t in EXPLICIT_CORRECTIONS.items():
        convert_dict[s] = t
        if s[0].isupper():
            convert_dict[s.lower()] = t

    print(f"📊 Tổng thuật ngữ đã quét : {total_raw}")
    print(f"✨ Thuật ngữ đã tinh chỉnh : {modified_count}")
    print(f"📚 Số cặp chuyển đổi Convert: {len(convert_dict)}")

    # 1. Ghi đè file thuat_ngu_muse_spark.txt đã chuẩn hóa sạch bóng
    with open(GLOSSARY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")
    print(f"✅ Đã cập nhật file từ điển sạch: {GLOSSARY_FILE}")

    # 2. Ghi ra file thuat_ngu_chuan.txt
    with open(CHUAN_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")
    print(f"✅ Đã xuất bản từ điển chuẩn: {CHUAN_FILE}")

    # 3. Xuất file mac_tool/convert_dict.json cho Rules Engine đọc trực tiếp
    # Sắp xếp theo độ dài khóa giảm dần (từ dài ưu tiên trước)
    sorted_dict = dict(sorted(convert_dict.items(), key=lambda item: len(item[0]), reverse=True))
    with open(CONVERT_DICT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_dict, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã xuất từ điển Offline Engine: {CONVERT_DICT_FILE}")

    # 4. Xuất file mac_tool/convert_dict.txt dạng dòng ngắn gọn
    convert_txt_file = os.path.join(MAC_TOOL_DIR, "convert_dict.txt")
    with open(convert_txt_file, "w", encoding="utf-8") as f:
        f.write("# TỪ ĐIỂN CHUYỂN ĐỔI CONVERT SANG TRUYỆN DỊCH (TIÊN TÔN TOOL)\n")
        f.write("# Tự động cập nhật từ kho thuật ngữ Muse Spark\n")
        for s, t in sorted_dict.items():
            f.write(f"{s}={t}\n")
    print(f"✅ Đã xuất từ điển text: {convert_txt_file}")

    print("=" * 65)
    print("🎉 HOÀN TẤT BƯỚC CHUẨN HÓA VÀ TÍCH HỢP TỪ ĐIỂN!")
    print("=" * 65)

if __name__ == "__main__":
    main()
