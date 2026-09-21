package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Cấu trúc request OpenAI-compatible cho Muse Spark API
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []ChatMessage `json:"messages"`
	Temperature float64       `json:"temperature"`
}

type ChatChoice struct {
	Index   int         `json:"index"`
	Message ChatMessage `json:"message"`
}

type ChatCompletionResponse struct {
	ID      string       `json:"id"`
	Choices []ChatChoice `json:"choices"`
	Error   *struct {
		Message string `json:"message"`
		Type    string `json:"type"`
		Code    any    `json:"code"`
	} `json:"error,omitempty"`
}

// Cấu trúc lưu trữ thuật ngữ
type TermItem struct {
	Original   string // Thuật ngữ gốc / convert
	Translated string // Bản dịch chuẩn mượt
	Category   string // Nhân vật, Môn phái, Cảnh giới, Công pháp, Từ lóng...
	Note       string // Ghi chú thêm
}

// Quản lý từ điển luồng an toàn (thread-safe)
type GlossaryCollector struct {
	mu    sync.Mutex
	terms map[string]TermItem
}

func NewGlossaryCollector() *GlossaryCollector {
	return &GlossaryCollector{
		terms: make(map[string]TermItem),
	}
}

func (gc *GlossaryCollector) Add(original, translated, category, note string) {
	original = strings.TrimSpace(original)
	translated = strings.TrimSpace(translated)
	category = strings.TrimSpace(category)
	note = strings.TrimSpace(note)

	if original == "" || translated == "" {
		return
	}

	gc.mu.Lock()
	defer gc.mu.Unlock()

	// Nếu đã có nhưng bản mới có thể loại rõ hơn thì cập nhật
	existing, found := gc.terms[strings.ToLower(original)]
	if !found || (existing.Category == "" || existing.Category == "Khác") {
		gc.terms[strings.ToLower(original)] = TermItem{
			Original:   original,
			Translated: translated,
			Category:   category,
			Note:       note,
		}
	}
}

func (gc *GlossaryCollector) GetAll() []TermItem {
	gc.mu.Lock()
	defer gc.mu.Unlock()

	list := make([]TermItem, 0, len(gc.terms))
	for _, item := range gc.terms {
		list = append(list, item)
	}

	// Sắp xếp theo thể loại rồi đến bảng chữ cái
	sort.Slice(list, func(i, j int) bool {
		if list[i].Category != list[j].Category {
			return list[i].Category < list[j].Category
		}
		return list[i].Original < list[j].Original
	})

	return list
}

// Sắp xếp tự nhiên tên file (0001, 0002, ..., 0010 thay vì 0001, 0010)
func naturalSort(files []string) {
	re := regexp.MustCompile(`(\d+)`)
	sort.Slice(files, func(i, j int) bool {
		partsI := re.Split(files[i], -1)
		partsJ := re.Split(files[j], -1)
		numsI := re.FindAllString(files[i], -1)
		numsJ := re.FindAllString(files[j], -1)

		minLen := len(partsI)
		if len(partsJ) < minLen {
			minLen = len(partsJ)
		}

		for k := 0; k < minLen; k++ {
			if partsI[k] != partsJ[k] {
				return partsI[k] < partsJ[k]
			}
			if k < len(numsI) && k < len(numsJ) {
				nI, _ := strconv.Atoi(numsI[k])
				nJ, _ := strconv.Atoi(numsJ[k])
				if nI != nJ {
					return nI < nJ
				}
			}
		}
		return files[i] < files[j]
	})
}

// Đọc file với bộ mã UTF-8
func readFile(path string) (string, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(bytes), nil
}

// Gọi API Muse Spark
func callMuseSpark(baseURL, apiKey, model, content string) (string, error) {
	systemPrompt := `Bạn là chuyên gia dịch thuật và phân tích thuật ngữ tiểu thuyết mạng Trung Quốc (Tiên Hiệp, Huyền Huyễn, Võng Du, Try Hard).
NHIỆM VỤ: Quét toàn bộ đoạn văn bản truyện convert/dịch bên dưới và TRÍCH XUẤT TOÀN BỘ CÁC THUẬT NGỮ ĐẶC THÙ, TÊN RIÊNG, TỪ LÓNG GAME và BẢN DỊCH CHUẨN XÁC, MƯỢT MÀ.

CÁC NHÓM CẦN TRÍCH XUẤT:
1. Tên nhân vật (nhân vật chính, phụ, phản diện, thú cưng, người thân).
2. Địa danh, môn phái, thị tộc, thế lực, cấm địa.
3. Cảnh giới tu luyện (Bàn Huyết, Luyện Khí, Trúc Cơ, Kim Đan, Chí Tôn...).
4. Công pháp, bí tịch, kỹ năng, chiêu thức, bảo thuật (Nguyên Thủy Chân Giải, Tật Phong Kiếm Pháp...).
5. Pháp bảo, bảo cụ, linh đan, dị thú, hung thú, hung cầm (Toan Nghê, Thanh Lân Ưng, Chu Yếm...).
6. Thuật ngữ game, cày cuốc, từ lóng mạng (VD: lá gan đế => trùm cày cuốc; nổ lá gan => bạo gan cày cuốc; đại khái dẫn đầu => khả năng cao; có ít đồ => có chút bản lĩnh...).

ĐỊNH DẠNG TRẢ VỀ BẮT BUỘC:
Mỗi thuật ngữ ghi trên 1 dòng theo cú pháp chuẩn xác sau:
[Thuật ngữ gốc/Convert] => [Bản dịch chuẩn mượt] | [Thể loại] | [Ghi chú ngắn]

Ví dụ:
Bạch Nhất Tâm => Bạch Nhất Tâm | Nhân vật | Nhân vật chính
Thạch Hạo => Thạch Hạo | Nhân vật | Tiểu bất điểm
Thạch thôn => Thạch thôn | Địa danh | Ngôi làng cổ tích
lá gan đế => trùm cày cuốc | Từ lóng/Game | Kẻ try hard cày cuốc điên cuồng
nổ lá gan => bạo gan cày cuốc | Từ lóng/Game | Dốc toàn lực cày game
Độc Giác Báo => Độc Giác Báo | Dị thú | Hung thú báo một sừng
Cuồng Phong Tuyệt Tức Trảm => Cuồng Phong Tuyệt Tức Trảm | Kỹ năng | Chiêu thức gió

CHỈ TRẢ VỀ DANH SÁCH THUẬT NGỮ THEO ĐỊNH DẠNG TRÊN, KHÔNG KÈM LỜI DẪN HAY GIẢI THÍCH DÀI DÒNG.`

	url := strings.TrimRight(baseURL, "/") + "/chat/completions"

	reqBody := ChatCompletionRequest{
		Model: model,
		Messages: []ChatMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: fmt.Sprintf("Văn bản truyện cần bóc tách thuật ngữ:\n\n%s", content)},
		},
		Temperature: 0.2,
	}

	jsonBytes, err := json.Marshal(reqBody)
	if err != nil {
		return "", err
	}

	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonBytes))
		if err != nil {
			return "", err
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+apiKey)

		client := &http.Client{Timeout: 90 * time.Second}
		resp, err := client.Do(req)
		if err != nil {
			lastErr = err
			time.Sleep(time.Duration(attempt*2) * time.Second)
			continue
		}

		bodyBytes, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			lastErr = err
			continue
		}

		if resp.StatusCode == 429 {
			// Rate limit: Chờ rồi thử lại
			time.Sleep(time.Duration(attempt*5) * time.Second)
			continue
		}

		if resp.StatusCode != http.StatusOK {
			lastErr = fmt.Errorf("API error (status %d): %s", resp.StatusCode, string(bodyBytes))
			time.Sleep(time.Duration(attempt*2) * time.Second)
			continue
		}

		var chatResp ChatCompletionResponse
		if err := json.Unmarshal(bodyBytes, &chatResp); err != nil {
			return "", err
		}

		if chatResp.Error != nil {
			return "", fmt.Errorf("API error: %s", chatResp.Error.Message)
		}

		if len(chatResp.Choices) > 0 {
			return chatResp.Choices[0].Message.Content, nil
		}

		return "", fmt.Errorf("không có phản hồi từ mô hình")
	}

	return "", lastErr
}

// Phân tích dòng trả về từ model và nạp vào collector
func parseAndCollect(output string, collector *GlossaryCollector) {
	scanner := bufio.NewScanner(strings.NewReader(output))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "```") {
			continue
		}

		// Định dạng: A => B | C | D
		var orig, trans, cat, note string

		if strings.Contains(line, "=>") {
			parts := strings.SplitN(line, "=>", 2)
			orig = strings.TrimSpace(parts[0])
			rest := parts[1]

			subParts := strings.Split(rest, "|")
			if len(subParts) >= 1 {
				trans = strings.TrimSpace(subParts[0])
			}
			if len(subParts) >= 2 {
				cat = strings.TrimSpace(subParts[1])
			}
			if len(subParts) >= 3 {
				note = strings.TrimSpace(subParts[2])
			}
		} else if strings.Contains(line, "->") {
			parts := strings.SplitN(line, "->", 2)
			orig = strings.TrimSpace(parts[0])
			rest := parts[1]
			subParts := strings.Split(rest, "|")
			if len(subParts) >= 1 {
				trans = strings.TrimSpace(subParts[0])
			}
			if len(subParts) >= 2 {
				cat = strings.TrimSpace(subParts[1])
			}
		} else if strings.Contains(line, ":") && !strings.HasPrefix(line, "http") {
			// Định dạng: A: B (Thể loại)
			parts := strings.SplitN(line, ":", 2)
			orig = strings.TrimSpace(parts[0])
			trans = strings.TrimSpace(parts[1])
			cat = "Chung"
		}

		// Xóa các gạch đầu dòng Markdown nếu có
		orig = strings.TrimLeft(orig, "-*•0123456789. ")
		trans = strings.TrimLeft(trans, "-*• ")

		if orig != "" && trans != "" {
			collector.Add(orig, trans, cat, note)
		}
	}
}

func main() {
	var (
		dirFlag        = flag.String("dir", "/Users/macbook-pro/Downloads/tryhard", "Thư mục chứa các file .txt truyện")
		apiKeyFlag     = flag.String("api-key", "", "API Key cho Muse Spark (hoặc đặt biến môi trường MUSE_SPARK_API_KEY)")
		baseURLFlag    = flag.String("base-url", "https://api.empiriolabs.ai/v1", "Base URL của Muse Spark API (OpenAI-compatible)")
		modelFlag      = flag.String("model", "muse-spark-1.3", "Tên model Muse Spark (VD: muse-spark-1.3, muse-spark, meta/muse-spark)")
		outFlag        = flag.String("out", "thuat_ngu_muse_spark.txt", "File xuất danh sách thuật ngữ tổng hợp")
		workersFlag    = flag.Int("workers", 3, "Số luồng gửi API đồng thời (mặc định: 3 để tránh chạm rate limit)")
		batchSizeFlag  = flag.Int("batch", 2, "Số chương gộp vào 1 lượt gọi API để tiết kiệm token và ngữ cảnh tốt hơn")
		limitFlag      = flag.Int("limit", 0, "Giới hạn số chương quét (0 = quét toàn bộ)")
		stepFlag       = flag.Int("step", 1, "Bước nhảy quét (1 = quét từng chương, 2 = quét cách chương)")
	)
	flag.Parse()

	fmt.Println("=================================================================")
	fmt.Println("🚀  TIÊN TÔN TOOL - TRÍCH XUẤT THUẬT NGỮ QUA MUSE SPARK API   🚀")
	fmt.Println("=================================================================")

	apiKey := *apiKeyFlag
	if apiKey == "" {
		apiKey = os.Getenv("MUSE_SPARK_API_KEY")
	}
	if apiKey == "" {
		apiKey = os.Getenv("MUSE_API_KEY")
	}
	if apiKey == "" {
		apiKey = os.Getenv("OPENAI_API_KEY")
	}

	if apiKey == "" {
		fmt.Println("❌ Lỗi: Chưa cung cấp API Key!")
		fmt.Println("Vui lòng truyền qua cờ -api-key hoặc thiết lập biến môi trường MUSE_SPARK_API_KEY:")
		fmt.Println("  go run extract_terms.go -api-key \"YOUR_MUSE_SPARK_KEY\" -dir /Users/macbook-pro/Downloads/tryhard")
		os.Exit(1)
	}

	// Đọc danh sách file trong thư mục
	entries, err := os.ReadDir(*dirFlag)
	if err != nil {
		fmt.Printf("❌ Không thể mở thư mục: %v\n", err)
		os.Exit(1)
	}

	var files []string
	for _, entry := range entries {
		if !entry.IsDir() && strings.HasSuffix(strings.ToLower(entry.Name()), ".txt") && !strings.HasPrefix(entry.Name(), ".") {
			if entry.Name() != "danh_sach_chuong.txt" && entry.Name() != "muc_luc.txt" {
				files = append(files, entry.Name())
			}
		}
	}

	naturalSort(files)

	if len(files) == 0 {
		fmt.Println("⚠️ Không tìm thấy file chương truyện .txt nào!")
		os.Exit(0)
	}

	// Áp dụng limit & step
	var selectedFiles []string
	for i := 0; i < len(files); i += *stepFlag {
		selectedFiles = append(selectedFiles, files[i])
		if *limitFlag > 0 && len(selectedFiles) >= *limitFlag {
			break
		}
	}

	fmt.Printf("📂 Thư mục nguồn      : %s\n", *dirFlag)
	fmt.Printf("📑 Tổng số chương quét: %d / %d chương\n", len(selectedFiles), len(files))
	fmt.Printf("🤖 Mô hình Muse Spark : %s (Endpoint: %s)\n", *modelFlag, *baseURLFlag)
	fmt.Printf("⚡ Luồng song song     : %d worker(s) (Gộp %d chương/lượt)\n", *workersFlag, *batchSizeFlag)
	fmt.Printf("📄 File xuất kết quả  : %s\n", *outFlag)
	fmt.Println("-----------------------------------------------------------------")

	collector := NewGlossaryCollector()

	// Chia thành các batches
	type Batch struct {
		ID    int
		Files []string
	}

	var batches []Batch
	batchID := 1
	for i := 0; i < len(selectedFiles); i += *batchSizeFlag {
		end := i + *batchSizeFlag
		if end > len(selectedFiles) {
			end = len(selectedFiles)
		}
		batches = append(batches, Batch{
			ID:    batchID,
			Files: selectedFiles[i:end],
		})
		batchID++
	}

	totalBatches := len(batches)
	batchChan := make(chan Batch, totalBatches)
	for _, b := range batches {
		batchChan <- b
	}
	close(batchChan)

	var wg sync.WaitGroup
	var completedBatches int
	var progressMu sync.Mutex
	startTime := time.Now()

	for w := 1; w <= *workersFlag; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			for b := range batchChan {
				var combinedText strings.Builder
				for _, fname := range b.Files {
					fpath := filepath.Join(*dirFlag, fname)
					content, err := readFile(fpath)
					if err == nil {
						// Lấy tối đa 1500 ký tự đầu và 1000 ký tự sau để tối ưu token
						if len(content) > 3000 {
							content = content[:1500] + "\n...\n" + content[len(content)-1000:]
						}
						combinedText.WriteString(fmt.Sprintf("\n--- CHƯƠNG: %s ---\n", fname))
						combinedText.WriteString(content)
					}
				}

				output, err := callMuseSpark(*baseURLFlag, apiKey, *modelFlag, combinedText.String())
				if err != nil {
					fmt.Printf("\n⚠️ [Worker %d] Lỗi Batch %d: %v\n", workerID, b.ID, err)
				} else {
					parseAndCollect(output, collector)
				}

				progressMu.Lock()
				completedBatches++
				pct := float64(completedBatches) / float64(totalBatches) * 100
				fmt.Printf("\r⏳ Tiến độ: [%d/%d batch] (%.1f%%) - Đã tìm thấy: %d thuật ngữ...",
					completedBatches, totalBatches, pct, len(collector.terms))
				progressMu.Unlock()

				// Lịch sự nghỉ nhẹ để giữ kết nối ổn định
				time.Sleep(300 * time.Millisecond)
			}
		}(w)
	}

	wg.Wait()
	fmt.Println()

	// Xuất kết quả ra file txt chuẩn hóa
	allTerms := collector.GetAll()

	outFile, err := os.Create(*outFlag)
	if err != nil {
		fmt.Printf("❌ Không thể tạo file xuất: %v\n", err)
		os.Exit(1)
	}
	defer outFile.Close()

	writer := bufio.NewWriter(outFile)
	writer.WriteString("# =================================================================\n")
	fmt.Fprintf(writer, "# TỪ ĐIỂN THUẬT NGỮ TRUYỆN DỊCH - TIÊN TÔN TOOL\n")
	fmt.Fprintf(writer, "# Trích xuất tự động qua: Muse Spark API (%s)\n", *modelFlag)
	fmt.Fprintf(writer, "# Ngày trích xuất: %s | Tổng số: %d thuật ngữ\n", time.Now().Format("2006-01-02 15:04:05"), len(allTerms))
	writer.WriteString("# Định dạng: [Từ gốc/Convert] => [Bản dịch chuẩn] | [Phân loại] | [Ghi chú]\n")
	writer.WriteString("# =================================================================\n\n")

	currentCat := ""
	for _, item := range allTerms {
		cat := item.Category
		if cat == "" {
			cat = "Thuật ngữ chung"
		}
		if cat != currentCat {
			currentCat = cat
			fmt.Fprintf(writer, "\n## [%s]\n", strings.ToUpper(currentCat))
		}
		if item.Note != "" {
			fmt.Fprintf(writer, "%s => %s | %s | %s\n", item.Original, item.Translated, item.Category, item.Note)
		} else {
			fmt.Fprintf(writer, "%s => %s | %s\n", item.Original, item.Translated, item.Category)
		}
	}
	writer.Flush()

	elapsed := time.Since(startTime)
	fmt.Println("-----------------------------------------------------------------")
	fmt.Printf("🎉 HOÀN TẤT TRÍCH XUẤT THUẬT NGỮ TRUYỆN!\n")
	fmt.Printf("⏱️  Thời gian thực thi : %.2f giây\n", elapsed.Seconds())
	fmt.Printf("📖 Tổng số thuật ngữ  : %d thuật ngữ\n", len(allTerms))
	fmt.Printf("📂 Đã ghi vào file     : %s\n", *outFlag)
	fmt.Println("=================================================================")
	fmt.Printf("\n👉 BƯỚC TIẾP THEO:\n")
	fmt.Printf("Sau khi anh chạy script xong và file '%s' được tạo,\n", *outFlag)
	fmt.Println("anh chỉ cần nhắn cho em biết: 'Đã xuất xong file thuat_ngu_muse_spark.txt'.")
	fmt.Println("Em sẽ đọc file này và tự động nạp toàn bộ vào hệ thống names.txt & rules offline của Tiên Tôn Tool!")
}
