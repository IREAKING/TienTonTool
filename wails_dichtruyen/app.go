package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

const bridgeURL = "http://127.0.0.1:58231"

// App struct
type App struct {
	ctx       context.Context
	pyCmd     *exec.Cmd
	bridgeURL string
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{
		bridgeURL: bridgeURL,
	}
}

// checkBridge kiểm tra xem Python bridge server có đang chạy không
func (a *App) checkBridge() bool {
	client := http.Client{
		Timeout: 800 * time.Millisecond,
	}
	resp, err := client.Get(a.bridgeURL + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == 200
}

// startup is called at application startup
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx

	// Tìm đường dẫn tới bridge.py
	bridgeScript := "/Users/macbook-pro/Downloads/Tool_dich_truyen_2.3/mac_tool/bridge.py"

	if exePath, err := os.Executable(); err == nil {
		// Nếu chạy từ trong Bundle: DichTruyen.app/Contents/MacOS/app
		appDir := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(exePath))))
		cand := filepath.Join(appDir, "mac_tool", "bridge.py")
		if _, err := os.Stat(cand); err == nil {
			bridgeScript = cand
		}
	}

	if cwd, err := os.Getwd(); err == nil {
		cand1 := filepath.Join(cwd, "mac_tool", "bridge.py")
		if _, err := os.Stat(cand1); err == nil {
			bridgeScript = cand1
		}
		cand2 := filepath.Join(cwd, "..", "mac_tool", "bridge.py")
		if _, err := os.Stat(cand2); err == nil {
			bridgeScript = cand2
		}
	}

	if a.checkBridge() {
		fmt.Println("Python bridge đã đang chạy sẵn tại", a.bridgeURL)
		return
	}

	// Đường dẫn python conda
	pythonBin := "/usr/local/Caskroom/miniconda/base/envs/dichtruyen/bin/python"
	if _, err := os.Stat(pythonBin); os.IsNotExist(err) {
		pythonBin = "python3"
	}

	// Khởi chạy tiến trình Python bridge
	a.pyCmd = exec.Command(pythonBin, bridgeScript)
	a.pyCmd.Dir = filepath.Dir(bridgeScript)
	a.pyCmd.Env = append(os.Environ(),
		"PYTHONUNBUFFERED=1",
		"PATH=/usr/local/Caskroom/miniconda/base/envs/dichtruyen/bin:"+os.Getenv("PATH"),
	)
	a.pyCmd.Stdout = os.Stdout
	a.pyCmd.Stderr = os.Stderr
	if err := a.pyCmd.Start(); err != nil {
		fmt.Printf("Lỗi khởi chạy Python bridge: %v\n", err)
	} else {
		fmt.Printf("Đã khởi chạy Python bridge PID %d với script %s\n", a.pyCmd.Process.Pid, bridgeScript)
	}

	// Chờ bridge server khởi động
	go func() {
		for i := 0; i < 30; i++ {
			resp, err := http.Get(a.bridgeURL + "/health")
			if err == nil && resp.StatusCode == 200 {
				resp.Body.Close()
				fmt.Println("Python bridge đã sẵn sàng kết nối!")
				break
			}
			time.Sleep(500 * time.Millisecond)
		}
	}()
}

// shutdown is called at application termination
func (a *App) shutdown(ctx context.Context) {
	if a.pyCmd != nil && a.pyCmd.Process != nil {
		fmt.Println("Đang tắt Python bridge...")
		a.pyCmd.Process.Kill()
	}
}

// SelectFolder mở hộp thoại chọn thư mục chuẩn macOS
func (a *App) SelectFolder() (string, error) {
	selected, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Chọn thư mục",
	})
	if err != nil {
		return "", err
	}
	return selected, nil
}

// postJSON helper gửi HTTP POST
func (a *App) postJSON(endpoint string, payload interface{}) (map[string]interface{}, error) {
	jsonData, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	resp, err := http.Post(a.bridgeURL+endpoint, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("không thể kết nối với dịch vụ dịch: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// getJSON helper gửi HTTP GET
func (a *App) getJSON(endpoint string) (map[string]interface{}, error) {
	resp, err := http.Get(a.bridgeURL + endpoint)
	if err != nil {
		return nil, fmt.Errorf("không thể kết nối với dịch vụ dịch: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// TranslateText dịch văn bản trực tiếp
func (a *App) TranslateText(text, model string, beamSize, batchSize int, opencc bool) (map[string]interface{}, error) {
	return a.postJSON("/translate", map[string]interface{}{
		"text":       text,
		"model":      model,
		"beam_size":  beamSize,
		"batch_size": batchSize,
		"opencc":     opencc,
	})
}

// CheckFolder kiểm tra số file trong thư mục
func (a *App) CheckFolder(folder string) (map[string]interface{}, error) {
	return a.postJSON("/check_folder", map[string]interface{}{
		"folder": folder,
	})
}

// StartBatch bắt đầu dịch hàng loạt
func (a *App) StartBatch(inputFolder, outputFolder, suffix, model string, beamSize, batchSize int, opencc bool) (map[string]interface{}, error) {
	return a.postJSON("/start_batch", map[string]interface{}{
		"input_folder":  inputFolder,
		"output_folder": outputFolder,
		"suffix":        suffix,
		"model":         model,
		"beam_size":     beamSize,
		"batch_size":    batchSize,
		"opencc":        opencc,
	})
}

// StopBatch dừng dịch hàng loạt
func (a *App) StopBatch() (map[string]interface{}, error) {
	return a.postJSON("/stop_batch", map[string]interface{}{})
}

// GetBatchStatus lấy trạng thái dịch hàng loạt
func (a *App) GetBatchStatus() (map[string]interface{}, error) {
	return a.getJSON("/batch_status")
}

// GetDictionary lấy nội dung file names.txt
func (a *App) GetDictionary() (map[string]interface{}, error) {
	return a.getJSON("/dict")
}

// SaveDictionary lưu nội dung file names.txt
func (a *App) SaveDictionary(content string) (map[string]interface{}, error) {
	return a.postJSON("/dict", map[string]interface{}{
		"content": content,
	})
}

// AddDictEntry thêm nhanh 1 cặp từ
func (a *App) AddDictEntry(src, tgt string) (map[string]interface{}, error) {
	return a.postJSON("/add_dict_entry", map[string]interface{}{
		"src": src,
		"tgt": tgt,
	})
}

// GetModels lấy danh sách các mô hình
func (a *App) GetModels() (map[string]interface{}, error) {
	return a.getJSON("/models")
}

// LoadModel nạp mô hình vào RAM
func (a *App) LoadModel(model string) (map[string]interface{}, error) {
	return a.postJSON("/load_model", map[string]interface{}{
		"model": model,
	})
}

// GetBridgeStatus trả về trạng thái hoạt động của Python bridge
func (a *App) GetBridgeStatus() map[string]interface{} {
	alive := a.checkBridge()
	return map[string]interface{}{
		"alive": alive,
		"url":   a.bridgeURL,
	}
}

// TestScrapeChapter kiểm tra thử 1 chương
func (a *App) TestScrapeChapter(url, titleSel, contentSel, excludeSel, nextSel string) (map[string]interface{}, error) {
	return a.postJSON("/scraper/test", map[string]interface{}{
		"url":              url,
		"title_selector":   titleSel,
		"content_selector": contentSel,
		"exclude_selector": excludeSel,
		"next_selector":    nextSel,
	})
}

// StartScraper bắt đầu tiến trình cào truyện
func (a *App) StartScraper(config map[string]interface{}) (map[string]interface{}, error) {
	return a.postJSON("/scraper/start", config)
}

// GetScraperStatus lấy trạng thái cào truyện
func (a *App) GetScraperStatus() (map[string]interface{}, error) {
	return a.getJSON("/scraper/status")
}

// StopScraper dừng cào truyện
func (a *App) StopScraper() (map[string]interface{}, error) {
	return a.postJSON("/scraper/stop", map[string]interface{}{})
}

// GetScraperPresets lấy danh sách cấu hình mẫu
func (a *App) GetScraperPresets() (map[string]interface{}, error) {
	return a.getJSON("/scraper/presets")
}

