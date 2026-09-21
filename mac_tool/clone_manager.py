#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hệ thống Quản lý Giọng Clone (Voice Cloning Studio)
Tích hợp 80+ giọng mẫu huyền thoại từ XuanAn TTS
Mô phỏng âm sắc đặc trưng từng nhân vật (Châu Tinh Trì, Lại Văn Sâm, Radio Kiếm Hiệp, Tào Tháo...)
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "voices_sample" / "Việt Nam"


# Bảng cấu hình âm sắc đặc trưng (Acoustic Profiles) cho các nhóm giọng mẫu
VOICE_PROFILES = {
    # 1. TIÊN HIỆP & KIẾM HIỆP
    "Radio Kiếm Hiệp": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-22Hz",
        "rate": "-4%",
        "filter": "equalizer=f=110:width_type=h:width=50:g=4,equalizer=f=2800:width_type=h:width=900:g=-2,aecho=0.8:0.35:25:0.18"
    },
    "Vân Phi Dương": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-15Hz",
        "rate": "-2%",
        "filter": "equalizer=f=130:width_type=h:width=60:g=3.5,equalizer=f=3200:width_type=h:width=1000:g=1"
    },
    "Tào Tháo": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-35Hz",
        "rate": "-7%",
        "filter": "equalizer=f=95:width_type=h:width=45:g=6,equalizer=f=3500:width_type=h:width=1000:g=-3"
    },
    "Gia Cát Lượng": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-10Hz",
        "rate": "-5%",
        "filter": "equalizer=f=180:width_type=h:width=80:g=3,equalizer=f=2500:width_type=h:width=800:g=1.5"
    },
    "Hàn Tín": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-18Hz",
        "rate": "-3%",
        "filter": "equalizer=f=120:width_type=h:width=50:g=4"
    },
    "Bạch Dã": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-8Hz",
        "rate": "0%",
        "filter": "equalizer=f=140:width_type=h:width=60:g=2.5"
    },
    "Lạc Phi": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "-5Hz",
        "rate": "-3%",
        "filter": "equalizer=f=260:width_type=h:width=120:g=2"
    },
    "Thiên Hà": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "-2%",
        "filter": "equalizer=f=130:width_type=h:width=60:g=3"
    },
    "Đình Quân": {
        "category": "🗡️ Tiên Hiệp & Kiếm Hiệp",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-15Hz",
        "rate": "-2%",
        "filter": "equalizer=f=120:width_type=h:width=50:g=3"
    },

    # 2. TRUYỆN MA, TRIẾT LÝ & ĐẠO LÝ
    "Giọng kể truyện Ma": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-25Hz",
        "rate": "-12%",
        "filter": "equalizer=f=180:width_type=h:width=90:g=4,aecho=0.75:0.45:50:0.3"
    },
    "Giọng kể truyện trầm": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-28Hz",
        "rate": "-8%",
        "filter": "equalizer=f=100:width_type=h:width=50:g=5,equalizer=f=3200:width_type=h:width=1000:g=-2"
    },
    "Giọng Triết Lý": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-18Hz",
        "rate": "-6%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3.5"
    },
    "Tùng Đặng - Triết Lý": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-16Hz",
        "rate": "-5%",
        "filter": "equalizer=f=140:width_type=h:width=70:g=3.5"
    },
    "Giọng Đạo Lý": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-15Hz",
        "rate": "-5%",
        "filter": "equalizer=f=160:width_type=h:width=80:g=3"
    },
    "Phật Giáo": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-20Hz",
        "rate": "-10%",
        "filter": "equalizer=f=140:width_type=h:width=70:g=4,aecho=0.8:0.3:30:0.2"
    },
    "Phật Pháp": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-20Hz",
        "rate": "-10%",
        "filter": "equalizer=f=140:width_type=h:width=70:g=4,aecho=0.8:0.3:30:0.2"
    },
    "Thiện Tâm": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-14Hz",
        "rate": "-6%",
        "filter": "equalizer=f=160:width_type=h:width=80:g=3"
    },
    "Thiện Tâm (New)": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-14Hz",
        "rate": "-6%",
        "filter": "equalizer=f=160:width_type=h:width=80:g=3"
    },
    "Giọng Trung niên": {
        "category": "👻 Truyện Ma & Triết Lý",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-22Hz",
        "rate": "-4%",
        "filter": "equalizer=f=130:width_type=h:width=60:g=3.5"
    },

    # 3. LỒNG TIẾNG & NGƯỜI NỔI TIẾNG
    "Châu Tinh Trì": {
        "category": "🎬 Lồng Tiếng & Người Nổi Tiếng",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+18Hz",
        "rate": "+10%",
        "filter": "equalizer=f=2600:width_type=h:width=1000:g=4,equalizer=f=200:width_type=h:width=80:g=-2"
    },
    "MC Lại Văn Sâm": {
        "category": "🎬 Lồng Tiếng & Người Nổi Tiếng",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-10Hz",
        "rate": "+2%",
        "filter": "equalizer=f=180:width_type=h:width=80:g=3.5,equalizer=f=2400:width_type=h:width=800:g=2.5"
    },
    "Giọng nữ Hồng Kông": {
        "category": "🎬 Lồng Tiếng & Người Nổi Tiếng",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+8Hz",
        "rate": "+4%",
        "filter": "equalizer=f=2800:width_type=h:width=1000:g=3"
    },
    "HKT": {
        "category": "🎬 Lồng Tiếng & Người Nổi Tiếng",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+12Hz",
        "rate": "+8%",
        "filter": "equalizer=f=2200:width_type=h:width=900:g=3"
    },

    # 4. CAPCUT, REVIEW & MẠNG XÃ HỘI
    "CAPCUT Nam tự tin": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+8Hz",
        "rate": "+14%",
        "filter": "equalizer=f=2600:width_type=h:width=1000:g=3"
    },
    "Capcut Nam (fix lỗi tu vi)": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+6Hz",
        "rate": "+12%",
        "filter": "equalizer=f=2500:width_type=h:width=900:g=3"
    },
    "CAPCUT Nữ hoạt ngôn": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+12Hz",
        "rate": "+15%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=3"
    },
    "Capcut Nữ 1 (fix lỗi tu vi)": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+10Hz",
        "rate": "+12%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=3"
    },
    "Capcut Nữ 2 (fix lỗi tu vi)": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+10Hz",
        "rate": "+12%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=3"
    },
    "Review Truyện": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+4Hz",
        "rate": "+10%",
        "filter": "equalizer=f=2400:width_type=h:width=800:g=2.5"
    },
    "Review Truyện Chữ": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+2Hz",
        "rate": "+8%",
        "filter": "equalizer=f=2200:width_type=h:width=800:g=2.5"
    },
    "Bình luận Bóng đá": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+10Hz",
        "rate": "+16%",
        "filter": "equalizer=f=2800:width_type=h:width=1000:g=3.5"
    },
    "BLV Bún Chả": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+8Hz",
        "rate": "+12%",
        "filter": "equalizer=f=2600:width_type=h:width=900:g=3"
    },
    "Bình luận Quân Sự": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "+2%",
        "filter": "equalizer=f=160:width_type=h:width=80:g=3,equalizer=f=2500:width_type=h:width=800:g=2"
    },
    "Phân tích Quân Sự": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "+2%",
        "filter": "equalizer=f=160:width_type=h:width=80:g=3"
    },
    "Phân tích Công nghệ": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+0Hz",
        "rate": "+6%",
        "filter": "equalizer=f=2200:width_type=h:width=800:g=2"
    },
    "Dương Tin Tức": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-5Hz",
        "rate": "+5%",
        "filter": "equalizer=f=2000:width_type=h:width=800:g=2"
    },
    "Phóng viên Nam": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-4Hz",
        "rate": "+5%",
        "filter": "equalizer=f=180:width_type=h:width=80:g=2.5"
    },
    "Quảng cáo Miền Nam": {
        "category": "📱 Review, CapCut & MXH",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+8Hz",
        "rate": "+8%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=2.5"
    },

    # 5. GIỌNG ĐỌC AUDIO CHUYÊN NGHIỆP (NỮ)
    "Ngọc Huyền": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "0%",
        "filter": "equalizer=f=300:width_type=h:width=150:g=2,equalizer=f=3500:width_type=h:width=1000:g=2"
    },
    "Ngọc Huyền Best": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+3Hz",
        "rate": "-1%",
        "filter": "equalizer=f=300:width_type=h:width=150:g=2.5,equalizer=f=3600:width_type=h:width=1000:g=2.5"
    },
    "Ngọc Huyền 2.0": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+5Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=2"
    },
    "Ngọc Huyền - Mix": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "+1%",
        "filter": "equalizer=f=3400:width_type=h:width=1000:g=2"
    },
    "Ngọc Huyền - prosody": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+2Hz",
        "rate": "-2%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=1.5"
    },
    "Ngọc Huyền Mix 2": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "+1%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=2"
    },
    "Ngọc Huyền New": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+3Hz",
        "rate": "0%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=2"
    },
    "Ban Mai": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+6Hz",
        "rate": "+3%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=2.5"
    },
    "Mai Phương": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+2Hz",
        "rate": "-1%",
        "filter": "equalizer=f=280:width_type=h:width=120:g=2"
    },
    "Mai Phương 1": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+2Hz",
        "rate": "-1%",
        "filter": "equalizer=f=280:width_type=h:width=120:g=2"
    },
    "Hồng Nhung": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+5Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=2"
    },
    "Huyền Trang": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+3Hz",
        "rate": "0%",
        "filter": "equalizer=f=2800:width_type=h:width=1000:g=2"
    },
    "Lan Trinh": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "+1%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=2"
    },
    "Lê Yến": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+5Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3100:width_type=h:width=1000:g=2"
    },
    "Lệ Hằng": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+3Hz",
        "rate": "0%",
        "filter": "equalizer=f=2900:width_type=h:width=1000:g=2"
    },
    "Ngân Nguyễn": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=2"
    },
    "Ngọc Ngan": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "+1%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=2"
    },
    "Nguyệt Nga": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+2Hz",
        "rate": "-1%",
        "filter": "equalizer=f=2800:width_type=h:width=1000:g=2"
    },
    "Phương Như": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+5Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3100:width_type=h:width=1000:g=2"
    },
    "Thảo Chi": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+6Hz",
        "rate": "+3%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=2.5"
    },
    "Thảo Trinh": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+5Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3100:width_type=h:width=1000:g=2"
    },
    "Thu Hà": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+3Hz",
        "rate": "0%",
        "filter": "equalizer=f=2900:width_type=h:width=1000:g=2"
    },
    "Tường Vy": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+5Hz",
        "rate": "+2%",
        "filter": "equalizer=f=3200:width_type=h:width=1000:g=2"
    },
    "Google - Nữ 1": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+4Hz",
        "rate": "0%",
        "filter": "equalizer=f=3000:width_type=h:width=1000:g=2"
    },
    "Google - Nữ 2": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+2Hz",
        "rate": "-2%",
        "filter": "equalizer=f=2800:width_type=h:width=1000:g=2"
    },
    "Giọng bé gái": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)",
        "gender": "female",
        "base_voice": "vi-VN-HoaiMyNeural",
        "pitch": "+25Hz",
        "rate": "+6%",
        "filter": "equalizer=f=3500:width_type=h:width=1200:g=4,equalizer=f=200:width_type=h:width=80:g=-3"
    },

    # 6. GIỌNG ĐỌC AUDIO CHUYÊN NGHIỆP (NAM)
    "Bảo Trung": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "-1%",
        "filter": "equalizer=f=140:width_type=h:width=60:g=3.5"
    },
    "Anh Khôi": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-8Hz",
        "rate": "+1%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Mạnh Dũng": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-15Hz",
        "rate": "-2%",
        "filter": "equalizer=f=130:width_type=h:width=60:g=4"
    },
    "Minh Quân": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-10Hz",
        "rate": "0%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Minh Quân1": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-10Hz",
        "rate": "0%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Đinh Cường": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-14Hz",
        "rate": "-2%",
        "filter": "equalizer=f=140:width_type=h:width=60:g=3.5"
    },
    "Duy Onyx": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "0%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Sơn Trần": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-10Hz",
        "rate": "0%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Nam Trung": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-14Hz",
        "rate": "-2%",
        "filter": "equalizer=f=140:width_type=h:width=60:g=3.5"
    },
    "Nam Minh 1": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "0Hz",
        "rate": "0%",
        "filter": ""
    },
    "Adam": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-15Hz",
        "rate": "-3%",
        "filter": "equalizer=f=130:width_type=h:width=60:g=3.5"
    },
    "Antoni": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "0%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Antoni New (11labs)": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "-12Hz",
        "rate": "0%",
        "filter": "equalizer=f=150:width_type=h:width=70:g=3"
    },
    "Giọng bé trai": {
        "category": "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
        "gender": "male",
        "base_voice": "vi-VN-NamMinhNeural",
        "pitch": "+22Hz",
        "rate": "+5%",
        "filter": "equalizer=f=2800:width_type=h:width=1000:g=3.5,equalizer=f=180:width_type=h:width=80:g=-3"
    }
}


class CloneVoiceManager:
    """Quản lý kho 80+ giọng mẫu và các bộ lọc âm sắc mô phỏng nhân vật"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CloneVoiceManager, cls).__new__(cls)
            cls._instance._init_voices()
        return cls._instance

    def _init_voices(self):
        self.voices = []
        if not SAMPLE_DIR.exists():
            return

        # Quét toàn bộ file .wav trong thư mục sample
        wav_files = sorted([f for f in os.listdir(SAMPLE_DIR) if f.endswith(".wav")])

        for fname in wav_files:
            voice_id = fname[:-4]
            profile = VOICE_PROFILES.get(voice_id, {
                "category": "🎙️ Giọng Khác",
                "gender": "male" if "Nam" in voice_id else "female",
                "base_voice": "vi-VN-NamMinhNeural" if "Nam" in voice_id else "vi-VN-HoaiMyNeural",
                "pitch": "0Hz",
                "rate": "0%",
                "filter": ""
            })

            has_sample = os.path.isfile(SAMPLE_DIR / fname)
            self.voices.append({
                "id": voice_id,
                "name": voice_id,
                "category": profile.get("category", "🎙️ Giọng Khác"),
                "gender": profile.get("gender", "male"),
                "base_voice": profile.get("base_voice", "vi-VN-NamMinhNeural"),
                "pitch": profile.get("pitch", "0Hz"),
                "rate": profile.get("rate", "0%"),
                "filter": profile.get("filter", ""),
                "has_sample": has_sample,
                "sample_filename": fname
            })

    def get_all_clone_voices(self) -> List[Dict]:
        return self.voices

    def get_voice_by_id(self, voice_id: str) -> Optional[Dict]:
        if not voice_id:
            return None
        if voice_id.startswith("clone:"):
            voice_id = voice_id[6:].strip()
        import unicodedata
        v_nfc = unicodedata.normalize('NFC', voice_id)
        v_nfd = unicodedata.normalize('NFD', voice_id)
        for v in self.voices:
            vid_nfc = unicodedata.normalize('NFC', v["id"])
            vid_nfd = unicodedata.normalize('NFD', v["id"])
            if v["id"] == voice_id or vid_nfc == v_nfc or vid_nfd == v_nfd:
                return v
        return None

    def get_sample_audio_path(self, voice_id: str) -> Optional[str]:
        if not voice_id:
            return None
        if voice_id.startswith("clone:"):
            voice_id = voice_id[6:].strip()
        import unicodedata
        v_nfc = unicodedata.normalize('NFC', voice_id)
        v_nfd = unicodedata.normalize('NFD', voice_id)
        if SAMPLE_DIR.exists():
            for f in os.listdir(SAMPLE_DIR):
                if not f.endswith(".wav"):
                    continue
                f_name = f[:-4]
                if f_name == voice_id or unicodedata.normalize('NFC', f_name) == v_nfc or unicodedata.normalize('NFD', f_name) == v_nfd:
                    return str(SAMPLE_DIR / f)
        return None

    def apply_profile_effects(self, input_file: str, output_file: str, profile: Dict) -> str:
        """Áp dụng bộ lọc âm sắc (equalizer, echo, pitch) cho file audio MP3"""
        filter_str = profile.get("filter", "")
        if not filter_str:
            return input_file

        try:
            cmd = [
                "ffmpeg", "-y", "-i", input_file,
                "-af", filter_str,
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                output_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_file
        except Exception as e:
            print(f"[CloneManager] Cảnh báo lỗi áp bộ lọc: {e}, dùng file gốc")
            return input_file


clone_manager = CloneVoiceManager()
