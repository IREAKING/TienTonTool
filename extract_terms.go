// extract_terms.go — Trích xuất thuật ngữ truyện convert qua Meta Model API (Muse Spark)
//
// Chạy thử:
//
//	export MUSE_SPARK_API_KEY="key_cua_ban"      (hoặc MODEL_API_KEY)
//	go run extract_terms.go -dir ./tryhard -limit 4 -workers 1
//
// Chạy đầy đủ (có thể Ctrl+C rồi chạy lại cùng lệnh để tiếp tục):
//
//	go run extract_terms.go -dir ./tryhard -workers 3
package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unicode/utf8"
)

const promptVersion = "v2"

const systemPrompt = `Bạn là chuyên gia phân tích thuật ngữ tiểu thuyết mạng Trung Quốc (Tiên Hiệp, Huyền Huyễn, Võng Du, Try Hard).
Văn bản đầu vào là truyện dạng convert (Hán-Việt do máy dịch), thường lủng củng.

NHIỆM VỤ: Đọc các chương bên dưới, trích xuất các thuật ngữ đặc thù XUẤT HIỆN TRONG VĂN BẢN kèm bản dịch chuẩn, mượt mà.

QUY TẮC BẮT BUỘC:
1. Cột gốc phải chép NGUYÊN VĂN đúng như trong văn bản (đúng chữ, đúng dấu). Không sửa, không suy diễn.
2. Chỉ trích thuật ngữ thật sự có trong văn bản. Tuyệt đối không dùng ví dụ trong prompt này, không dùng kiến thức về truyện khác.
3. Bỏ qua từ thông dụng, đại từ, câu dài, động từ/tính từ thường.
4. Tên riêng giữ Hán-Việt (bản dịch = bản gốc, trừ khi convert bị tách/sai chữ). Từ lóng, thuật ngữ game dịch sang tiếng Việt tự nhiên.
5. Mỗi thuật ngữ một dòng, không lặp lại.

THỂ LOẠI (chọn đúng một trong các nhãn sau):
Nhân vật | Địa danh/Thế lực | Cảnh giới | Công pháp/Kỹ năng | Pháp bảo/Vật phẩm | Dị thú | Từ lóng/Game | Khác

ĐỊNH DẠNG TRẢ VỀ (mỗi dòng):
Từ gốc => Bản dịch | Thể loại | Ghi chú ngắn

VÍ DỤ CÚ PHÁP (tên giả, chỉ minh họa):
Tên A => Tên A | Nhân vật | Nhân vật chính
Địa điểm B => Địa điểm B | Địa danh/Thế lực | Một thôn làng
Kỹ năng C => Kỹ năng C | Công pháp/Kỹ năng | Chiêu thức kiếm
Từ lóng convert D => cách nói tự nhiên | Từ lóng/Game | Giải thích ngắn

CHỈ TRẢ VỀ DANH SÁCH THEO ĐỊNH DẠNG TRÊN, KHÔNG LỜI DẪN, KHÔNG GIẢI THÍCH.`

// ============================================================
// Kiểu dữ liệu API
// ============================================================

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatRequest struct {
	Model               string        `json:"model"`
	Messages            []chatMessage `json:"messages"`
	Temperature         *float64      `json:"temperature,omitempty"`
	ReasoningEffort     string        `json:"reasoning_effort,omitempty"`
	MaxCompletionTokens int           `json:"max_completion_tokens,omitempty"`
}

type chatResponse struct {
	ID      string `json:"id"`
	Choices []struct {
		Message      chatMessage `json:"message"`
		FinishReason string      `json:"finish_reason"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
		Type    string `json:"type"`
		Code    any    `json:"code"`
	} `json:"error,omitempty"`
}

// fatalError: lỗi cấu hình (key/model/endpoint/tham số sai) — không nên retry, dừng cả chương trình.
type fatalError struct{ msg string }

func (e *fatalError) Error() string { return e.msg }

// ============================================================
// Client
// ============================================================

type Client struct {
	baseURL    string
	apiKey     string
	model      string
	temp       *float64
	reasoning  string
	maxTokens  int
	maxRetries int
	http       *http.Client
}

func sleepCtx(ctx context.Context, d time.Duration) bool {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

func parseRetryAfter(v string) time.Duration {
	if n, err := strconv.Atoi(strings.TrimSpace(v)); err == nil && n > 0 {
		return time.Duration(n) * time.Second
	}
	return 0
}

// chat trả về (nội dung, bị cắt do hết token?, lỗi).
func (c *Client) chat(ctx context.Context, content string) (string, bool, error) {
	url := strings.TrimRight(c.baseURL, "/") + "/chat/completions"

	body := chatRequest{
		Model: c.model,
		Messages: []chatMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: "Văn bản truyện cần bóc tách thuật ngữ:\n\n" + content},
		},
		Temperature:         c.temp,
		ReasoningEffort:     c.reasoning,
		MaxCompletionTokens: c.maxTokens,
	}
	payload, err := json.Marshal(body)
	if err != nil {
		return "", false, err
	}

	var lastErr error
	for attempt := 1; attempt <= c.maxRetries; attempt++ {
		if ctx.Err() != nil {
			return "", false, ctx.Err()
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payload))
		if err != nil {
			return "", false, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+c.apiKey)

		resp, err := c.http.Do(req)
		if err != nil {
			if ctx.Err() != nil {
				return "", false, ctx.Err()
			}
			lastErr = err
			if !sleepCtx(ctx, time.Duration(attempt*2)*time.Second) {
				return "", false, ctx.Err()
			}
			continue
		}

		respBody, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		retryAfter := parseRetryAfter(resp.Header.Get("Retry-After"))

		if readErr != nil {
			lastErr = readErr
			if !sleepCtx(ctx, time.Duration(attempt*2)*time.Second) {
				return "", false, ctx.Err()
			}
			continue
		}

		switch {
		case resp.StatusCode == http.StatusTooManyRequests:
			lastErr = fmt.Errorf("rate limit 429: %s", truncate(string(respBody), 300))
			wait := time.Duration(attempt*5) * time.Second
			if retryAfter > wait {
				wait = retryAfter
			}
			if !sleepCtx(ctx, wait) {
				return "", false, ctx.Err()
			}
			continue

		case resp.StatusCode == http.StatusBadRequest,
			resp.StatusCode == http.StatusUnauthorized,
			resp.StatusCode == http.StatusForbidden,
			resp.StatusCode == http.StatusNotFound:
			hint := ""
			switch resp.StatusCode {
			case http.StatusUnauthorized, http.StatusForbidden:
				hint = " → kiểm tra API key"
			case http.StatusNotFound:
				hint = " → kiểm tra -base-url và -model (thử GET /v1/models)"
			case http.StatusBadRequest:
				hint = " → thử bỏ/đổi -temp, -reasoning, -max-tokens"
			}
			return "", false, &fatalError{fmt.Sprintf("API status %d%s: %s",
				resp.StatusCode, hint, truncate(string(respBody), 400))}

		case resp.StatusCode != http.StatusOK:
			lastErr = fmt.Errorf("API status %d: %s", resp.StatusCode, truncate(string(respBody), 300))
			if !sleepCtx(ctx, time.Duration(attempt*2)*time.Second) {
				return "", false, ctx.Err()
			}
			continue
		}

		var cr chatResponse
		if err := json.Unmarshal(respBody, &cr); err != nil {
			lastErr = fmt.Errorf("JSON không hợp lệ: %w", err)
			continue
		}
		if cr.Error != nil {
			lastErr = fmt.Errorf("API error: %s", cr.Error.Message)
			if !sleepCtx(ctx, time.Duration(attempt*2)*time.Second) {
				return "", false, ctx.Err()
			}
			continue
		}
		if len(cr.Choices) == 0 {
			lastErr = errors.New("không có choices trong phản hồi")
			continue
		}

		text := strings.TrimSpace(cr.Choices[0].Message.Content)
		finish := cr.Choices[0].FinishReason
		if text == "" {
			lastErr = fmt.Errorf("phản hồi rỗng (finish_reason=%q) — có thể reasoning đã dùng hết max-tokens", finish)
			continue
		}
		return text, finish == "length", nil
	}

	return "", false, fmt.Errorf("hết %d lần thử: %w", c.maxRetries, lastErr)
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n]) + "…"
}

// ============================================================
// Từ điển thuật ngữ
// ============================================================

var catOrder = map[string]int{
	"Nhân vật":          0,
	"Địa danh/Thế lực":  1,
	"Cảnh giới":         2,
	"Công pháp/Kỹ năng": 3,
	"Pháp bảo/Vật phẩm": 4,
	"Dị thú":            5,
	"Từ lóng/Game":      6,
	"Khác":              7,
}

func containsAny(s string, subs ...string) bool {
	for _, sub := range subs {
		if strings.Contains(s, sub) {
			return true
		}
	}
	return false
}

// normalizeCategory gom các biến thể "Nhân Vật", "nhân vật"... về một nhãn chuẩn.
func normalizeCategory(c string) string {
	l := strings.ToLower(strings.TrimSpace(c))
	switch {
	case l == "":
		return "Khác"
	case strings.Contains(l, "nhân vật"):
		return "Nhân vật"
	case containsAny(l, "dị thú", "hung thú", "yêu thú", "linh thú", "hung cầm", "thú cưng"):
		return "Dị thú"
	case containsAny(l, "địa danh", "môn phái", "thế lực", "thị tộc", "tổ chức", "cấm địa", "tông môn", "gia tộc"):
		return "Địa danh/Thế lực"
	case containsAny(l, "cảnh giới", "cấp bậc"):
		return "Cảnh giới"
	case containsAny(l, "công pháp", "kỹ năng", "kĩ năng", "chiêu thức", "bí tịch", "bảo thuật", "thần thông", "võ kỹ"):
		return "Công pháp/Kỹ năng"
	case containsAny(l, "pháp bảo", "linh đan", "vật phẩm", "bảo cụ", "đan dược", "trang bị", "linh dược", "đạo cụ"):
		return "Pháp bảo/Vật phẩm"
	case containsAny(l, "lóng", "game", "cày"):
		return "Từ lóng/Game"
	default:
		return "Khác"
	}
}

type TermItem struct {
	Original string
	Category string
	Note     string
	Count    int            // số lần model báo cáo thuật ngữ này
	Trans    map[string]int // các bản dịch đã gặp -> số lần
}

// Best trả về bản dịch phổ biến nhất và danh sách bản dịch còn lại.
func (t *TermItem) Best() (string, []string) {
	type kv struct {
		k string
		v int
	}
	list := make([]kv, 0, len(t.Trans))
	for k, v := range t.Trans {
		list = append(list, kv{k, v})
	}
	sort.Slice(list, func(i, j int) bool {
		if list[i].v != list[j].v {
			return list[i].v > list[j].v
		}
		return list[i].k < list[j].k
	})
	var alts []string
	for _, e := range list[1:] {
		alts = append(alts, fmt.Sprintf("%s (%d)", e.k, e.v))
	}
	return list[0].k, alts
}

type GlossaryCollector struct {
	mu    sync.Mutex
	terms map[string]*TermItem
}

func NewGlossaryCollector() *GlossaryCollector {
	return &GlossaryCollector{terms: make(map[string]*TermItem)}
}

func (gc *GlossaryCollector) Add(original, translated, category, note string) {
	original = strings.Join(strings.Fields(original), " ")
	translated = strings.TrimSpace(translated)
	if original == "" || translated == "" {
		return
	}
	category = normalizeCategory(category)
	key := strings.ToLower(original)

	gc.mu.Lock()
	defer gc.mu.Unlock()

	it, ok := gc.terms[key]
	if !ok {
		it = &TermItem{Original: original, Category: category, Note: note, Trans: map[string]int{}}
		gc.terms[key] = it
	}
	it.Count++
	it.Trans[translated]++
	if it.Category == "Khác" && category != "Khác" {
		it.Category = category
	}
	if it.Note == "" {
		it.Note = note
	}
}

func (gc *GlossaryCollector) Len() int {
	gc.mu.Lock()
	defer gc.mu.Unlock()
	return len(gc.terms)
}

func (gc *GlossaryCollector) GetAll() []*TermItem {
	gc.mu.Lock()
	defer gc.mu.Unlock()

	list := make([]*TermItem, 0, len(gc.terms))
	for _, it := range gc.terms {
		list = append(list, it)
	}
	sort.Slice(list, func(i, j int) bool {
		if list[i].Category != list[j].Category {
			return catOrder[list[i].Category] < catOrder[list[j].Category]
		}
		li, lj := strings.ToLower(list[i].Original), strings.ToLower(list[j].Original)
		if li != lj {
			return li < lj
		}
		return list[i].Original < list[j].Original
	})
	return list
}

// ============================================================
// Parse kết quả model
// ============================================================

var listPrefix = regexp.MustCompile(`^\s*(?:[-*•+]|\d+[.)])\s+`)

func cleanTerm(s string) string {
	s = strings.TrimSpace(s)
	s = strings.Trim(s, "*`[]\"“”' \t")
	return strings.TrimSpace(s)
}

func parseLine(line string) (orig, trans, cat, note string, ok bool) {
	line = strings.TrimSpace(line)
	if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "```") {
		return
	}
	line = strings.TrimSpace(strings.Trim(line, "|"))
	line = listPrefix.ReplaceAllString(line, "")

	sep := ""
	for _, s := range []string{"=>", "→", "->"} {
		if strings.Contains(line, s) {
			sep = s
			break
		}
	}
	if sep == "" {
		return
	}

	parts := strings.SplitN(line, sep, 2)
	orig = cleanTerm(parts[0])
	sub := strings.Split(parts[1], "|")
	trans = cleanTerm(sub[0])
	if len(sub) > 1 {
		cat = cleanTerm(sub[1])
	}
	if len(sub) > 2 {
		note = cleanTerm(strings.Join(sub[2:], "|"))
	}

	n := utf8.RuneCountInString(orig)
	if n < 2 || n > 40 || trans == "" || utf8.RuneCountInString(trans) > 80 {
		return
	}
	ok = true
	return
}

// parseAndCollect chỉ nhận thuật ngữ mà từ gốc THỰC SỰ có trong văn bản đã gửi (chống bịa/chép ví dụ).
func parseAndCollect(output, src string, c *GlossaryCollector) (accepted, rejected int) {
	srcLower := strings.ToLower(src)
	sc := bufio.NewScanner(strings.NewReader(output))
	sc.Buffer(make([]byte, 0, 64*1024), 1<<20)
	for sc.Scan() {
		orig, trans, cat, note, ok := parseLine(sc.Text())
		if !ok {
			continue
		}
		if !strings.Contains(srcLower, strings.ToLower(orig)) {
			rejected++
			continue
		}
		c.Add(orig, trans, cat, note)
		accepted++
	}
	return
}

// ============================================================
// Đọc file, chia đoạn, gộp batch
// ============================================================

var digitRe = regexp.MustCompile(`(\d+)`)

// naturalSort: 0001, 0002, ..., 0010 thay vì 0001, 0010, 0002.
func naturalSort(files []string) {
	sort.Slice(files, func(i, j int) bool {
		partsI := digitRe.Split(files[i], -1)
		partsJ := digitRe.Split(files[j], -1)
		numsI := digitRe.FindAllString(files[i], -1)
		numsJ := digitRe.FindAllString(files[j], -1)

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

func readFile(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	s := strings.TrimPrefix(string(data), "\xef\xbb\xbf") // bỏ BOM
	if !utf8.ValidString(s) {
		s = strings.ToValidUTF8(s, "")
	}
	return s, nil
}

// splitText chia văn bản thành các đoạn <= max ký tự (rune), ưu tiên cắt ở cuối dòng.
func splitText(text string, max int) []string {
	if utf8.RuneCountInString(text) <= max {
		return []string{text}
	}
	var parts []string
	var cur strings.Builder
	curLen := 0
	flush := func() {
		if cur.Len() > 0 {
			parts = append(parts, cur.String())
			cur.Reset()
			curLen = 0
		}
	}
	for _, line := range strings.SplitAfter(text, "\n") {
		l := utf8.RuneCountInString(line)
		if l > max {
			flush()
			r := []rune(line)
			for i := 0; i < len(r); i += max {
				j := i + max
				if j > len(r) {
					j = len(r)
				}
				parts = append(parts, string(r[i:j]))
			}
			continue
		}
		if curLen+l > max {
			flush()
		}
		cur.WriteString(line)
		curLen += l
	}
	flush()
	return parts
}

type Batch struct {
	ID    int
	Key   string
	Text  string
	Files []string
}

func batchKey(model, text string) string {
	h := sha256.Sum256([]byte(model + "\x00" + promptVersion + "\x00" + text))
	return hex.EncodeToString(h[:])[:24]
}

func addUnique(list []string, s string) []string {
	for _, x := range list {
		if x == s {
			return list
		}
	}
	return append(list, s)
}

func summarizeFiles(files []string) string {
	if len(files) <= 3 {
		return strings.Join(files, ", ")
	}
	return fmt.Sprintf("%s, ... (+%d file)", strings.Join(files[:3], ", "), len(files)-3)
}

// ============================================================
// Checkpoint
// ============================================================

type ckptRecord struct {
	Key    string `json:"k"`
	Output string `json:"o"`
}

func loadCheckpoint(path string) map[string]string {
	m := map[string]string{}
	f, err := os.Open(path)
	if err != nil {
		return m
	}
	defer f.Close()
	dec := json.NewDecoder(bufio.NewReaderSize(f, 1<<20))
	for {
		var r ckptRecord
		if err := dec.Decode(&r); err != nil {
			break // EOF hoặc dòng cuối bị dở do crash
		}
		m[r.Key] = r.Output
	}
	return m
}

// ============================================================
// Tiến độ
// ============================================================

type runStats struct {
	mu        sync.Mutex
	total     int
	done      int
	cached    int
	failed    []string
	truncated int
	accepted  int
	rejected  int
}

func (s *runStats) printProgress(termCount int) { // gọi khi đang giữ s.mu
	pct := 0.0
	if s.total > 0 {
		pct = float64(s.done) / float64(s.total) * 100
	}
	fmt.Printf("\r⏳ [%d/%d batch] %.1f%% | thuật ngữ: %d | cache: %d | lỗi: %d   ",
		s.done, s.total, pct, termCount, s.cached, len(s.failed))
}

// ============================================================
// Ghi kết quả
// ============================================================

func writeOutput(path, model string, items []*TermItem) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()

	w := bufio.NewWriter(f)
	w.WriteString("# =================================================================\n")
	fmt.Fprintf(w, "# TỪ ĐIỂN THUẬT NGỮ TRUYỆN DỊCH - TIÊN TÔN TOOL\n")
	fmt.Fprintf(w, "# Trích xuất tự động qua Meta Model API (%s)\n", model)
	fmt.Fprintf(w, "# Ngày: %s | Tổng: %d thuật ngữ\n", time.Now().Format("2006-01-02 15:04:05"), len(items))
	w.WriteString("# Định dạng: [Từ gốc/Convert] => [Bản dịch] | [Phân loại] | [Ghi chú]\n")
	w.WriteString("# Dòng '# ⚠' = thuật ngữ có nhiều bản dịch khác nhau, cần duyệt tay.\n")
	w.WriteString("# =================================================================\n")

	cur := ""
	for _, it := range items {
		if it.Category != cur {
			cur = it.Category
			fmt.Fprintf(w, "\n## [%s]\n", strings.ToUpper(cur))
		}
		best, alts := it.Best()
		if it.Note != "" {
			fmt.Fprintf(w, "%s => %s | %s | %s\n", it.Original, best, it.Category, it.Note)
		} else {
			fmt.Fprintf(w, "%s => %s | %s\n", it.Original, best, it.Category)
		}
		if len(alts) > 0 {
			fmt.Fprintf(w, "# ⚠ %s còn có bản dịch khác: %s\n", it.Original, strings.Join(alts, ", "))
		}
	}
	return w.Flush()
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if v != "" {
			return v
		}
	}
	return ""
}

// ============================================================
// main
// ============================================================

func main() {
	var (
		dirFlag        = flag.String("dir", "/Users/macbook-pro/Downloads/tryhard", "Thư mục chứa các file .txt truyện")
		apiKeyFlag     = flag.String("api-key", "LLM_1817646072560701_QnV8RBYhuHS65VccE0DYkPOlUT8", "API key (khuyên dùng biến môi trường MUSE_SPARK_API_KEY hoặc MODEL_API_KEY thay vì cờ này)")
		baseURLFlag    = flag.String("base-url", "https://api.meta.ai/v1", "Base URL API (OpenAI-compatible)")
		modelFlag      = flag.String("model", "muse-spark-1.3-contributor", "Tên model (kiểm tra bằng GET /v1/models)")
		outFlag        = flag.String("out", "thuat_ngu_muse_spark.txt", "File xuất danh sách thuật ngữ")
		workersFlag    = flag.Int("workers", 3, "Số luồng gọi API đồng thời")
		batchCharsFlag = flag.Int("batch-chars", 12000, "Số ký tự tối đa mỗi lượt gọi API (gộp nhiều chương / chia chương dài)")
		limitFlag      = flag.Int("limit", 0, "Giới hạn số chương quét (0 = tất cả)")
		stepFlag       = flag.Int("step", 1, "Bước nhảy chương (1 = quét mọi chương; >1 sẽ bỏ sót thuật ngữ)")
		tempFlag       = flag.Float64("temp", -1, "Temperature (-1 = không gửi, dùng mặc định của model)")
		reasoningFlag  = flag.String("reasoning", "", "reasoning_effort: minimal|low|medium|high|xhigh (rỗng = không gửi)")
		maxTokensFlag  = flag.Int("max-tokens", 8192, "max_completion_tokens (0 = không gửi)")
		timeoutFlag    = flag.Duration("timeout", 180*time.Second, "Timeout mỗi request")
		retriesFlag    = flag.Int("retries", 4, "Số lần thử tối đa mỗi batch")
		ckptFlag       = flag.String("ckpt", "", "File checkpoint (mặc định: <out>.ckpt.jsonl)")
		freshFlag      = flag.Bool("fresh", false, "Xóa checkpoint, chạy lại từ đầu")
	)
	flag.Parse()

	fmt.Println("=================================================================")
	fmt.Println("🚀  TIÊN TÔN TOOL - TRÍCH XUẤT THUẬT NGỮ (Meta Model API)  🚀")
	fmt.Println("=================================================================")

	apiKey := firstNonEmpty(*apiKeyFlag, os.Getenv("MODEL_API_KEY"), os.Getenv("MUSE_SPARK_API_KEY"),
		os.Getenv("MUSE_API_KEY"), os.Getenv("OPENAI_API_KEY"))
	if apiKey == "" {
		fmt.Println("❌ Chưa có API key. Hãy đặt biến môi trường:")
		fmt.Println("   export MUSE_SPARK_API_KEY=\"key_cua_ban\"")
		os.Exit(1)
	}
	if *stepFlag < 1 {
		*stepFlag = 1
	}
	if *workersFlag < 1 {
		*workersFlag = 1
	}
	if *batchCharsFlag < 2000 {
		*batchCharsFlag = 2000
	}

	// ---- Liệt kê file ----
	entries, err := os.ReadDir(*dirFlag)
	if err != nil {
		fmt.Printf("❌ Không thể mở thư mục: %v\n", err)
		os.Exit(1)
	}
	skip := map[string]bool{
		"danh_sach_chuong.txt":  true,
		"muc_luc.txt":           true,
		filepath.Base(*outFlag): true,
	}
	var files []string
	for _, e := range entries {
		name := e.Name()
		if e.IsDir() || strings.HasPrefix(name, ".") || skip[name] {
			continue
		}
		if strings.HasSuffix(strings.ToLower(name), ".txt") {
			files = append(files, name)
		}
	}
	if len(files) == 0 {
		fmt.Println("⚠️ Không tìm thấy file chương .txt nào!")
		os.Exit(0)
	}
	naturalSort(files)

	var selected []string
	for i := 0; i < len(files); i += *stepFlag {
		selected = append(selected, files[i])
		if *limitFlag > 0 && len(selected) >= *limitFlag {
			break
		}
	}

	// ---- Đọc, chia đoạn, gộp batch (giữ nguyên toàn văn, không cắt mất thân chương) ----
	var batches []Batch
	var curText strings.Builder
	curLen := 0
	var curFiles []string
	flushBatch := func() {
		if curLen == 0 {
			return
		}
		text := curText.String()
		batches = append(batches, Batch{
			ID:    len(batches) + 1,
			Key:   batchKey(*modelFlag, text),
			Text:  text,
			Files: curFiles,
		})
		curText.Reset()
		curLen = 0
		curFiles = nil
	}

	totalChars := 0
	for _, fname := range selected {
		content, err := readFile(filepath.Join(*dirFlag, fname))
		if err != nil {
			fmt.Printf("⚠️ Bỏ qua %s: %v\n", fname, err)
			continue
		}
		content = strings.TrimSpace(content)
		if content == "" {
			continue
		}
		parts := splitText(content, *batchCharsFlag-200) // chừa chỗ cho tiêu đề
		for i, p := range parts {
			header := fmt.Sprintf("\n--- CHƯƠNG: %s ---\n", fname)
			if len(parts) > 1 {
				header = fmt.Sprintf("\n--- CHƯƠNG: %s (phần %d/%d) ---\n", fname, i+1, len(parts))
			}
			piece := header + p + "\n"
			pl := utf8.RuneCountInString(piece)
			totalChars += pl
			if curLen > 0 && curLen+pl > *batchCharsFlag {
				flushBatch()
			}
			curText.WriteString(piece)
			curLen += pl
			curFiles = addUnique(curFiles, fname)
		}
	}
	flushBatch()

	if len(batches) == 0 {
		fmt.Println("⚠️ Không có nội dung để quét.")
		os.Exit(0)
	}

	ckptPath := *ckptFlag
	if ckptPath == "" {
		ckptPath = *outFlag + ".ckpt.jsonl"
	}
	if *freshFlag {
		os.Remove(ckptPath)
	}

	fmt.Printf("📂 Thư mục nguồn : %s\n", *dirFlag)
	fmt.Printf("📑 Chương quét   : %d / %d chương (~%d ký tự)\n", len(selected), len(files), totalChars)
	fmt.Printf("📦 Số batch      : %d (tối đa %d ký tự/batch)\n", len(batches), *batchCharsFlag)
	fmt.Printf("🤖 Model         : %s @ %s\n", *modelFlag, *baseURLFlag)
	fmt.Printf("⚡ Luồng         : %d worker(s)\n", *workersFlag)
	fmt.Printf("💾 Checkpoint    : %s\n", ckptPath)
	fmt.Printf("📄 File xuất     : %s\n", *outFlag)
	fmt.Println("-----------------------------------------------------------------")

	// ---- Context: Ctrl+C dừng êm, lỗi cấu hình dừng toàn bộ ----
	sigCtx, stopSig := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stopSig()
	ctx, cancel := context.WithCancel(sigCtx)
	defer cancel()

	var fatalMu sync.Mutex
	var fatalErr error
	setFatal := func(e error) {
		fatalMu.Lock()
		if fatalErr == nil {
			fatalErr = e
		}
		fatalMu.Unlock()
		cancel()
	}

	client := &Client{
		baseURL:    *baseURLFlag,
		apiKey:     apiKey,
		model:      *modelFlag,
		reasoning:  *reasoningFlag,
		maxTokens:  *maxTokensFlag,
		maxRetries: *retriesFlag,
		http:       &http.Client{Timeout: *timeoutFlag},
	}
	if *tempFlag >= 0 {
		t := *tempFlag
		client.temp = &t
	}
	if client.maxRetries < 1 {
		client.maxRetries = 1
	}
	if client.maxTokens < 0 {
		client.maxTokens = 0
	}

	collector := NewGlossaryCollector()
	stats := &runStats{total: len(batches)}

	// ---- Nạp lại batch đã có trong checkpoint ----
	cache := loadCheckpoint(ckptPath)
	var pending []Batch
	for _, b := range batches {
		if out, ok := cache[b.Key]; ok {
			acc, rej := parseAndCollect(out, b.Text, collector)
			stats.accepted += acc
			stats.rejected += rej
			stats.cached++
			stats.done++
			continue
		}
		pending = append(pending, b)
	}
	if stats.cached > 0 {
		fmt.Printf("♻️  Dùng lại %d batch từ checkpoint, còn %d batch cần gọi API.\n", stats.cached, len(pending))
	}

	ckptFile, err := os.OpenFile(ckptPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		fmt.Printf("❌ Không thể mở file checkpoint: %v\n", err)
		os.Exit(1)
	}
	defer ckptFile.Close()
	ckptEnc := json.NewEncoder(ckptFile)
	var ckptMu sync.Mutex
	saveCkpt := func(key, out string) {
		ckptMu.Lock()
		defer ckptMu.Unlock()
		if err := ckptEnc.Encode(ckptRecord{Key: key, Output: out}); err != nil {
			fmt.Printf("\n⚠️ Không ghi được checkpoint: %v\n", err)
		}
	}

	startTime := time.Now()

	// ---- Worker pool ----
	if len(pending) > 0 {
		queue := make(chan Batch, len(pending))
		for _, b := range pending {
			queue <- b
		}
		close(queue)

		var wg sync.WaitGroup
		for w := 1; w <= *workersFlag; w++ {
			wg.Add(1)
			go func(workerID int) {
				defer wg.Done()
				for b := range queue {
					if ctx.Err() != nil {
						continue // rút cạn hàng đợi khi đã hủy
					}

					out, truncated, err := client.chat(ctx, b.Text)
					if err != nil {
						var fe *fatalError
						if errors.As(err, &fe) {
							setFatal(err)
							continue
						}
						if ctx.Err() != nil {
							continue
						}
						stats.mu.Lock()
						stats.failed = append(stats.failed, fmt.Sprintf("batch %d [%s]", b.ID, summarizeFiles(b.Files)))
						stats.done++
						fmt.Printf("\n⚠️ [Worker %d] Lỗi batch %d (%s): %v\n", workerID, b.ID, summarizeFiles(b.Files), err)
						stats.printProgress(collector.Len())
						stats.mu.Unlock()
						continue
					}

					saveCkpt(b.Key, out)
					acc, rej := parseAndCollect(out, b.Text, collector)

					stats.mu.Lock()
					stats.accepted += acc
					stats.rejected += rej
					stats.done++
					if truncated {
						stats.truncated++
					}
					stats.printProgress(collector.Len())
					stats.mu.Unlock()

					sleepCtx(ctx, 300*time.Millisecond)
				}
			}(w)
		}
		wg.Wait()
	}
	fmt.Println()

	// ---- Ghi kết quả (kể cả khi bị ngắt giữa chừng) ----
	allTerms := collector.GetAll()
	if len(allTerms) > 0 {
		if err := writeOutput(*outFlag, *modelFlag, allTerms); err != nil {
			fmt.Printf("❌ Không thể ghi file xuất: %v\n", err)
			os.Exit(1)
		}
	}

	fmt.Println("-----------------------------------------------------------------")
	fatalMu.Lock()
	fe := fatalErr
	fatalMu.Unlock()

	switch {
	case fe != nil:
		fmt.Printf("❌ DỪNG DO LỖI CẤU HÌNH: %v\n", fe)
	case sigCtx.Err() != nil:
		fmt.Println("⏹️  Đã dừng theo yêu cầu. Chạy lại đúng lệnh cũ để tiếp tục từ checkpoint.")
	default:
		fmt.Println("🎉 HOÀN TẤT TRÍCH XUẤT!")
	}
	fmt.Printf("⏱️  Thời gian     : %.1f giây\n", time.Since(startTime).Seconds())
	fmt.Printf("📖 Thuật ngữ     : %d (nhận %d dòng, loại %d dòng không có trong văn bản)\n",
		len(allTerms), stats.accepted, stats.rejected)
	if stats.truncated > 0 {
		fmt.Printf("⚠️ %d batch bị cắt do hết max-tokens → tăng -max-tokens hoặc giảm -batch-chars/-reasoning.\n", stats.truncated)
	}
	if len(stats.failed) > 0 {
		fmt.Printf("⚠️ %d batch lỗi (chạy lại cùng lệnh sẽ tự thử lại các batch này):\n", len(stats.failed))
		for _, f := range stats.failed {
			fmt.Printf("   - %s\n", f)
		}
	}
	if len(allTerms) > 0 {
		fmt.Printf("📂 Đã ghi vào    : %s\n", *outFlag)
	}
	fmt.Println("=================================================================")

	if fe != nil {
		os.Exit(1)
	}
}