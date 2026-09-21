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
        self._init_dict_engine()

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

            # Try Hard / Cày cuốc / Slang tiểu thuyết mạng
            ("lấy lá gan nhập đạo", "lấy cày cuốc nhập đạo"),
            ("toàn thân đều là lá gan", "khắp người tràn ngập tinh thần cày cuốc"),
            ("khi tiến vào nổ lá gan trạng thái lúc", "khi bước vào trạng thái bạo gan cày cuốc"),
            ("tiến vào nổ lá gan trạng thái lúc", "bước vào trạng thái bạo gan cày cuốc"),
            ("nổ lá gan trạng thái lúc", "trạng thái bạo gan cày cuốc"),
            ("nổ lá gan trạng thái", "trạng thái bạo gan cày cuốc"),
            ("nổ lá gan", "bạo gan cày cuốc"),
            ("lá gan trò chơi", "cày game"),
            ("lá gan đến", "cày lên"),
            ("lá gan tới", "cày tới"),
            ("lá gan đế", "trùm cày cuốc"),
            ("độ thuần thục", "độ thành thạo"),
            ("tân thủ chỉ dẫn nhiệm vụ tặng", "quà tặng từ nhiệm vụ hướng dẫn tân thủ"),
            ("bảng nền trắng chữ đen", "bảng giao diện nền trắng chữ đen"),
            ("bảng trò chơi đồng dạng", "như giao diện trò chơi"),
            ("bảng trò chơi", "bảng giao diện trò chơi"),
            ("thông tin cá nhân bảng", "bảng thông tin cá nhân"),
            ("thương thành nhiệm vụ chờ công năng", "thương thành, nhiệm vụ và các tính năng"),
            ("một cái không rơi", "không thiếu thứ nào"),
            ("đều là làm tân thủ chỉ dẫn nhiệm vụ tặng", "đều là phần thưởng từ nhiệm vụ tân thủ"),
            ("tiểu đao đâm cái mông —— mở rộng tầm mắt!", "đúng là mở rộng tầm mắt!"),
            ("tiểu đao đâm cái mông —— mở rộng tầm mắt", "đúng là mở rộng tầm mắt"),
            ("tiểu đao đâm cái mông", "đúng là mở rộng tầm mắt"),
            ("tùy thời ở giữa", "theo thời gian"),
            ("tu tiên đạo đồ", "con đường tu tiên"),
            ("đạo đồ", "con đường tu luyện"),
            ("chuỗi thức ăn bên trên địa vị", "vị trí trên chuỗi thức ăn"),
            ("chuỗi thức ăn bên trên", "trên chuỗi thức ăn"),
            ("đập vào trò chơi", "chơi game"),
            ("uống vào đồ uống", "uống nước ngọt"),
            ("nhưng so sánh hiện tại thoải mái nhiều", "so với bây giờ thoải mái hơn nhiều"),
            ("loại này tiểu bất điểm dáng vẻ", "bộ dạng tiểu bất điểm này"),
            ("mượn cái này nước mưa", "dùng chỗ nước mưa này"),
            ("đem gác ở trên đống lửa dâng lên lửa", "đem gác lên đống lửa, châm lửa nướng"),
            ("đến tranh thủ thời gian", "phải tranh thủ thời gian"),
            ("sớm làm rời đi thì tốt hơn", "sớm rời khỏi đây thì tốt hơn"),
            ("tốt nhất là tìm nơi có người", "tốt nhất là tìm nơi có người ở"),
            ("lưu lại một cái như bàn chân tiểu bồn địa", "để lại một vùng trũng nhỏ tựa vết chân"),
            ("không khỏi run run người", "không khỏi rùng mình"),
            ("kinh hãi ngẩng đầu", "kinh hãi ngẩng đầu lên"),
            ("theo bản năng đem", "theo bản năng mang"),
            ("chín thịt báo", "thịt báo vừa chín"),
            ("không sai biệt lắm chín thịt báo", "thịt báo vừa chín tới"),
            ("thịt báo thu vào ba lô", "thịt báo cất vào ba lô"),
            ("trong nháy mắt liền ẩn núp bên trên đỉnh đầu nồng đậm tán cây bên trong", "trong nháy mắt liền ẩn nấp vào tán cây rậm rạp trên đỉnh đầu"),
            ("vụng trộm lộ ra", "lén lút để lộ"),
            ("một đôi mắt đen chuyển động", "đôi mắt đen đảo quanh"),
            ("quan sát bốn phía tình huống", "quan sát tình hình bốn phía"),
            ("Xảy ra chuyện gì", "Có chuyện gì xảy ra?"),
            ("mãnh chim", "chim dữ"),
            ("ngút trời đào tẩu", "bay vút lên trời trốn chạy"),
            ("Đến đi qua nhìn một chút", "Phải qua đó xem thử mới được"),
            ("quyết định hướng tiếng rống phương hướng đi qua nhìn một chút", "quyết định đi về hướng tiếng gầm xem thử"),
            ("Tục ngữ nói tốt", "Tục ngữ có câu"),
            ("cầu phú quý trong nguy hiểm", "giàu sang trong nguy hiểm"),
            ("Dù nhưng", "Mặc dù"),
            ("dù nhưng", "mặc dù"),
            ("đại khái dẫn đầu là", "khả năng cao là"),
            ("đại khái dẫn đầu", "rất có khả năng"),
            ("một loại nào đó hung tàn hung thú", "loài hung thú tàn bạo nào đó"),
            ("mười phần nguy hiểm", "vô cùng nguy hiểm"),
            ("Nhưng, đổi cái góc độ đến xem", "Thế nhưng, nhìn từ một góc độ khác"),
            ("đổi cái góc độ đến xem", "nhìn từ góc độ khác"),
            ("kinh thiên nộ hống đây này?", "tiếng gầm kinh thiên động địa thế này?"),
            ("Khả năng này không nhỏ", "Khả năng này rất lớn"),
            ("học xong một chút", "đã học được vài phần"),
            ("dã thú bản năng", "bản năng loài dã thú"),
            ("Cũng tỷ như", "Chẳng hạn như"),
            ("không còn sống lâu nữa cảm giác", "cảm giác như sắp gần đất xa trời"),
            ("không còn sống lâu nữa", "không còn sống được bao lâu"),
            ("đáng giá Bạch Nhất Tâm mạo hiểm đi xem một chút", "đáng để Bạch Nhất Tâm mạo hiểm qua xem thử"),
            ("loại nguy cơ này cảm", "cảm giác nguy cơ này"),
            ("càng diễn càng mạnh", "ngày càng dữ dội"),
            ("đừng nói là ai loại cấm địa loại hình địa phương", "đừng bảo đây là cấm địa nhân loại đấy nhé"),
            ("Thần Ma cấm địa hay sao?", "Thần Ma cấm địa hay sao?"),
            ("suy nghĩ tỉ mỉ đi xuống", "nghĩ ngợi thêm nữa"),
            ("trước đi qua nhìn một chút tình huống đi", "cứ qua đó xem tình hình thế nào trước đã"),
            ("Nếu là đoán sai, cũng không sao", "Nếu đoán sai cũng chẳng sao"),
            ("an toàn của mình vẫn là có bảo hộ", "sự an toàn của mình vẫn được bảo đảm"),
            ("nhìn thoáng qua chính mình trong ba lô đống kia lung tung vật phẩm bên trong", "liếc nhìn đống đồ vật linh tinh trong ba lô của mình, thấy"),
            ("thân theo phong động, nâng thân đạp lá", "thân theo gió động, nhẹ lướt trên cành lá"),
            ("thuận âm thanh rống chỗ mà đi", "men theo tiếng gầm mà tiến tới"),
            ("liên miên không dứt", "trùng điệp không dứt"),
            ("đếm không hết cổ mộc chọc vào vòm trời", "vô số cổ thụ chọc thẳng vòm trời"),
            ("thổi lên lá khí", "cuốn theo làn gió mát"),
            ("sàn sạt ở giữa", "trong tiếng lá xào xạc"),
            ("một thân ảnh lặng yên không một tiếng động", "một bóng người thoăn thoắt không một tiếng động"),
            ("Tại cành lá ở giữa xẹt qua", "lướt qua giữa các cành lá"),
            ("để người cảm thấy mười phần kiềm chế", "khiến người ta cảm thấy vô cùng ngột ngạt"),
            ("yên tĩnh im ắng", "tĩnh lặng như tờ"),
            ("như là một mảnh tử địa", "tựa như một mảnh tử địa"),
            ("hiện lộ rõ ràng khác biệt", "lộ rõ vẻ khác thường"),
            ("không có một cái thú chạy gào thét", "không một tiếng gầm gừ của thú dữ"),
            ("không rét mà run", "khiến người không rét mà run"),
            ("không làm sự việc dư thừa", "không làm chuyện thừa thãi"),
            ("tất cả lấy tính mệnh ưu tiên", "tất cả đều lấy an toàn tính mạng làm đầu"),
            ("Tránh lui vài dặm", "Lùi xa vài dặm"),
            ("lặng lẽ leo lên", "lặng lẽ trèo lên"),
            ("xa xa nhìn ra xa", "từ xa nhìn về"),
            ("mật thiết chú ý nơi đó tình huống", "chăm chú quan sát tình hình nơi đó"),
            ("hi vọng có thể nhìn thấy bóng người", "hy vọng tìm thấy bóng người"),
            ("Một thời ba khắc", "Chỉ một lát sau"),
            ("có một đám người từ đằng xa toát ra", "bỗng có một toán người từ xa xuất hiện"),
            ("vội vã hướng cái kia phiến núi rừng xông vào", "vội vã xông vào cánh rừng núi kia"),
            ("Có người tồn tại liền tốt", "Có người ở đây là tốt rồi"),
            ("híp híp mắt", "nheo mắt lại"),
            ("thở dài một hơi", "thở phào nhẹ nhõm"),
            ("nghĩ kỹ làm sao cùng bọn hắn tiếp xúc đổi lấy thông tin", "nghĩ ra cách tiếp xúc để dò hỏi tin tức"),
            ("cũng giống là cảm nhận được cái gì", "dường như cũng cảm nhận được điều gì"),
            ("nhóm người này có ít đồ", "nhóm người này quả có chút bản lĩnh"),
            ("có ít đồ", "có chút bản lĩnh"),
            ("miễn phải tự mình đi cái kia phiến địa phương nguy hiểm nhắc nhở", "đỡ phải tự mình đến nơi nguy hiểm kia nhắc nhở"),
            ("Bóng người một chút", "Bóng người thoắt ẩn thoắt hiện"),
            ("tiếng hò hét âm vang lên", "tiếng hò hét ầm ĩ vang lên"),
            ("bay thẳng toà kia sụp đổ núi đá", "lao thẳng về phía ngọn núi đá sụp đổ kia"),
            ("tích cực như vậy đi tìm chết?", "nhiệt tình đi tìm chết như thế?"),
            ("thứ nhất băng người tới tới gần", "tiếp cận nhóm người đầu tiên"),
            ("thứ nhất băng người", "nhóm người đầu tiên"),
            ("thứ một nhóm người", "nhóm người đầu tiên"),
            ("băng người", "toán người"),
            ("Không có tính toán đi nhắc nhở", "Không có ý định đi nhắc nhở"),
            ("chuyến này đến chỉ vì cầu người hỏi", "chuyến này tới chỉ để dò hỏi tin tức"),
            ("ngu xuẩn thường thường chết nhanh nhất", "kẻ ngu xuẩn thường là kẻ chết sớm nhất"),
            ("ba phe nhân mã", "ba toán nhân mã"),
            ("thấu tai giết tiếng quát", "tiếng thét chém giết chói tai"),
            ("vài đầu hung cầm bay tới", "mấy con hung cầm sà tới"),
            ("tại chỗ liền đem sáu, bảy người cho xé rách", "ngay tại chỗ đã xé nát sáu, bảy người"),
            ("Khá lắm", "Khá khen thay"),
            ("Cái này lấy máu tanh tràng cảnh", "Cảnh tượng đẫm máu này"),
            ("toàn bộ sơn mạch đều sôi trào", "cả dãy núi đều sôi trào"),
            ("Đàn thú bạo động", "Đàn thú nổi cơn điên cuồng"),
            ("như là một cỗ hồng triều vọt tới", "tựa như một cơn hồng thủy cuồn cuộn ập đến"),
            ("giống như điên hướng phía", "như điên như dại hướng về"),
            ("loại này trận thế", "thế trận bực này"),
            ("không miễn kinh hãi không thôi", "không khỏi kinh hãi tột cùng"),
            ("Đến đều đến, luôn không khả năng một chuyến tay không đi", "Đã tới tận đây rồi, sao có thể ra về tay trắng"),
            ("nói không chừng sẽ bị lan đến gần", "nói không chừng sẽ bị vạ lây"),
            ("Thứ một nhóm người bên trong", "Trong nhóm người đầu tiên"),
            ("thực hiện viện thủ", "ra tay tương trợ"),
            ("Một cái lão giả từ đám người đi tới", "Một lão giả từ trong đám người bước ra"),
            ("trên mặt nụ cười", "nụ cười trên môi"),
            ("hướng về phía Bạch Nhất Tâm cái này đột nhiên xuất hiện tiểu hài tử nói", "nói với đứa bé Bạch Nhất Tâm vừa đột ngột xuất hiện:"),
            ("làm Thạch thôn địa phương", "nơi có tên là Thạch thôn"),
            ("không sai biệt lắm sinh vật", "sinh vật có hình dáng giống ta"),
            ("giết hết Cự Bưu", "sau khi tiêu diệt Cự Bưu"),
            ("ngơ ngác sững sờ", "ngơ ngác ngẩn ngơ"),
            ("kỳ quái lời nói", "những lời kỳ lạ"),
            ("ngươi bao lớn rồi?", "cháu bao nhiêu tuổi rồi?"),
            ("thường thức tính đồ vật", "kiến thức thường thức"),
            ("gọn gàng mà linh hoạt", "gọn gàng dứt khoát"),
            ("kỳ quái oa tử", "đứa bé kỳ lạ"),
            ("chẳng biết xấu hổ xem nhẹ", "mặt dày phớt lờ"),
            ("phía sau 22", "đằng sau số 22"),
            ("ấn vò hai bên huyệt thái dương", "day day hai bên huyệt thái dương"),
            ("đặc biệt dùng tay che kín ánh mắt của mình", "cố ý lấy tay che mắt mình lại"),
            ("Sinh ra đã biết", "Sinh ra đã biết tất cả"),
            ("như cái trắng búp bê", "tựa như búp bê sứ trắng trẻo"),
            ("cứu mình tộc nhân soái khí tiểu ca ca", "vị tiểu ca ca khôi ngô đã cứu tộc nhân mình"),
            ("nhấc lên một vòng dáng tươi cười", "nở một nụ cười"),
            ("khập khiễng đáp lại nói", "lắp bắp đáp lời:"),
            ("khập khiễng nói", "lắp bắp nói"),
            ("khập khiễng đáp", "lắp bắp đáp"),
            ("Không có nghĩ tới đây vậy mà", "Không ngờ nơi này vậy mà"),
            ("xác định vững chắc xuống tới", "thật sự xác nhận rõ ràng"),
            ("liếc xéo", "đưa mắt liếc nhìn"),
            ("băng lãnh mà bức nhân", "lạnh lẽo bức người"),
            ("cúi nhìn phía dưới", "nhìn xuống bên dưới"),
            ("Thanh đại thẩm, là cùng chúng ta cùng một chỗ", "Thanh đại thẩm đi cùng bọn đệ"),
            ("thời gian không kịp", "không kịp nữa rồi"),
            ("làm lòng người run", "khiến lòng người run rẩy"),
            ("Sưu một tiếng vọt lên", "Vút một tiếng nhảy vọt lên"),
            ("rơi vào rộng lớn lưng chim ưng bên trên", "đáp xuống tấm lưng rộng lớn của chim ưng"),
            ("không sai biệt lắm chín", "vừa chín tới"),
            ("không sai biệt lắm", "gần như"),
            ("chạy theo như vịt", "đổ xô tranh giành"),
            ("đinh lên", "dán chặt mắt vào"),
            ("hỏi đồ vật", "dò hỏi tin tức"),
            ("phụ một tay", "giúp một tay"),
            ("lan đến gần", "vạ lây"),
            ("loại sự tình này", "chuyện này"),
            ("loại sự tình", "chuyện loại này"),
            ("cái này loại", "loại này"),
            ("cái kia loại", "loại kia"),
            ("dáng dấp cùng ta không sai biệt lắm", "dáng vẻ giống như ta"),
            ("người loại này thường thức tính đồ vật", "kiến thức thường thức về loài người"),
            ("soái khí", "khôi ngô"),
            ("chẳng biết xấu hổ", "mặt dày"),
            ("xem nhẹ 6 phía sau 22", "phớt lờ con số 22 đằng sau số 6"),
            ("lập loè hàn quang lớp vảy màu xanh diều hâu", "con ưng phủ vảy xanh lập lòe ánh kim"),
            ("lấy tinh kim rèn luyện mà thành", "được đúc rèn từ tinh kim"),
            ("thật xác định vững chắc xuống tới", "thật sự xác nhận điều đó"),
            ("Sưu một tiếng", "Vút một tiếng"),
            ("C!", "Chết tiệt!"),
            ("Đông!", "Bịch!"),
            ("liếm môi một cái", "khẽ liếm môi"),
            ("đến đều đến", "đã tới rồi thì"),
            ("Đến đều đến", "Đã tới rồi thì"),
            ("trở thành ta cơm trưa đi", "trở thành bữa trưa của ta đi"),
            ("ta cơm trưa", "bữa trưa của ta"),
            ("ô tô lớn nhỏ thân thể bên trong", "bên trong thân hình to như chiếc ô tô"),
            ("ô tô lớn nhỏ thân thể", "thân hình to như chiếc ô tô"),
            ("ba trượng lớn nhỏ", "rộng chừng ba trượng"),
            ("cả đám đều có phòng ốc lớn như vậy", "con nào con nấy to như gian nhà"),
            ("phòng ốc lớn như vậy", "to như một gian nhà"),
            ("một đóa nhỏ nhắn xinh xắn màu đen mây đen nhỏ", "một đám mây đen nhỏ nhắn"),
            ("thật là đúng là", "đúng là"),
            ("hai đầu lão hổ", "hai con hổ"),
            ("lão hổ", "hổ"),
            ("TiChính mình", "Chính mình"),

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

            # Lượng từ động vật & danh từ
            (re.compile(r'\b(\d+|vài|mấy|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm|ngàn|vạn)\s+đầu\s+(hung thú|mãnh thú|hung cầm|dị thú|yêu thú|ma thú|lão hổ|báo|sư tử|gấu|cẩu|ngưu|trâu|bò|hổ|báo đốm|chó|sói|diều hâu|thần thú|linh thú|quái vật|thú|chim|Độc Giác Báo|Thanh Lân Ưng)\b', re.IGNORECASE), r'\1 con \2'),
            (re.compile(r'\bmột đầu hung thú\b', re.IGNORECASE), 'một con hung thú'),
            (re.compile(r'\bmột đầu mãnh thú\b', re.IGNORECASE), 'một con mãnh thú'),
            (re.compile(r'\b(\d+|vài|mấy|một)\s+cái\s+oa tử\b', re.IGNORECASE), r'\1 đứa bé'),
            (re.compile(r'\b(\d+|vài|mấy|một)\s+cái\s+tiểu hài\b', re.IGNORECASE), r'\1 đứa bé'),
            (re.compile(r'\btiểu hài này\b', re.IGNORECASE), 'đứa bé này'),
            (re.compile(r'\bnhân loại kia tiểu hài\b', re.IGNORECASE), 'đứa bé loài người kia'),
            (re.compile(r'\bnhân loại tiểu hài\b', re.IGNORECASE), 'đứa bé loài người'),
            (re.compile(r'\bmột cái thông thiên trụ đen\b', re.IGNORECASE), 'một cây cột đen thông thiên'),
            (re.compile(r'\b(\d+|vài|mấy|một)\s+khỏa\s+(đan dược|linh đan|thần đan|tinh cầu|cổ thụ|đầu người)\b', re.IGNORECASE), r'\1 viên \2'),

            # Cấu trúc hành động nhìn / dán mắt (盯上 / 盯着)
            (re.compile(r'\b(ánh mắt[^\n,.:;!?]{0,25}?)\s+đinh lên\b', re.IGNORECASE), r'\1 dán chặt vào'),
            (re.compile(r'\b(ánh mắt[^\n,.:;!?]{0,25}?)\s+đinh lấy\b', re.IGNORECASE), r'\1 nhìn chằm chằm vào'),
            (re.compile(r'\bgắt gao\s+đinh lấy\b', re.IGNORECASE), 'nhìn chằm chằm không rời'),
            (re.compile(r'\bgắt gao\s+đinh lên\b', re.IGNORECASE), 'dán chặt mắt vào'),
            (re.compile(r'\bđinh lên\b', re.IGNORECASE), 'dán chặt vào'),
            (re.compile(r'\bđinh lấy\b', re.IGNORECASE), 'nhìn chằm chằm vào'),
            (re.compile(r'\bđinh ở\b', re.IGNORECASE), 'dán chặt vào'),

            # Cấu trúc đảo ngữ: trước mặt / trước mắt + Danh từ -> Danh từ + trước mắt (phong cách convert lộn xộn)
            (re.compile(r'\btrước mặt\s+(tiểu hài|hài tử|đứa bé|thiếu niên|thiếu nữ|thanh niên|lão giả|lão nhân|địch nhân|hung thú|mãnh thú|cự thú|quái vật|đối thủ|nam tử|nữ tử|đại hán|cường giả|vương giả|tôn giả|người|mấy người|đám người)\b', re.IGNORECASE), r'\1 trước mắt'),
            (re.compile(r'\btrước mắt\s+(tiểu hài|hài tử|đứa bé|thiếu niên|thiếu nữ|thanh niên|lão giả|lão nhân|địch nhân|hung thú|mãnh thú|cự thú|quái vật|đối thủ|nam tử|nữ tử|đại hán|cường giả|vương giả|tôn giả|người|mấy người|đám người|cây lớn|cổ thụ|núi đá|cảnh tượng|hình ảnh|hết thảy|tất cả|nguy cơ|khó khăn)\b', re.IGNORECASE), r'\1 trước mắt'),
            (re.compile(r'\btrước mắt\s+cái này\s+bảng\b', re.IGNORECASE), 'bảng giao diện trước mắt này'),
            (re.compile(r'\btrước mắt\s+tuổi\b', re.IGNORECASE), 'tuổi hiện tại'),
            (re.compile(r'\btrước mắt\s+tình huống\b', re.IGNORECASE), 'tình hình hiện tại'),
            (re.compile(r'\btrước mắt\s+trạng thái\b', re.IGNORECASE), 'trạng thái hiện tại'),

            # Cấu trúc đảo ngữ sở hữu: <Chủ thể> + vị trí + <Vật> -> <Vật> + vị trí + <Chủ thể>
            (re.compile(r'\b(tiểu hài này|đứa bé này|thiếu niên này|thiếu nữ này|hắn|nàng|y)\s+trong tay\s+(một thanh|thanh|chiếc|cây)\s+(đoản kiếm|trường kiếm|trường thương|đại đao|bảo kiếm|thần kiếm|vũ khí|bảo cụ)\b', re.IGNORECASE), r'\2 \3 trong tay \1'),
            (re.compile(r'\b(hắn|nàng|y|ngươi|ta)\s+trong tay\s+(trường kiếm|đoản kiếm|bảo kiếm|thần kiếm|vũ khí|bảo cụ|cốt thư|ngọc giản|pháp bảo)\b', re.IGNORECASE), r'\2 trong tay \1'),
            (re.compile(r'\b(hắn|nàng|y|ngươi|ta)\s+sau lưng\s+(hư ảnh|động thiên|thần hoàn|dị tượng|quang dực|đôi cánh|pháp tướng)\b', re.IGNORECASE), r'\2 sau lưng \1'),
            (re.compile(r'\b(hắn|nàng|y|ngươi|ta)\s+đỉnh đầu\s+(hư không|bảo tháp|thần hoàn|đại đỉnh|mây đen)\b', re.IGNORECASE), r'\2 trên đỉnh đầu \1'),
            (re.compile(r'\b(hắn|nàng|y|ngươi|ta)\s+dưới chân\s+(đại địa|mặt đất|núi đá|phi kiếm|trận pháp)\b', re.IGNORECASE), r'\2 dưới chân \1'),

            # Cấu trúc đảo ngữ vị trí + Danh từ -> Danh từ + vị trí
            (re.compile(r'\bđỉnh đầu\s+(?:nồng đậm\s+)?tán cây\b', re.IGNORECASE), 'tán cây rậm rạp trên đỉnh đầu'),
            (re.compile(r'\bđỉnh đầu\s+(mây đen|lôi vân|lôi điện|hư không|cự kiếm|bảo tháp|thần hoàn|đại đỉnh|nhật nguyệt|dị tượng|Thanh Lân Ưng|hung cầm|dị điểu)\b', re.IGNORECASE), r'\1 trên đỉnh đầu'),
            (re.compile(r'\b(?:sau lưng|phía sau)\s+(hư ảnh|động thiên|thần hoàn|dị tượng|quang dực|đôi cánh|cánh|cự thú|địch nhân|thiếu niên|pháp tướng|cự nhân|núi thịt)\b', re.IGNORECASE), r'\1 sau lưng'),
            (re.compile(r'\bbên người\s+(thiếu nữ|thiếu niên|thị nữ|người hầu|đồng bạn|tùy tùng|nữ tử|nam tử|linh thú|thần thú)\b', re.IGNORECASE), r'\1 bên cạnh'),
            (re.compile(r'\bdưới chân\s+(đại địa|mặt đất|núi đá|cự thạch|trận pháp|tế đàn|linh kiếm|phi kiếm|phi chu|vân vụ)\b', re.IGNORECASE), r'\1 dưới chân'),
            (re.compile(r'\btrong tay\s+(đoản kiếm|trường kiếm|trường thương|chiến mâu|đại đao|bảo kiếm|thần kiếm|vũ khí|bảo cụ|cốt thư|ngọc giản|pháp bảo|phù lục|trường cung|cốt mâu)\b', re.IGNORECASE), r'\1 trong tay'),

            # Cấu trúc đảo ngữ: <Nơi chốn> tình huống -> tình hình <Nơi chốn>
            (re.compile(r'\b(nơi đó|nơi đây|bên trong|bên ngoài|bốn phía|xung quanh|hai người|chiến trường|chiến đấu|trong núi)\s+tình huống\b', re.IGNORECASE), r'tình hình \1'),

            # Cấu trúc đảo ngữ: loại ... này cảm -> cảm giác ... này
            (re.compile(r'\bloại\s+([a-zA-ZÀ-ỹ\s]{2,20}?)\s+này cảm\b', re.IGNORECASE), r'cảm giác \1 này'),
            (re.compile(r'\bloại này\s+([a-zA-ZÀ-ỹ\s]{2,20}?)\s+cảm\b', re.IGNORECASE), r'cảm giác \1 này'),

            # Cấu trúc đòn đánh: cái này một kích/kiếm/quyền -> đòn kích này/kiếm này/quyền này
            (re.compile(r'\bcái này một kích\b', re.IGNORECASE), 'đòn kích này'),
            (re.compile(r'\bcái kia một kích\b', re.IGNORECASE), 'đòn kích kia'),
            (re.compile(r'\bcái này một kiếm\b', re.IGNORECASE), 'nhát kiếm này'),
            (re.compile(r'\bcái này một quyền\b', re.IGNORECASE), 'cú đấm này'),
            (re.compile(r'\bcái này một chưởng\b', re.IGNORECASE), 'chưởng này'),

            # Sở hữu cách đảo
            (re.compile(r'\bhắn trong tay\b', re.IGNORECASE), 'trong tay hắn'),
            (re.compile(r'\bhắn trong mắt\b', re.IGNORECASE), 'trong mắt hắn'),
            (re.compile(r'\bhắn bên tai\b', re.IGNORECASE), 'bên tai hắn'),
            (re.compile(r'\bhắn đỉnh đầu\b', re.IGNORECASE), 'trên đỉnh đầu hắn'),
            (re.compile(r'\bhắn trên thân\b', re.IGNORECASE), 'trên người hắn'),
            (re.compile(r'\bnó trên đầu\b', re.IGNORECASE), 'trên đầu nó'),
            (re.compile(r'\bnó sừng nhọn\b', re.IGNORECASE), 'chiếc sừng nhọn của nó'),
            (re.compile(r'\bchính mình trong ba lô\b', re.IGNORECASE), 'trong ba lô của mình'),
            (re.compile(r'\bchính mình trong đầu\b', re.IGNORECASE), 'trong đầu mình'),
            (re.compile(r'\ban toàn của mình\b', re.IGNORECASE), 'sự an toàn của bản thân'),

            # Cấu trúc thời gian / ngữ pháp
            (re.compile(r'\bkhi\s+tiến vào\s+đến\s+([^,.\n!?:;]{2,40}?)\s+thời điểm\b', re.IGNORECASE), r'khi tiến vào \1'),
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,40}?)\s+thời điểm\b', re.IGNORECASE), r'vào thời điểm \1'),
            (re.compile(r'\bhướng phía\s+([^,.\n!?:;]{2,30}?)\s+hư trảm một kiếm\b', re.IGNORECASE), r'vung kiếm vào hư không về phía \1'),
            (re.compile(r'\btại\s+([^,.\n!?:;]{2,30}?)\s+ngo ngoe muốn động\b', re.IGNORECASE), r'đang rục rịch chuyển động trong \1'),
            (re.compile(r'\bngo ngoe muốn động\b', re.IGNORECASE), 'rục rịch ngóc đầu dậy'),
            (re.compile(r'\bsáng ngời có thần đôi mắt\b', re.IGNORECASE), 'đôi mắt sáng ngời có thần'),
            (re.compile(r'\bcách hắn chỉ có xa\s+([^,.\n!?:;]{2,20}?)\s+một con\b', re.IGNORECASE), r'cách hắn chỉ \1 là một con'),
            (re.compile(r'\bcòn tại tuôn máu vết máu\b', re.IGNORECASE), 'vết thương vẫn còn đang rỉ máu'),
            (re.compile(r'\bdiện mạo không kinh người nó vậy mà\b', re.IGNORECASE), 'trông vẻ ngoài không có gì nổi bật nhưng lại'),
            (re.compile(r'\bnghe được vang lên bên tai âm thanh\b', re.IGNORECASE), 'nghe thấy âm thanh vang lên bên tai'),
            (re.compile(r'\bhơi nhếch khóe môi lên lên\b', re.IGNORECASE), 'khóe môi khẽ nhếch lên'),
            (re.compile(r'\bkhóe miệng nhấc lên một vòng dáng tươi cười\b', re.IGNORECASE), 'khóe miệng nở một nụ cười'),
            (re.compile(r'\bsờ sờ\s+([^,.\n!?:;]{2,30}?)\s+đầu\b', re.IGNORECASE), r'xoa đầu \1'),
            (re.compile(r'\bnhéo nhéo\s+([^,.\n!?:;]{2,30}?)\s+khuôn mặt nhỏ nhắn\b', re.IGNORECASE), r'véo khuôn mặt nhỏ nhắn của \1'),
            (re.compile(r'\btrắng nõn khuôn mặt nhỏ nhắn\b', re.IGNORECASE), 'khuôn mặt nhỏ nhắn trắng nõn'),
            (re.compile(r'\bbộ kia dáng tươi cười\b', re.IGNORECASE), 'nụ cười kia'),
        ]

    def _init_dict_engine(self):
        """Khởi tạo từ điển thuật ngữ chuyển đổi Convert sang Dịch mượt mà (offline 100%)"""
        dict_file = os.path.join(BASE_DIR, "convert_dict.json")
        ext_dict = {}
        if os.path.exists(dict_file):
            try:
                import json
                with open(dict_file, "r", encoding="utf-8") as f:
                    ext_dict = json.load(f)
            except Exception as e:
                print(f"Lỗi nạp convert_dict.json: {e}")

        all_terms = dict(self.phrase_mappings)
        for k, v in ext_dict.items():
            all_terms[k] = v

        sorted_keys = sorted(all_terms.keys(), key=len, reverse=True)
        self._dict_map = {k: all_terms[k] for k in sorted_keys}
        self._dict_lower_map = {k.lower(): v for k, v in all_terms.items()}

        def make_safe_pattern(k):
            prefix = r"(?<!\w)" if k[0].isalnum() else ""
            suffix = r"(?!\w)" if k[-1].isalnum() else ""
            return f"{prefix}{re.escape(k)}{suffix}"

        pattern_str = "|".join(make_safe_pattern(k) for k in sorted_keys)
        self._master_dict_regex = re.compile(pattern_str, re.IGNORECASE)

    def _dict_replacer(self, m):
        val = m.group(0)
        return self._dict_map.get(val, self._dict_lower_map.get(val.lower(), val))

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

        # Áp dụng từ điển cụm từ convert -> dịch & thuật ngữ truyện dịch chuẩn (100% offline)
        if hasattr(self, '_master_dict_regex') and self._master_dict_regex:
            result = self._master_dict_regex.sub(self._dict_replacer, result)
        else:
            for src, tgt in self.phrase_mappings:
                pattern = re.compile(re.escape(src), re.IGNORECASE)
                result = pattern.sub(tgt, result)

        # Xóa dấu hai chấm bị lặp lại (ví dụ : : hoặc : : )
        result = re.sub(r':\s*:', ':', result)
        result = re.sub(r':\s*,', ':', result)
        result = re.sub(r',\s*:', ':', result)

        # Chuẩn hóa dấu ba chấm dính hoặc cách xa (. . .)
        result = re.sub(r'(?:\.[ \t]*){2,}\.?', '...', result)
        result = re.sub(r'\.\.\.([a-zA-ZÀ-ỹ])', r'... \1', result)
        result = re.sub(r'([!?,;])\s*\1+', r'\1', result)
        result = re.sub(r':\s*\.', ':', result)
        result = re.sub(r',\s*\.', '.', result)

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
        dict_entries: Optional[Dict[str, str]] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """Xử lý bằng AI LLM (DeepSeek / Gemini / Custom Model) với prompt văn học chuyên sâu"""
        system_prompt = (custom_prompt and custom_prompt.strip()) or CONVERT_PROMPTS.get(genre, CONVERT_PROMPTS["xianxia"])
        
        # Thêm từ điển tùy chọn nếu có
        dict_hint = ""
        if dict_entries:
            items = list(dict_entries.items())[:50]
            lines = ["\nDANH TỪ / TÊN RIÊNG BẮT BUỘC GIỮ CHUẨN XÁC:"]
            for s, t in items:
                lines.append(f"- {s} => {t}")
            dict_hint = "\n".join(lines) + "\n"

        full_prompt = f"{system_prompt}\n{dict_hint}\nĐoạn văn bản Convert cần chuyển sang truyện dịch:\n\n{text}"

        # 1. Kiểm tra xem engine có khớp với Custom AI Model nào không (Muse Spark, DeepSeek R1, GPT-4o, v.v.)
        custom_cfg = None
        custom_list = self.llm.get_custom_models(mask_keys=False)
        for cm in custom_list:
            if cm.get("id") == engine or cm.get("name") == engine or cm.get("model") == engine or cm.get("name") in engine or cm.get("model") in engine:
                custom_cfg = cm
                break

        # Nếu chọn "active" hoặc chưa chọn model cụ thể, thử lấy active model ID
        if not custom_cfg and (engine in ("active", "custom", "custom_ai", "") or "(custom ai)" in engine.lower()):
            active_id = self.llm.config.get("active_model_id")
            for cm in custom_list:
                if cm.get("id") == active_id:
                    custom_cfg = cm
                    break

        if custom_cfg:
            # Chạy qua Universal OpenAI-compatible client của LLMTranslator với Prompt Convert chuyên dụng
            model_copy = dict(custom_cfg)
            if api_key:
                model_copy["api_key"] = api_key
            return self.llm.translate_openai_compatible(
                model_cfg=model_copy,
                text=text,
                dict_entries=dict_entries,
                system_prompt=system_prompt,
                user_prompt_prefix="Chuyển thể và gọt giũa đoạn văn bản convert sau thành truyện dịch văn học hoàn chỉnh:\n\n"
            )

        if "gemini" in engine.lower():
            key = api_key or os.environ.get("GEMINI_API_KEY", "").strip() or self.llm.config.get("gemini_api_key", "").strip()
            if not key:
                raise ValueError("Chưa thiết lập Gemini API Key. Vui lòng cấu hình trong Cài Đặt.")
            import requests
            model = "gemini-2.0-flash" if "2.0" in engine else "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"temperature": 0.35, "maxOutputTokens": 8192}
            }
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(f"Lỗi Gemini API ({resp.status_code}): {resp.text}")
            data = resp.json()
            try:
                candidate = data["candidates"][0]
                text_out = candidate["content"]["parts"][0]["text"].strip()
                return text_out
            except Exception as e:
                raise RuntimeError(f"Lỗi đọc kết quả Gemini: {data}")

        elif "deepseek" in engine.lower():
            key = api_key or os.environ.get("DEEPSEEK_API_KEY", "").strip() or self.llm.config.get("deepseek_api_key", "").strip()
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
                "temperature": 0.35,
                "stream": False
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code != 200:
                raise RuntimeError(f"Lỗi DeepSeek API ({resp.status_code}): {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        else:
            raise ValueError(f"Không hỗ trợ AI Engine '{engine}'. Vui lòng cấu hình model trong Cài Đặt.")

    def polish_hybrid(
        self,
        text: str,
        engine: str = "gemini",
        genre: str = "xianxia",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Chế độ Hybrid Thông Minh (Smart Selective Routing):
        1. Bước 1: Dùng Rules Engine tiền xử lý và khử 85% lỗi ngữ pháp convert thô.
        2. Bước 2: Tự động trích xuất các bảng thuộc tính game/chỉ số (【...】) để khóa offline, không tốn token AI.
        3. Bước 3: Đưa văn bản tự sự và đối thoại vào AI LLM (Gemini/DeepSeek) để trau chuốt cảm xúc, văn phong.
        4. Bước 4: Khôi phục các bảng thuộc tính và chuẩn hóa dấu câu lần cuối.
        Nếu API AI gặp sự cố hoặc chưa có key, tự động fallback về bản Rules sạch đẹp 100%.
        """
        if not text:
            return ""

        # 1. Tiền xử lý sạch bằng Rules Engine
        cleaned_text = self.rules_engine.polish(text)

        # 2. Khóa bảng chỉ số game / thông báo thuộc tính
        panel_pattern = re.compile(r'((?:^\s*[【\[][^】\]\n]+[】\]][^\n]*\n?)+)', re.MULTILINE)
        panels = []

        def panel_repl(m):
            idx = len(panels)
            panels.append(m.group(1).strip())
            return f"\n\n<<<SYSTEM_PANEL_{idx}>>>\n\n"

        masked_text = panel_pattern.sub(panel_repl, cleaned_text)

        # 3. Gửi cho AI trau chuốt (với chỉ thị bảo toàn các thẻ <<<SYSTEM_PANEL_X>>>)
        try:
            ai_polished = self.polish_ai(
                text=masked_text,
                engine=engine,
                genre=genre,
                api_key=api_key,
                dict_entries=dict_entries,
                custom_prompt=custom_prompt
            )
            # 4. Khôi phục lại các bảng chỉ số
            for idx, panel in enumerate(panels):
                ai_polished = ai_polished.replace(f"<<<SYSTEM_PANEL_{idx}>>>", panel)
            return self.rules_engine._capitalize_sentences(ai_polished)
        except Exception as e:
            print(f"⚠️ Hybrid AI ({engine}): {e}. Chuyển sang dự phòng Offline chất lượng cao.")
            return cleaned_text

    def polish(
        self,
        text: str,
        mode: str = "rules",
        engine: str = "deepseek",
        genre: str = "xianxia",
        api_key: Optional[str] = None,
        dict_entries: Optional[Dict[str, str]] = None,
        custom_prompt: Optional[str] = None
    ) -> str:
        """Hàm điều hướng tổng quát: rules, ai hoặc hybrid"""
        if mode == "rules":
            return self.polish_rules(text)
        elif mode == "ai":
            return self.polish_ai(text, engine=engine, genre=genre, api_key=api_key, dict_entries=dict_entries, custom_prompt=custom_prompt)
        elif mode == "hybrid":
            return self.polish_hybrid(text, engine=engine, genre=genre, api_key=api_key, dict_entries=dict_entries, custom_prompt=custom_prompt)
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
        custom_prompt: Optional[str] = None,
        resume: bool = True,
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

            base, ext = os.path.splitext(fname)
            out_path = os.path.join(output_folder, f"{base}{suffix}{ext}")

            # Smart Resume: Nếu file đích đã tồn tại và có dung lượng > 10 bytes, bỏ qua và chuyển tiếp chương tiếp theo
            if resume and os.path.exists(out_path) and os.path.getsize(out_path) > 10:
                if status_callback:
                    status_callback(f"⏩ Đã có bản dịch, bỏ qua: {fname}", round((i / total) * 100, 1), fname, i, total)
                continue

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
                    genre=genre,
                    custom_prompt=custom_prompt
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
