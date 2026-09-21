// ==========================================
// TOAST NOTIFICATION SYSTEM (HOLOGRAPHIC HUD)
// ==========================================
function showToast(message, type = "info", duration = 3200) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "warning") icon = "⚠️";
    if (type === "error") icon = "❌";

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-msg">${message}</span>
        <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
    `;

    toast.addEventListener("click", () => dismissToast(toast));
    container.appendChild(toast);

    const timer = setTimeout(() => {
        dismissToast(toast);
    }, duration);

    function dismissToast(el) {
        clearTimeout(timer);
        if (el.classList.contains("toast-exit")) return;
        el.classList.add("toast-exit");
        el.addEventListener("animationend", () => {
            el.remove();
        });
    }
}

// ==========================================
// UNIFIED SERVICE BRIDGE (WAILS + DIRECT HTTP FALLBACK)
// ==========================================
const HTTP_BRIDGE_URL = "http://127.0.0.1:58231";

class ServiceBridge {
    static async isWailsAvailable() {
        return Boolean(window.go && window.go.main && window.go.main.App);
    }

    static async checkHealth() {
        if (await this.isWailsAvailable()) {
            try {
                const status = await window.go.main.App.GetBridgeStatus();
                if (status && status.alive) return { ok: true, source: "wails" };
            } catch (e) {
                // Thử qua HTTP fallback
            }
        }
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/health`, { method: "GET" });
            if (resp.ok) {
                const data = await resp.json();
                return { ok: true, source: "http", data };
            }
        } catch (e) {
            // Không phản hồi
        }
        return { ok: false };
    }

    static async getModels() {
        if (await this.isWailsAvailable()) {
            try {
                const res = await window.go.main.App.GetModels();
                if (res && res.models) return res;
            } catch (e) {
                console.warn("Wails GetModels failed, trying HTTP fallback:", e);
            }
        }
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/models`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            console.error("HTTP getModels error:", e);
        }
        return { models: [] };
    }

    static async translate(text, model, beamSize = 2, batchSize = 16, opencc = true) {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.TranslateText(text, model, beamSize, batchSize, opencc);
            } catch (e) {
                console.warn("Wails TranslateText failed, trying HTTP fallback:", e);
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/translate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: text,
                model: model,
                beam_size: beamSize,
                batch_size: batchSize,
                opencc: opencc
            })
        });
        return await resp.json();
    }

    static async getDictionary() {
        if (await this.isWailsAvailable()) {
            try {
                const res = await window.go.main.App.GetDictionary();
                if (res && res.content !== undefined) return res;
            } catch (e) {
                console.warn("Wails GetDictionary failed, trying HTTP fallback:", e);
            }
        }
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/dict`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            console.error("HTTP getDictionary error:", e);
        }
        return { content: "" };
    }

    static async saveDictionary(content) {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.SaveDictionary(content);
            } catch (e) {
                console.warn("Wails SaveDictionary failed, trying HTTP fallback:", e);
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/dict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content })
        });
        return await resp.json();
    }

    static async addDictEntry(src, tgt) {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.AddDictEntry(src, tgt);
            } catch (e) {
                console.warn("Wails AddDictEntry failed, trying HTTP fallback:", e);
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/add_dict_entry`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ src, tgt })
        });
        return await resp.json();
    }

    static async selectFolder() {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.SelectFolder();
            } catch (e) {
                console.error("Lỗi SelectFolder:", e);
            }
        }
        return "";
    }

    static async checkFolder(folder) {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.CheckFolder(folder);
            } catch (e) {
                console.warn("Wails CheckFolder failed, trying HTTP fallback:", e);
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/check_folder`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder })
        });
        return await resp.json();
    }

    static async startBatch(inputFolder, outputFolder, suffix, model, beamSize, batchSize, opencc, concurrency = 3, autoClean = true) {
        const resp = await fetch(`${HTTP_BRIDGE_URL}/start_batch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                input_folder: inputFolder,
                output_folder: outputFolder,
                suffix: suffix,
                model: model,
                beam_size: beamSize,
                batch_size: batchSize,
                opencc: opencc,
                concurrency: concurrency,
                auto_clean: autoClean
            })
        });
        return await resp.json();
    }

    static async extractGlossary(text, method = "auto", engine = "gemini", minCount = 1) {
        const resp = await fetch(`${HTTP_BRIDGE_URL}/glossary/extract`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: text,
                method: method,
                engine: engine,
                min_count: minCount
            })
        });
        return await resp.json();
    }

    static async batchAddGlossary(entries) {
        const resp = await fetch(`${HTTP_BRIDGE_URL}/glossary/batch_add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ entries: entries })
        });
        return await resp.json();
    }

    static async lookupGlossary(text) {
        const resp = await fetch(`${HTTP_BRIDGE_URL}/glossary/lookup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text })
        });
        return await resp.json();
    }

    static async alignBilingual(src, tgt) {
        const resp = await fetch(`${HTTP_BRIDGE_URL}/bilingual/align`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ src: src, tgt: tgt })
        });
        return await resp.json();
    }

    static async getBatchStatus() {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.GetBatchStatus();
            } catch (e) {
                // HTTP fallback
            }
        }
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/batch_status`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            // Không phản hồi
        }
        return null;
    }

    static async stopBatch() {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.StopBatch();
            } catch (e) {
                // HTTP fallback
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/stop_batch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        return await resp.json();
    }

    static async getScraperPresets() {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.GetScraperPresets();
            } catch (e) {
                // fallback
            }
        }
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/scraper/presets`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            // error
        }
        return {};
    }

    static async testScrapeChapter(url, titleSel, contentSel, excludeSel, nextSel) {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.TestScrapeChapter(url, titleSel, contentSel, excludeSel, nextSel);
            } catch (e) {
                console.warn("Wails TestScrapeChapter fallback:", e);
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/scraper/test`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url,
                title_selector: titleSel,
                content_selector: contentSel,
                exclude_selector: excludeSel,
                next_selector: nextSel
            })
        });
        return await resp.json();
    }

    static async startScraper(config) {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.StartScraper(config);
            } catch (e) {
                console.warn("Wails StartScraper fallback:", e);
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/scraper/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        });
        return await resp.json();
    }

    static async getScraperStatus() {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.GetScraperStatus();
            } catch (e) {
                // fallback
            }
        }
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/scraper/status`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            // error
        }
        return null;
    }

    static async stopScraper() {
        if (await this.isWailsAvailable()) {
            try {
                return await window.go.main.App.StopScraper();
            } catch (e) {
                // fallback
            }
        }
        const resp = await fetch(`${HTTP_BRIDGE_URL}/scraper/stop`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });
        return await resp.json();
    }

    static async scanToc(url, tocSelector) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/scraper/toc`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url, toc_selector: tocSelector })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi scanToc:", e);
            return { error: String(e), chapters: [] };
        }
    }

    static async mergeTxt(folder, title, author) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/export/merge_txt`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ folder, title, author })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi mergeTxt:", e);
            return { success: false, error: String(e) };
        }
    }

    static async exportEpub(folder, title, author) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/export/epub`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ folder, title, author })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi exportEpub:", e);
            return { success: false, error: String(e) };
        }
    }

    static async getSettings() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/settings`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            console.error("Lỗi getSettings:", e);
        }
        return null;
    }

    static async saveSettings(newConfig) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/settings`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newConfig)
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi saveSettings:", e);
            return { success: false, error: String(e) };
        }
    }

    static async getTtsVoices() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/tts/voices`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            console.error("Lỗi getTtsVoices:", e);
        }
        return { voices: [] };
    }

    static async getCloneVoices() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/tts/clone_voices`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            console.error("Lỗi getCloneVoices:", e);
        }
        return { voices: [] };
    }

    static getSampleAudioUrl(voiceId) {
        return `${HTTP_BRIDGE_URL}/tts/sample_audio/${encodeURIComponent(voiceId)}`;
    }

    static async speakTts(text, voice, speed = 1.0, normalize = true, onProgress = null) {
        try {
            const startResp = await fetch(`${HTTP_BRIDGE_URL}/tts/task_start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, voice, speed, normalize })
            });
            if (!startResp.ok) {
                const errJson = await startResp.json().catch(() => ({}));
                return { success: false, error: errJson.error || "Không thể khởi tạo tiến trình đọc audio" };
            }
            const startData = await startResp.json();
            const taskId = startData.task_id;
            if (!taskId) {
                return { success: false, error: "Không lấy được mã tiến trình đọc" };
            }

            // Polling tiến trình thời gian thực
            while (true) {
                await new Promise(r => setTimeout(r, 400));
                try {
                    const statusResp = await fetch(`${HTTP_BRIDGE_URL}/tts/task_status?id=${encodeURIComponent(taskId)}`);
                    if (!statusResp.ok) continue;
                    const task = await statusResp.json();
                    if (task.status === "in_progress") {
                        if (onProgress) {
                            onProgress(task.progress || 0, task.current_chunk || 0, task.total_chunks || 0, task.status_msg);
                        }
                    } else if (task.status === "done") {
                        if (onProgress) {
                            onProgress(100, task.total_chunks || 1, task.total_chunks || 1, "Hoàn tất!");
                        }
                        return {
                            success: true,
                            audio_url: task.audio_url,
                            filename: task.filename,
                            file_path: task.file_path
                        };
                    } else if (task.status === "error") {
                        return { success: false, error: task.error || "Lỗi tổng hợp âm thanh" };
                    }
                } catch (pollErr) {
                    console.warn("Poll status error, retrying...", pollErr);
                }
            }
        } catch (e) {
            console.error("Lỗi speakTts:", e);
            let msg = String(e);
            if (msg.includes("Load failed") || msg.includes("Failed to fetch")) {
                msg = "Không thể kết nối đến TTS Service (Đang khởi động lại). Vui lòng thử lại!";
            }
            return { success: false, error: msg };
        }
    }

    static async startBatchTts(inputFolder, outputFolder, voice, speed = 1.0, normalize = true) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/tts/batch_start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    input_folder: inputFolder,
                    output_folder: outputFolder,
                    voice,
                    speed,
                    normalize
                })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi startBatchTts:", e);
            return { success: false, error: String(e) };
        }
    }

    static async getBatchTtsStatus() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/tts/batch_status`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            // fallback
        }
        return null;
    }

    static async stopBatchTts() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/tts/batch_stop`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi stopBatchTts:", e);
            return { success: false, error: String(e) };
        }
    }

    static async polishConvert(text, mode = "rules", engine = "deepseek", genre = "xianxia") {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/convert/polish`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, mode, engine, genre })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi polishConvert:", e);
            return { error: String(e), result: "" };
        }
    }

    static async startBatchConvert(inputFolder, outputFolder, mode = "rules", engine = "deepseek", genre = "xianxia", suffix = "_dich") {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/convert/batch_start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    input_folder: inputFolder,
                    output_folder: outputFolder,
                    mode,
                    engine,
                    genre,
                    suffix
                })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi startBatchConvert:", e);
            return { error: String(e) };
        }
    }

    static async getBatchConvertStatus() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/convert/batch_status`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            // ignore
        }
        return null;
    }

    static async stopBatchConvert() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/convert/batch_stop`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi stopBatchConvert:", e);
            return { error: String(e) };
        }
    }

    static async cleanText(text, removeWatermarks = true) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/clean_text`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, remove_watermarks: removeWatermarks })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi cleanText:", e);
            return { error: String(e), result: text, count: 0 };
        }
    }

    static async cleanFolder(inputFolder, outputFolder, suffix = "_clean", removeWatermarks = true) {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/clean_folder`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    input_folder: inputFolder,
                    output_folder: outputFolder,
                    suffix,
                    remove_watermarks: removeWatermarks
                })
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi cleanFolder:", e);
            return { error: String(e) };
        }
    }

    static async getCleanFolderStatus() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/clean_folder_status`);
            if (resp.ok) return await resp.json();
        } catch (e) {
            // ignore
        }
        return null;
    }

    static async stopCleanFolder() {
        try {
            const resp = await fetch(`${HTTP_BRIDGE_URL}/clean_folder_stop`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            });
            return await resp.json();
        } catch (e) {
            console.error("Lỗi stopCleanFolder:", e);
            return { error: String(e) };
        }
    }
}

// ==========================================
// KHỞI ĐỘNG ỨNG DỤNG
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initTextTranslation();
    initBilingualStudio();
    initBatchTranslation();
    initConvert();
    initScraper();
    initTts();
    initDictionary();
    initAutoGlossary();
    initSettings();
    startHealthMonitor();
});

function switchTab(tabId) {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    navItems.forEach(i => i.classList.remove("active"));
    tabPanes.forEach(p => p.classList.remove("active"));
    const btn = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (btn) btn.classList.add("active");
    const pane = document.getElementById(tabId);
    if (pane) pane.classList.add("active");
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ==========================================
// CHUYỂN TAB CÓ HIỆU ỨNG
// ==========================================
function initTabs() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetId = item.getAttribute("data-tab");

            navItems.forEach(i => i.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            item.classList.add("active");
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add("active");
            }
        });
    });
}

// ==========================================
// TAB 1: DỊCH VĂN BẢN TRỰC TIẾP
// ==========================================
function initTextTranslation() {
    const srcText = document.getElementById("src-text");
    const tgtText = document.getElementById("tgt-text");
    const btnTranslate = document.getElementById("btn-translate-now");
    const btnClear = document.getElementById("btn-clear-src");
    const btnPaste = document.getElementById("btn-paste-src");
    const btnCopy = document.getElementById("btn-copy-tgt");
    const srcCounter = document.getElementById("src-counter");
    const tgtCounter = document.getElementById("tgt-counter");
    const timeBadge = document.getElementById("trans-time");

    const quickModelSelect = document.getElementById("quick-model-select");
    const quickBeamSelect = document.getElementById("quick-beam-select");
    const quickOpenCC = document.getElementById("quick-opencc");

    // Đếm ký tự thời gian thực
    srcText.addEventListener("input", () => {
        srcCounter.textContent = `${srcText.value.length.toLocaleString()} ký tự`;
    });

    btnClear.addEventListener("click", () => {
        srcText.value = "";
        tgtText.value = "";
        srcCounter.textContent = "0 ký tự";
        tgtCounter.textContent = "0 từ";
        timeBadge.textContent = "⚡ 0.00s";
        showToast("Đã xóa nội dung văn bản", "info", 1800);
    });

    btnPaste.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                srcText.value = text;
                srcCounter.textContent = `${text.length.toLocaleString()} ký tự`;
                showToast("Đã dán văn bản từ clipboard!", "info", 2000);
            } else {
                showToast("Clipboard đang trống!", "warning", 2000);
            }
        } catch (e) {
            showToast("Không thể đọc clipboard: " + e, "error");
        }
    });

    const btnScanNamesQuick = document.getElementById("btn-scan-names-quick");
    if (btnScanNamesQuick) {
        btnScanNamesQuick.addEventListener("click", () => {
            const raw = srcText.value.trim();
            if (!raw) {
                showToast("Vui lòng dán văn bản tiếng Trung cần quét tên riêng!", "warning");
                return;
            }
            if (window.triggerQuickScanFromText) {
                window.triggerQuickScanFromText(raw);
            }
        });
    }

    const btnOpenInStudio = document.getElementById("btn-open-in-studio");
    if (btnOpenInStudio) {
        btnOpenInStudio.addEventListener("click", () => {
            const s = srcText.value.trim();
            const t = tgtText.value.trim();
            if (!s && !t) {
                showToast("Vui lòng có ít nhất văn bản tiếng Trung hoặc bản dịch để mở Studio!", "warning");
                return;
            }
            switchTab("tab-bilingual");
            if (window.loadBilingualStudio) {
                window.loadBilingualStudio(s, t);
            }
        });
    }

    const btnCleanSrc = document.getElementById("btn-clean-src");
    if (btnCleanSrc) {
        btnCleanSrc.addEventListener("click", async () => {
            const raw = srcText.value;
            if (!raw.trim()) {
                showToast("Vui lòng nhập hoặc dán văn bản trước khi khử rác!", "warning", 2000);
                return;
            }
            btnCleanSrc.disabled = true;
            try {
                const res = await ServiceBridge.cleanText(raw);
                if (res && res.result) {
                    srcText.value = res.result;
                    srcCounter.textContent = `${res.result.length.toLocaleString()} ký tự`;
                    showToast(`Đã khử sạch ${res.count || 0} từ bị chèn dấu rác (c·hết ➔ chết, b·ạo đ·ộng ➔ bạo động)!`, "success", 3000);
                }
            } catch (err) {
                showToast("Lỗi khử rác: " + err, "error");
            } finally {
                btnCleanSrc.disabled = false;
            }
        });
    }

    btnCopy.addEventListener("click", async () => {
        if (tgtText.value) {
            await navigator.clipboard.writeText(tgtText.value);
            btnCopy.innerHTML = "<span>✅ Đã chép</span>";
            showToast("Đã sao chép bản dịch vào clipboard!", "success", 2200);
            setTimeout(() => {
                btnCopy.innerHTML = "<span>📋 Sao chép</span>";
            }, 1800);
        } else {
            showToast("Chưa có bản dịch nào để sao chép!", "warning", 2000);
        }
    });

    btnTranslate.addEventListener("click", async () => {
        const text = srcText.value.trim();
        if (!text) {
            showToast("Vui lòng nhập hoặc dán văn bản tiếng Trung cần dịch!", "warning");
            return;
        }

        btnTranslate.disabled = true;
        btnTranslate.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-label">Đang suy luận AI...</span>';

        try {
            const model = quickModelSelect.value || "DanVP/MoxhiMT-60 (Đỉnh Cao Tiên Hiệp - Văn phong đỉnh cao)";
            const beam = parseInt(quickBeamSelect.value) || 2;
            const opencc = quickOpenCC.checked;

            const res = await ServiceBridge.translate(text, model, beam, 16, opencc);
            if (res && res.result) {
                tgtText.value = res.result;
                const words = res.result.trim().split(/\s+/).length;
                tgtCounter.textContent = `${words.toLocaleString()} từ`;
                timeBadge.textContent = `⚡ ${res.time || 0}s`;
                showToast(`Dịch thành công ${words.toLocaleString()} từ trong ${res.time || 0}s!`, "success", 3000);
            } else if (res && res.error) {
                showToast("Lỗi dịch: " + res.error, "error", 4000);
            } else {
                showToast("Không nhận được phản hồi từ AI Service!", "error", 4000);
            }
        } catch (err) {
            showToast("Lỗi kết nối AI Service: " + err, "error", 4000);
        } finally {
            btnTranslate.disabled = false;
            btnTranslate.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-label">Bắt đầu dịch</span><div class="btn-shimmer"></div>';
        }
    });
}

// ==========================================
// TAB 2: DỊCH HÀNG LOẠT
// ==========================================
let batchInterval = null;

function initBatchTranslation() {
    const inputFolder = document.getElementById("batch-input-folder");
    const outputFolder = document.getElementById("batch-output-folder");
    const btnSelectInput = document.getElementById("btn-select-input-folder");
    const btnSelectOutput = document.getElementById("btn-select-output-folder");
    const btnScan = document.getElementById("btn-scan-folder");
    const btnStart = document.getElementById("btn-start-batch");
    const btnStop = document.getElementById("btn-stop-batch");
    const statusText = document.getElementById("batch-status-text");
    const percentageText = document.getElementById("batch-percentage");
    const progressBar = document.getElementById("batch-progress-bar");
    const logContent = document.getElementById("batch-log-content");
    const suffixInput = document.getElementById("batch-suffix");
    const modelSelect = document.getElementById("batch-model-select");

    // Chọn thư mục chuẩn macOS Finder
    btnSelectInput.addEventListener("click", async () => {
        const selected = await ServiceBridge.selectFolder();
        if (selected) {
            inputFolder.value = selected;
            showToast("Đã chọn thư mục nguồn: " + selected.split("/").pop(), "info", 2200);
        }
    });

    btnSelectOutput.addEventListener("click", async () => {
        const selected = await ServiceBridge.selectFolder();
        if (selected) {
            outputFolder.value = selected;
            showToast("Đã chọn thư mục xuất kết quả", "info", 2200);
        }
    });

    // Quét và đếm file .txt
    btnScan.addEventListener("click", async () => {
        const folder = inputFolder.value.trim();
        if (!folder) {
            showToast("Vui lòng nhập hoặc chọn thư mục nguồn trước!", "warning");
            return;
        }

        try {
            const res = await ServiceBridge.checkFolder(folder);
            if (res && res.count !== undefined) {
                logContent.textContent = `[QUÉT THÀNH CÔNG] Tìm thấy ${res.count} file .txt hợp lệ trong thư mục:\n` + res.preview.join("\n");
                statusText.textContent = `Sẵn sàng dịch ${res.count} file.`;
                showToast(`Tìm thấy ${res.count} file .txt chương truyện!`, "success", 3000);
            } else {
                showToast("Lỗi kiểm tra thư mục: " + (res.error || ""), "error");
            }
        } catch (err) {
            showToast("Lỗi: " + err, "error");
        }
    });

    // Bắt đầu dịch hàng loạt
    btnStart.addEventListener("click", async () => {
        const inF = inputFolder.value.trim();
        if (!inF) {
            showToast("Vui lòng nhập hoặc chọn thư mục nguồn!", "warning");
            return;
        }

        const outF = outputFolder.value.trim();
        const suffix = suffixInput.value.trim() || "_viet";
        const model = modelSelect.value || "DanVP/MoxhiMT-60 (Đỉnh Cao Tiên Hiệp - Văn phong đỉnh cao)";
        const concurrencySelect = document.getElementById("batch-concurrency-select");
        const autoCleanCheck = document.getElementById("batch-auto-clean-censor");
        const concurrency = concurrencySelect ? (parseInt(concurrencySelect.value) || 3) : 3;
        const autoClean = autoCleanCheck ? autoCleanCheck.checked : true;

        btnStart.disabled = true;
        btnStop.disabled = false;

        try {
            await ServiceBridge.startBatch(inF, outF, suffix, model, 2, 16, true, concurrency, autoClean);
            showToast(`Đã kích hoạt dịch hàng loạt (${concurrency} luồng song song, auto-save)!`, "info", 3000);
            startBatchPolling();
        } catch (err) {
            showToast("Lỗi khởi chạy batch: " + err, "error");
            btnStart.disabled = false;
            btnStop.disabled = true;
        }
    });

    // Dừng tiến trình
    btnStop.addEventListener("click", async () => {
        await ServiceBridge.stopBatch();
        btnStop.disabled = true;
        showToast("Đã gửi tín hiệu dừng tiến trình!", "warning", 2500);
    });
}

function startBatchPolling() {
    if (batchInterval) clearInterval(batchInterval);

    const statusText = document.getElementById("batch-status-text");
    const percentageText = document.getElementById("batch-percentage");
    const progressBar = document.getElementById("batch-progress-bar");
    const logContent = document.getElementById("batch-log-content");
    const btnStart = document.getElementById("btn-start-batch");
    const btnStop = document.getElementById("btn-stop-batch");

    batchInterval = setInterval(async () => {
        try {
            const state = await ServiceBridge.getBatchStatus();
            if (state) {
                statusText.textContent = state.status_msg || "Đang xử lý...";
                const pct = Math.round((state.progress || 0) * 100);
                percentageText.textContent = `${pct}%`;
                progressBar.style.width = `${pct}%`;

                if (state.logs && state.logs.length > 0) {
                    logContent.textContent = state.logs.slice(-50).join("\n");
                    logContent.scrollTop = logContent.scrollHeight;
                }

                if (!state.is_running) {
                    clearInterval(batchInterval);
                    btnStart.disabled = false;
                    btnStop.disabled = true;
                    if (pct >= 100) {
                        showToast("Đã hoàn tất dịch tất cả các file chương truyện!", "success", 4500);
                    }
                }
            }
        } catch (e) {
            console.error("Lỗi polling batch:", e);
        }
    }, 600);
}

// ==========================================
// TAB: CHUYỂN CONVERT SANG TRUYỆN DỊCH
// ==========================================
let convertBatchInterval = null;

function initConvert() {
    const srcText = document.getElementById("convert-src-text");
    const tgtText = document.getElementById("convert-tgt-text");
    const srcCounter = document.getElementById("convert-src-counter");
    const tgtCounter = document.getElementById("convert-tgt-counter");
    const timeBadge = document.getElementById("convert-time");

    const btnSample = document.getElementById("btn-convert-sample");
    const btnPaste = document.getElementById("btn-paste-convert");
    const btnClear = document.getElementById("btn-clear-convert");
    const btnPolish = document.getElementById("btn-convert-polish-now");
    const btnCopy = document.getElementById("btn-copy-convert-tgt");
    const btnToTts = document.getElementById("btn-convert-to-tts");

    const modeSelect = document.getElementById("convert-mode-select");
    const genreSelect = document.getElementById("convert-genre-select");

    // Đếm ký tự và từ
    function updateCounters() {
        if (srcText && srcCounter) {
            const chars = srcText.value.length;
            const words = srcText.value.trim() ? srcText.value.trim().split(/\s+/).length : 0;
            srcCounter.textContent = `${chars} ký tự (${words} từ)`;
        }
        if (tgtText && tgtCounter) {
            const words = tgtText.value.trim() ? tgtText.value.trim().split(/\s+/).length : 0;
            tgtCounter.textContent = `${words} từ`;
        }
    }

    if (srcText) {
        srcText.addEventListener("input", updateCounters);
    }
    if (tgtText) {
        tgtText.addEventListener("input", updateCounters);
    }

    // Đoạn convert mẫu
    if (btnSample) {
        btnSample.addEventListener("click", () => {
            const sample = `Thời gian dần qua, tại đan điền bên trong, nương theo lấy một cỗ uy áp kinh khủng bùng nổ, hắn chính mình không khỏi hít sâu một hơi khí lạnh.
Cái này một màn làm cho hắn nhóm toàn thân chấn động kịch liệt!
Hắn c·hết rồi, bị g·iết trong một cuộc b·ạo đ·ộng đ·ẫm m·áu tại hoàng cung bên trong.
Hắn hướng phía sơn cốc mà đi, thầm nghĩ nói: Làm sao có thể! Đến tột cùng là người phương nào xuất thủ?
Bị người ngăn cản phía trước, trong mắt hắn lóe lên một tia hàn mang, hét lớn một tiếng: Muốn chết sao!`;
            srcText.value = sample;
            updateCounters();
            showToast("Đã chèn đoạn văn convert mẫu (chứa c·hết, g·iết, b·ạo đ·ộng)!", "info", 2500);
        });
    }

    // Nút Khử ký tự rác (c·hết -> chết, g·iết -> giết, b·ạo đ·ộng -> bạo động)
    const btnCleanDecensor = document.getElementById("btn-clean-decensor");
    if (btnCleanDecensor) {
        btnCleanDecensor.addEventListener("click", async () => {
            const raw = srcText.value;
            if (!raw.trim()) {
                showToast("Vui lòng dán văn bản convert hoặc truyện cần khử rác trước!", "warning", 2000);
                return;
            }
            btnCleanDecensor.disabled = true;
            try {
                const res = await ServiceBridge.cleanText(raw);
                if (res && res.result) {
                    srcText.value = res.result;
                    updateCounters();
                    showToast(`Đã khử sạch ${res.count || 0} từ bị chèn dấu rác (c·hết ➔ chết, g·iết ➔ giết, b·ạo đ·ộng ➔ bạo động)!`, "success", 3000);
                }
            } catch (err) {
                showToast("Lỗi khử rác: " + err, "error");
            } finally {
                btnCleanDecensor.disabled = false;
            }
        });
    }

    // Dán từ clipboard
    if (btnPaste) {
        btnPaste.addEventListener("click", async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    srcText.value = text;
                    updateCounters();
                    showToast("Đã dán văn bản từ clipboard!", "success", 1800);
                }
            } catch (err) {
                showToast("Không thể truy cập clipboard: " + err, "error");
            }
        });
    }

    // Xóa nội dung
    if (btnClear) {
        btnClear.addEventListener("click", () => {
            srcText.value = "";
            tgtText.value = "";
            updateCounters();
            timeBadge.textContent = "⚡ 0.00s";
            showToast("Đã xóa trắng khung nhập!", "info", 1500);
        });
    }

    // Gọt giũa convert -> dịch
    if (btnPolish) {
        btnPolish.addEventListener("click", async () => {
            const text = srcText.value.trim();
            if (!text) {
                showToast("Vui lòng dán văn bản convert cần chuyển đổi!", "warning", 2000);
                return;
            }

            const rawMode = modeSelect.value;
            let mode = "rules";
            let engine = "deepseek";

            if (rawMode === "hybrid") {
                mode = "hybrid";
                engine = "deepseek";
            } else if (rawMode === "ai-deepseek") {
                mode = "ai";
                engine = "deepseek";
            } else if (rawMode === "ai-gemini") {
                mode = "ai";
                engine = "gemini";
            } else {
                mode = "rules";
            }

            const genre = genreSelect.value || "xianxia";

            btnPolish.disabled = true;
            btnPolish.innerHTML = `<span class="btn-icon">⏳</span><span class="btn-label">Đang gọt giũa văn phong...</span>`;
            timeBadge.textContent = "⏳ Đang xử lý...";

            const startT = performance.now();
            try {
                const res = await ServiceBridge.polishConvert(text, mode, engine, genre);
                const elapsed = ((performance.now() - startT) / 1000).toFixed(2);
                timeBadge.textContent = `⚡ ${res.time !== undefined ? res.time : elapsed}s`;

                if (res.error) {
                    showToast("Lỗi chuyển đổi: " + res.error, "error", 4000);
                } else if (res.result) {
                    tgtText.value = res.result;
                    updateCounters();
                    showToast("Đã chuyển convert sang truyện dịch thành công!", "success", 2500);
                }
            } catch (err) {
                showToast("Lỗi kết nối: " + err, "error");
            } finally {
                btnPolish.disabled = false;
                btnPolish.innerHTML = `<span class="btn-icon">✨</span><span class="btn-label">Chuyển Sang Truyện Dịch</span><div class="btn-shimmer"></div>`;
            }
        });
    }

    // Sao chép kết quả
    if (btnCopy) {
        btnCopy.addEventListener("click", async () => {
            const text = tgtText.value.trim();
            if (!text) {
                showToast("Chưa có bản dịch nào để sao chép!", "warning", 2000);
                return;
            }
            try {
                await navigator.clipboard.writeText(text);
                showToast("Đã sao chép bản dịch vào clipboard!", "success", 2000);
            } catch (err) {
                showToast("Lỗi sao chép: " + err, "error");
            }
        });
    }

    // Đọc Audio TTS
    if (btnToTts) {
        btnToTts.addEventListener("click", () => {
            const text = tgtText.value.trim();
            if (!text) {
                showToast("Vui lòng thực hiện chuyển đổi trước khi đọc Audio!", "warning", 2000);
                return;
            }
            const ttsInput = document.getElementById("tts-input-text");
            if (ttsInput) {
                ttsInput.value = text;
            }
            const navTts = document.querySelector('[data-tab="tab-tts"]');
            if (navTts) {
                navTts.click();
                showToast("Đã chuyển nội dung sang Trình Đọc Audio (TTS)!", "success", 2500);
            }
        });
    }

    // ==========================================
    // CHUYỂN ĐỔI HÀNG LOẠT THEO THƯ MỤC
    // ==========================================
    const inputFolder = document.getElementById("convert-batch-input-folder");
    const outputFolder = document.getElementById("convert-batch-output-folder");
    const btnSelectInput = document.getElementById("btn-select-convert-input-folder");
    const btnSelectOutput = document.getElementById("btn-select-convert-output-folder");
    const batchModeSelect = document.getElementById("convert-batch-mode-select");
    const batchGenreSelect = document.getElementById("convert-batch-genre-select");
    const suffixInput = document.getElementById("convert-batch-suffix");
    const btnBatchStart = document.getElementById("btn-convert-batch-start");
    const btnBatchStop = document.getElementById("btn-convert-batch-stop");

    if (btnSelectInput) {
        btnSelectInput.addEventListener("click", async () => {
            const selected = await ServiceBridge.selectFolder();
            if (selected) {
                inputFolder.value = selected;
                showToast("Đã chọn thư mục: " + selected.split("/").pop(), "info", 2000);
            }
        });
    }

    if (btnSelectOutput) {
        btnSelectOutput.addEventListener("click", async () => {
            const selected = await ServiceBridge.selectFolder();
            if (selected) {
                outputFolder.value = selected;
                showToast("Đã chọn thư mục xuất kết quả", "info", 2000);
            }
        });
    }

    if (btnBatchStart) {
        btnBatchStart.addEventListener("click", async () => {
            const inF = inputFolder.value.trim();
            if (!inF) {
                showToast("Vui lòng chọn thư mục chứa các chương Convert!", "warning", 2500);
                return;
            }

            const outF = outputFolder.value.trim();
            const rawMode = batchModeSelect.value;
            let mode = "rules";
            let engine = "deepseek";

            if (rawMode === "hybrid") {
                mode = "hybrid";
                engine = "deepseek";
            } else if (rawMode === "ai-deepseek") {
                mode = "ai";
                engine = "deepseek";
            } else if (rawMode === "ai-gemini") {
                mode = "ai";
                engine = "gemini";
            } else {
                mode = "rules";
            }

            const genre = batchGenreSelect.value || "xianxia";
            const suffix = suffixInput.value.trim() || "_dich";

            btnBatchStart.disabled = true;
            btnBatchStop.disabled = false;

            try {
                const res = await ServiceBridge.startBatchConvert(inF, outF, mode, engine, genre, suffix);
                if (res.error) {
                    showToast("Lỗi khởi chạy: " + res.error, "error");
                    btnBatchStart.disabled = false;
                    btnBatchStop.disabled = true;
                    return;
                }
                showToast("Đã bắt đầu chuyển đổi hàng loạt!", "info", 2500);
                startConvertBatchPolling();
            } catch (err) {
                showToast("Lỗi: " + err, "error");
                btnBatchStart.disabled = false;
                btnBatchStop.disabled = true;
            }
        });
    }

    // Khử rác hàng loạt thư mục mà không đổi văn phong
    const btnCleanBatchFolder = document.getElementById("btn-clean-batch-folder");
    if (btnCleanBatchFolder) {
        btnCleanBatchFolder.addEventListener("click", async () => {
            const inF = inputFolder.value.trim();
            if (!inF) {
                showToast("Vui lòng chọn thư mục chứa các file truyện cần khử rác!", "warning", 2500);
                return;
            }

            const outF = outputFolder.value.trim();
            const suffix = suffixInput.value.trim() || "_clean";

            btnBatchStart.disabled = true;
            btnCleanBatchFolder.disabled = true;
            btnBatchStop.disabled = false;

            try {
                const res = await ServiceBridge.cleanFolder(inF, outF, suffix);
                if (res.error) {
                    showToast("Lỗi: " + res.error, "error");
                    btnBatchStart.disabled = false;
                    btnCleanBatchFolder.disabled = false;
                    btnBatchStop.disabled = true;
                    return;
                }
                showToast("Đã bắt đầu làm sạch và khử rác toàn bộ thư mục!", "info", 2500);
                startCleanFolderPolling();
            } catch (err) {
                showToast("Lỗi: " + err, "error");
                btnBatchStart.disabled = false;
                btnCleanBatchFolder.disabled = false;
                btnBatchStop.disabled = true;
            }
        });
    }

    if (btnBatchStop) {
        btnBatchStop.addEventListener("click", async () => {
            await ServiceBridge.stopBatchConvert();
            await ServiceBridge.stopCleanFolder();
            btnBatchStop.disabled = true;
            showToast("Đã gửi tín hiệu dừng tiến trình!", "warning", 2500);
        });
    }
}

let cleanFolderInterval = null;

function startCleanFolderPolling() {
    if (cleanFolderInterval) clearInterval(cleanFolderInterval);

    const statusText = document.getElementById("convert-progress-status");
    const pctBadge = document.getElementById("convert-progress-pct");
    const progressBar = document.getElementById("convert-progress-bar");
    const logContent = document.getElementById("convert-log-content");
    const btnStart = document.getElementById("btn-convert-batch-start");
    const btnCleanFolder = document.getElementById("btn-clean-batch-folder");
    const btnStop = document.getElementById("btn-convert-batch-stop");

    cleanFolderInterval = setInterval(async () => {
        try {
            const state = await ServiceBridge.getCleanFolderStatus();
            if (state) {
                if (statusText) statusText.textContent = state.status_msg || "Đang khử rác...";
                const pct = Math.round(state.progress || 0);
                if (pctBadge) pctBadge.textContent = `${pct}%`;
                if (progressBar) progressBar.style.width = `${pct}%`;

                if (logContent && state.logs && state.logs.length > 0) {
                    logContent.textContent = state.logs.slice(-50).join("\n");
                    logContent.scrollTop = logContent.scrollHeight;
                }

                if (!state.is_running) {
                    clearInterval(cleanFolderInterval);
                    if (btnStart) btnStart.disabled = false;
                    if (btnCleanFolder) btnCleanFolder.disabled = false;
                    if (btnStop) btnStop.disabled = true;
                    if (pct >= 100) {
                        showToast("Đã hoàn tất khử rác (c·hết ➔ chết, b·ạo đ·ộng ➔ bạo động) cho toàn bộ thư mục!", "success", 4000);
                    }
                }
            }
        } catch (e) {
            console.error("Lỗi polling clean folder:", e);
        }
    }, 700);
}

function startConvertBatchPolling() {
    if (convertBatchInterval) clearInterval(convertBatchInterval);

    const statusText = document.getElementById("convert-progress-status");
    const pctBadge = document.getElementById("convert-progress-pct");
    const progressBar = document.getElementById("convert-progress-bar");
    const logContent = document.getElementById("convert-log-content");
    const btnStart = document.getElementById("btn-convert-batch-start");
    const btnCleanFolder = document.getElementById("btn-clean-batch-folder");
    const btnStop = document.getElementById("btn-convert-batch-stop");

    convertBatchInterval = setInterval(async () => {
        try {
            const state = await ServiceBridge.getBatchConvertStatus();
            if (state) {
                if (statusText) statusText.textContent = state.status_msg || "Đang xử lý...";
                const pct = Math.round(state.progress || 0);
                if (pctBadge) pctBadge.textContent = `${pct}%`;
                if (progressBar) progressBar.style.width = `${pct}%`;

                if (logContent && state.logs && state.logs.length > 0) {
                    logContent.textContent = state.logs.slice(-50).join("\n");
                    logContent.scrollTop = logContent.scrollHeight;
                }

                if (!state.is_running) {
                    clearInterval(convertBatchInterval);
                    if (btnStart) btnStart.disabled = false;
                    if (btnCleanFolder) btnCleanFolder.disabled = false;
                    if (btnStop) btnStop.disabled = true;
                    if (pct >= 100) {
                        showToast("Đã hoàn tất chuyển đổi toàn bộ thư mục sang truyện dịch!", "success", 4000);
                    }
                }
            }
        } catch (e) {
            console.error("Lỗi polling convert batch:", e);
        }
    }, 700);
}

// ==========================================
// TAB 3: CÀO TRUYỆN (SCRAPER)
// ==========================================
let scraperInterval = null;

const PRESETS = {
    "sangtacviet.app": {
        title_selector: "h1, .chapter-title",
        content_selector: "#maincontent, .contentbox",
        exclude_selector: "",
        next_selector: "",
        toc_selector: "",
        sample_url: "https://sangtacviet.app/truyen/fanqie/1/7678671315934383166/",
        auto_translate: true
    },
    "fanqienovel.com": {
        title_selector: "h1, .chapter-title",
        content_selector: ".muye-reader-content",
        exclude_selector: "",
        next_selector: "",
        toc_selector: "",
        sample_url: "https://fanqienovel.com/page/7069948840148732967",
        auto_translate: true
    },
    "tvtruyen.live": {
        title_selector: "a.chapter-title, .chapter-title, h1",
        content_selector: "#chapter-content, div.chapter-content",
        exclude_selector: ".signature, .ads, .highlight-box, ins.adsbygoogle",
        next_selector: "#next_chap, a#next_chap, a.chapter-modal-next",
        toc_selector: "#list-chapter a, a[href*='chuong-']",
        sample_url: "https://www.tvtruyen.live/tien-vo-de-ton-dich.html",
        auto_translate: false
    },
    "truyenhoan.com": {
        title_selector: "a.chapter-title, .chapter-title, h1",
        content_selector: "#chapter-c, div.chapter-c",
        exclude_selector: ".ads, .highlight-box, .list-tags, ins.adsbygoogle",
        next_selector: "#next_chap, a#next_chap",
        toc_selector: "#list-chapter a, .list-chapter a, a[href*='chuong-']",
        sample_url: "https://truyenhoan.com/tien-nghich/chuong-1.html",
        auto_translate: false
    },
    "ihuliwang.net": {
        title_selector: "div.pt-read-title > h1, h1",
        content_selector: "div.pt-read-text, div.size16.color5.pt-read-text",
        exclude_selector: ".pt-read-text p:last-child",
        next_selector: "a.pt-nextchapter",
        toc_selector: ".pt-chapter-cont a, .pt-dir-list a",
        sample_url: "https://www.ihuliwang.net/1582_1582589/read/2049.html",
        auto_translate: true
    },
    "69shu.me": {
        title_selector: "div.txtnav > h1, h1",
        content_selector: "div.txtnav, #content",
        exclude_selector: ".bottom-ad, .read-nav",
        next_selector: "a:contains('下一章'), a.next, #next_url",
        toc_selector: ".catalog a, #catalog a, .mulu a",
        sample_url: "https://www.69shu.me/",
        auto_translate: true
    },
    "biquge": {
        title_selector: ".bookname > h1, h1",
        content_selector: "#content",
        exclude_selector: "p.read_btn, .bottem",
        next_selector: "a:contains('下一章'), #next_url, .bottem2 a:last-child",
        toc_selector: "#list dd a, #list a",
        sample_url: "https://www.xbiquge.la/",
        auto_translate: true
    },
    "uukanshu": {
        title_selector: "h1#timu, h1",
        content_selector: "div#contentbox, .readcotent",
        exclude_selector: ".ad_content",
        next_selector: "a#next, a:contains('下一章')",
        toc_selector: "#chapterList a, .chapter-list a",
        sample_url: "https://www.uukanshu.com/",
        auto_translate: true
    }
};

function initScraper() {
    const presetSelect = document.getElementById("scraper-preset-select");
    const urlInput = document.getElementById("scraper-url");
    const titleSelInput = document.getElementById("scraper-title-sel");
    const contentSelInput = document.getElementById("scraper-content-sel");
    const excludeSelInput = document.getElementById("scraper-exclude-sel");
    const nextSelInput = document.getElementById("scraper-next-sel");
    const tocSelInput = document.getElementById("scraper-toc-sel");
    const btnScanToc = document.getElementById("btn-scan-toc");
    const modeSelect = document.getElementById("scraper-mode");
    const concurrencyInput = document.getElementById("scraper-concurrency");
    const resumeCheckbox = document.getElementById("scraper-resume");
    const saveFolderInput = document.getElementById("scraper-save-folder");
    const btnSelectFolder = document.getElementById("btn-select-scraper-folder");
    const maxChaptersInput = document.getElementById("scraper-max-chapters");
    const waitMinInput = document.getElementById("scraper-wait-min");
    const waitMaxInput = document.getElementById("scraper-wait-max");
    const autoTranslateCheckbox = document.getElementById("scraper-auto-translate");
    const btnTest = document.getElementById("btn-test-scraper");
    const btnStart = document.getElementById("btn-start-scraper");
    const btnStop = document.getElementById("btn-stop-scraper");
    const testPreview = document.getElementById("scraper-test-preview");
    const previewTitle = document.getElementById("preview-title");
    const previewNext = document.getElementById("preview-next");
    const previewContent = document.getElementById("preview-content");
    const statusText = document.getElementById("scraper-status-text");
    const countBadge = document.getElementById("scraper-count-badge");
    const logContent = document.getElementById("scraper-log-content");

    // Thành phần đóng gói xuất truyện
    const exportFolderInput = document.getElementById("export-folder");
    const exportTitleInput = document.getElementById("export-title");
    const exportAuthorInput = document.getElementById("export-author");
    const btnSelectExportFolder = document.getElementById("btn-select-export-folder");
    const btnMergeTxt = document.getElementById("btn-merge-txt");
    const btnExportEpub = document.getElementById("btn-export-epub");

    // Thay đổi Preset
    presetSelect.addEventListener("change", () => {
        const key = presetSelect.value;
        if (PRESETS[key]) {
            titleSelInput.value = PRESETS[key].title_selector;
            contentSelInput.value = PRESETS[key].content_selector;
            excludeSelInput.value = PRESETS[key].exclude_selector;
            nextSelInput.value = PRESETS[key].next_selector;
            if (tocSelInput && PRESETS[key].toc_selector) {
                tocSelInput.value = PRESETS[key].toc_selector;
            }
            if (PRESETS[key].sample_url) {
                urlInput.value = PRESETS[key].sample_url;
            }
            if (PRESETS[key].auto_translate !== undefined) {
                autoTranslateCheckbox.checked = PRESETS[key].auto_translate;
            }
            showToast(`Đã áp dụng mẫu cấu hình: ${key}`, "info", 2000);
        }
    });

    // Quét mục lục chương (TOC)
    if (btnScanToc) {
        btnScanToc.addEventListener("click", async () => {
            const url = urlInput.value.trim();
            if (!url) {
                showToast("Vui lòng nhập link trang truyện hoặc mục lục!", "warning");
                return;
            }
            btnScanToc.disabled = true;
            btnScanToc.innerHTML = "⏳ Đang quét...";
            try {
                const res = await ServiceBridge.scanToc(url, tocSelInput.value.trim());
                if (res && res.count > 0) {
                    showToast(`Quét thành công! Tìm thấy ${res.count} chương trong mục lục.`, "success", 4000);
                    logContent.textContent = `[Mục lục] Đã tìm thấy ${res.count} chương:\n` +
                        res.chapters.slice(0, 15).map(c => `#${c.index}. ${c.title}`).join("\n") +
                        (res.count > 15 ? `\n... và ${res.count - 15} chương nữa.` : "");
                } else {
                    showToast("Không tìm thấy chương nào với selector mục lục này.", "warning", 3500);
                }
            } catch (e) {
                showToast("Lỗi khi quét mục lục: " + e, "error");
            } finally {
                btnScanToc.disabled = false;
                btnScanToc.innerHTML = "📋 Quét danh sách chương";
            }
        });
    }

    // Chọn thư mục lưu cào
    btnSelectFolder.addEventListener("click", async () => {
        const selected = await ServiceBridge.selectFolder();
        if (selected) {
            saveFolderInput.value = selected;
            if (exportFolderInput && !exportFolderInput.value) {
                exportFolderInput.value = selected;
            }
            showToast("Đã chọn thư mục lưu truyện", "info", 2000);
        }
    });

    // Thử cào 1 chương
    btnTest.addEventListener("click", async () => {
        const url = urlInput.value.trim();
        if (!url) {
            showToast("Vui lòng nhập link chương cần thử nghiệm!", "warning");
            return;
        }

        btnTest.disabled = true;
        btnTest.innerHTML = "⏳ Đang thử...";

        try {
            const res = await ServiceBridge.testScrapeChapter(
                url,
                titleSelInput.value.trim(),
                contentSelInput.value.trim(),
                excludeSelInput.value.trim(),
                nextSelInput.value.trim()
            );

            if (res && res.success) {
                testPreview.style.display = "block";
                previewTitle.textContent = `📖 ${res.title}`;
                previewNext.textContent = res.next_url ? `➔ Tiếp theo: ${res.next_url}` : "(Không có link tiếp theo)";
                previewContent.textContent = res.content_preview || "(Không tìm thấy nội dung)";
                if (exportTitleInput && !exportTitleInput.value) {
                    exportTitleInput.value = res.title.split("/")[0].replace(/^#\d+\.\s*/, '').trim();
                }
                showToast(`Cào thử thành công: ${res.title} (${res.content_length} ký tự)`, "success", 3500);
            } else {
                showToast("Lỗi cào thử: " + (res.error || "Không lấy được nội dung"), "error", 4000);
            }
        } catch (e) {
            showToast("Lỗi kết nối khi cào thử: " + e, "error");
        } finally {
            btnTest.disabled = false;
            btnTest.innerHTML = "🔍 Thử cào 1 chương";
        }
    });

    // Bắt đầu cào truyện
    btnStart.addEventListener("click", async () => {
        const url = urlInput.value.trim();
        if (!url) {
            showToast("Vui lòng nhập link chương hoặc trang truyện!", "warning");
            return;
        }

        const config = {
            url: url,
            save_folder: saveFolderInput.value.trim(),
            title_selector: titleSelInput.value.trim(),
            content_selector: contentSelInput.value.trim(),
            exclude_selector: excludeSelInput.value.trim(),
            next_selector: nextSelInput.value.trim(),
            wait_min: parseFloat(waitMinInput.value) || 0.5,
            wait_max: parseFloat(waitMaxInput.value) || 1.5,
            max_chapters: parseInt(maxChaptersInput.value) || 0,
            auto_translate: autoTranslateCheckbox.checked,
            model: document.getElementById("quick-model-select") ? document.getElementById("quick-model-select").value : "DanVP/MoxhiMT-60 (Đỉnh Cao Tiên Hiệp - Văn phong đỉnh cao)",
            beam_size: 2,
            batch_size: 16,
            opencc: true,
            mode: modeSelect ? modeSelect.value : "sequential",
            concurrency: concurrencyInput ? (parseInt(concurrencyInput.value) || 4) : 4,
            resume: resumeCheckbox ? resumeCheckbox.checked : true,
            toc_selector: tocSelInput ? tocSelInput.value.trim() : ""
        };

        btnStart.disabled = true;
        btnStop.disabled = false;

        try {
            await ServiceBridge.startScraper(config);
            const modeName = config.mode === "toc" ? "Đa luồng TOC" : "Tuần tự Next";
            showToast(`Bắt đầu cào (${modeName} - ${config.concurrency} luồng)!`, "info", 3000);
            startScraperPolling();
        } catch (err) {
            showToast("Lỗi khởi chạy cào truyện: " + err, "error");
            btnStart.disabled = false;
            btnStop.disabled = true;
        }
    });

    // Dừng cào
    btnStop.addEventListener("click", async () => {
        await ServiceBridge.stopScraper();
        btnStop.disabled = true;
        showToast("Đã gửi tín hiệu dừng cào truyện!", "warning", 2500);
    });

    // --- ĐÓNG GÓI & XUẤT TRUYỆN ---
    if (btnSelectExportFolder) {
        btnSelectExportFolder.addEventListener("click", async () => {
            const selected = await ServiceBridge.selectFolder();
            if (selected) {
                exportFolderInput.value = selected;
                showToast("Đã chọn thư mục cần đóng gói", "info", 2000);
            }
        });
    }

    if (btnMergeTxt) {
        btnMergeTxt.addEventListener("click", async () => {
            const folder = exportFolderInput.value.trim() || saveFolderInput.value.trim();
            if (!folder) {
                showToast("Vui lòng chọn thư mục chứa các chương cần gộp!", "warning");
                return;
            }
            const title = exportTitleInput.value.trim() || "Bộ Truyện";
            const author = exportAuthorInput.value.trim() || "Khuyết Danh";

            btnMergeTxt.disabled = true;
            btnMergeTxt.innerHTML = "⏳ Đang gộp...";
            try {
                const res = await ServiceBridge.mergeTxt(folder, title, author);
                if (res && res.success) {
                    showToast(`✅ Gộp thành công ${res.total_chapters} chương thành file: ${res.filename} (${res.size_kb} KB)`, "success", 4500);
                } else {
                    showToast("Lỗi khi gộp file: " + (res.error || "Không rõ lỗi"), "error", 4000);
                }
            } catch (e) {
                showToast("Lỗi: " + e, "error");
            } finally {
                btnMergeTxt.disabled = false;
                btnMergeTxt.innerHTML = "<span>📑</span> Gộp 1 File TXT Duy Nhất";
            }
        });
    }

    if (btnExportEpub) {
        btnExportEpub.addEventListener("click", async () => {
            const folder = exportFolderInput.value.trim() || saveFolderInput.value.trim();
            if (!folder) {
                showToast("Vui lòng chọn thư mục chứa các chương cần xuất EPUB!", "warning");
                return;
            }
            const title = exportTitleInput.value.trim() || "Bộ Truyện";
            const author = exportAuthorInput.value.trim() || "Khuyết Danh";

            btnExportEpub.disabled = true;
            btnExportEpub.innerHTML = "⏳ Đang đóng gói...";
            try {
                const res = await ServiceBridge.exportEpub(folder, title, author);
                if (res && res.success) {
                    showToast(`📱 Đã tạo thành công sách EPUB: ${res.filename} (${res.total_chapters} chương, ${res.size_kb} KB)! Sẵn sàng mở trên Apple Books.`, "success", 5000);
                } else {
                    showToast("Lỗi khi tạo EPUB: " + (res.error || "Không rõ lỗi"), "error", 4000);
                }
            } catch (e) {
                showToast("Lỗi xuất EPUB: " + e, "error");
            } finally {
                btnExportEpub.disabled = false;
                btnExportEpub.innerHTML = "<span>📱</span> Xuất Sách EPUB Tiêu Chuẩn";
            }
        });
    }
}

function startScraperPolling() {
    if (scraperInterval) clearInterval(scraperInterval);

    const statusText = document.getElementById("scraper-status-text");
    const countBadge = document.getElementById("scraper-count-badge");
    const logContent = document.getElementById("scraper-log-content");
    const btnStart = document.getElementById("btn-start-scraper");
    const btnStop = document.getElementById("btn-stop-scraper");

    scraperInterval = setInterval(async () => {
        try {
            const state = await ServiceBridge.getScraperStatus();
            if (state) {
                statusText.textContent = state.status_msg || "Đang cào...";
                countBadge.textContent = `${state.total_scraped || 0} chương`;

                if (state.logs && state.logs.length > 0) {
                    logContent.textContent = state.logs.slice(-50).join("\n");
                    logContent.scrollTop = logContent.scrollHeight;
                }

                if (!state.is_running) {
                    clearInterval(scraperInterval);
                    btnStart.disabled = false;
                    btnStop.disabled = true;
                    showToast(`Tiến trình cào truyện kết thúc. Tổng cộng: ${state.total_scraped || 0} chương!`, "success", 4000);
                }
            }
        } catch (e) {
            console.error("Lỗi polling scraper:", e);
        }
    }, 700);
}

// ==========================================
// TAB: SÁCH NÓI AUDIO (TTS)
// ==========================================
let batchTtsInterval = null;

function initTts() {
    const ttsInput = document.getElementById("tts-input-text");
    const voiceSelect = document.getElementById("tts-voice-select");
    const speedSelect = document.getElementById("tts-speed-select");
    const normalizeCheck = document.getElementById("tts-normalize-check");
    const btnSpeak = document.getElementById("btn-tts-speak-now");
    const btnDownload = document.getElementById("btn-tts-download-now");
    const statusText = document.getElementById("tts-player-status");
    const audioContainer = document.getElementById("tts-audio-container");
    const audioPlayer = document.getElementById("tts-audio-player");
    const audioFilename = document.getElementById("tts-audio-filename");
    const audioDuration = document.getElementById("tts-audio-duration");

    const batchVoiceSelect = document.getElementById("batch-tts-voice-select");
    const batchSpeedSelect = document.getElementById("batch-tts-speed-select");
    const batchNormalizeCheck = document.getElementById("batch-tts-normalize-check");

    const btnPreviewSample = document.getElementById("btn-tts-preview-sample");
    const btnBatchPreviewSample = document.getElementById("btn-batch-tts-preview-sample");
    const samplePreviewPlayer = document.getElementById("tts-sample-preview-player");

    const btnPaste = document.getElementById("btn-tts-paste");
    const btnFromTrans = document.getElementById("btn-tts-from-trans");
    const btnClear = document.getElementById("btn-tts-clear");
    const btnListenTgt = document.getElementById("btn-listen-tgt");

    // Tự động tải danh sách 80+ giọng clone và chia theo nhóm nhân vật
    async function populateVoiceOptions() {
        try {
            const res = await ServiceBridge.getCloneVoices();
            if (!res || !res.voices || res.voices.length === 0) return;

            // Xóa các optgroup clone cũ nếu đã tồn tại để tránh trùng lặp
            [voiceSelect, batchVoiceSelect].forEach(sel => {
                if (!sel) return;
                sel.querySelectorAll('optgroup[data-type="clone"]').forEach(g => g.remove());
            });

            const categories = {};
            res.voices.forEach(v => {
                const cat = v.category || "🎙️ Giọng Khác";
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(v);
            });

            const priorityOrder = [
                "🗡️ Tiên Hiệp & Kiếm Hiệp",
                "👻 Truyện Ma & Triết Lý",
                "🎬 Lồng Tiếng & Người Nổi Tiếng",
                "📱 Review, CapCut & MXH",
                "🎙️ Giọng Audio Chuyên Nghiệp (Nam)",
                "🎙️ Giọng Audio Chuyên Nghiệp (Nữ)"
            ];

            const sortedCats = Object.keys(categories).sort((a, b) => {
                const ia = priorityOrder.indexOf(a);
                const ib = priorityOrder.indexOf(b);
                if (ia !== -1 && ib !== -1) return ia - ib;
                if (ia !== -1) return -1;
                if (ib !== -1) return 1;
                return a.localeCompare(b);
            });

            const fragment = document.createDocumentFragment();
            sortedCats.forEach(cat => {
                const grp = document.createElement("optgroup");
                grp.label = cat;
                grp.setAttribute('data-type', 'clone');
                categories[cat].forEach(v => {
                    const opt = document.createElement("option");
                    opt.value = `clone:${v.id}`;
                    opt.textContent = `${v.name} (${v.gender === "male" ? "Nam" : "Nữ"})`;
                    grp.appendChild(opt);
                });
                fragment.appendChild(grp);
            });

            if (voiceSelect) {
                voiceSelect.appendChild(fragment.cloneNode(true));
            }
            if (batchVoiceSelect) {
                batchVoiceSelect.appendChild(fragment.cloneNode(true));
            }
        } catch (e) {
            console.error("Lỗi nạp kho giọng:", e);
        }
    }
    populateVoiceOptions();

    // Xử lý nghe thử đoạn audio mẫu của nhân vật
    function handlePlayVoiceSample(selectElem, btnElem) {
        if (!selectElem) return;
        const val = selectElem.value;

        if (samplePreviewPlayer && !samplePreviewPlayer.paused) {
            samplePreviewPlayer.pause();
            samplePreviewPlayer.currentTime = 0;
            if (btnPreviewSample) btnPreviewSample.innerHTML = "🎧 Nghe giọng mẫu";
            if (btnBatchPreviewSample) btnBatchPreviewSample.innerHTML = "🎧 Nghe giọng mẫu";
            return;
        }

        if (val.startsWith("clone:")) {
            const voiceId = val.substring(6);
            const audioUrl = ServiceBridge.getSampleAudioUrl(voiceId);
            if (samplePreviewPlayer) {
                samplePreviewPlayer.src = audioUrl;
                samplePreviewPlayer.load();
                samplePreviewPlayer.play().then(() => {
                    btnElem.innerHTML = "⏸️ Đang nghe...";
                    showToast(`🎵 Đang phát đoạn mẫu giọng: ${voiceId}`, "info", 2200);
                }).catch(err => {
                    showToast("Không thể phát mẫu audio: " + err, "error");
                });

                samplePreviewPlayer.onended = () => {
                    btnElem.innerHTML = "🎧 Nghe giọng mẫu";
                };
                samplePreviewPlayer.onpause = () => {
                    btnElem.innerHTML = "🎧 Nghe giọng mẫu";
                };
            }
        } else {
            showToast(`Đang tổng hợp giọng chuẩn ${val}...`, "info", 2000);
            btnElem.innerHTML = "⏳ Đang tạo...";
            ServiceBridge.speakTts("Xin chào quý thính giả, đây là bản thử giọng đọc truyện truyền cảm.", val, 1.0, true)
                .then(res => {
                    if (res && res.audio_url && samplePreviewPlayer) {
                        samplePreviewPlayer.src = res.audio_url;
                        samplePreviewPlayer.load();
                        samplePreviewPlayer.play();
                        btnElem.innerHTML = "⏸️ Đang nghe...";
                        samplePreviewPlayer.onended = () => {
                            btnElem.innerHTML = "🎧 Nghe giọng mẫu";
                        };
                        samplePreviewPlayer.onpause = () => {
                            btnElem.innerHTML = "🎧 Nghe giọng mẫu";
                        };
                    } else {
                        btnElem.innerHTML = "🎧 Nghe giọng mẫu";
                    }
                })
                .catch(e => {
                    showToast("Lỗi nghe thử giọng: " + e, "error");
                    btnElem.innerHTML = "🎧 Nghe giọng mẫu";
                });
        }
    }

    if (btnPreviewSample) {
        btnPreviewSample.addEventListener("click", () => handlePlayVoiceSample(voiceSelect, btnPreviewSample));
    }
    if (btnBatchPreviewSample) {
        btnBatchPreviewSample.addEventListener("click", () => handlePlayVoiceSample(batchVoiceSelect, btnBatchPreviewSample));
    }

    // Dán clipboard
    if (btnPaste) {
        btnPaste.addEventListener("click", async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    ttsInput.value = text;
                    showToast("Đã dán văn bản từ clipboard!", "info", 1800);
                } else {
                    showToast("Clipboard đang trống!", "warning", 1800);
                }
            } catch (e) {
                showToast("Không thể đọc clipboard: " + e, "error");
            }
        });
    }

    // Lấy từ bản dịch
    if (btnFromTrans) {
        btnFromTrans.addEventListener("click", () => {
            const tgt = document.getElementById("tgt-text");
            if (tgt && tgt.value.trim()) {
                ttsInput.value = tgt.value.trim();
                showToast("Đã nạp văn bản từ bản dịch tiếng Việt!", "success", 2000);
            } else {
                showToast("Chưa có nội dung dịch bên Tab 1!", "warning", 2000);
            }
        });
    }

    // Nút nghe bản dịch ngay trên Tab 1
    if (btnListenTgt) {
        btnListenTgt.addEventListener("click", () => {
            const tgt = document.getElementById("tgt-text");
            if (!tgt || !tgt.value.trim()) {
                showToast("Chưa có bản dịch nào để đọc!", "warning", 2000);
                return;
            }
            ttsInput.value = tgt.value.trim();
            // Chuyển sang Tab TTS
            const ttsTabBtn = document.querySelector('.nav-item[data-tab="tab-tts"]');
            if (ttsTabBtn) ttsTabBtn.click();
            // Tự động bấm đọc
            setTimeout(() => {
                if (btnSpeak) btnSpeak.click();
            }, 300);
        });
    }

    // Xóa văn bản
    if (btnClear) {
        btnClear.addEventListener("click", () => {
            ttsInput.value = "";
            if (audioPlayer) audioPlayer.pause();
            if (audioContainer) audioContainer.style.display = "none";
            if (btnDownload) btnDownload.style.display = "none";
            if (statusText) statusText.textContent = "";
            showToast("Đã xóa nội dung", "info", 1500);
        });
    }

    // Đọc thử / Tạo Audio
    if (btnSpeak) {
        btnSpeak.addEventListener("click", async () => {
            const text = ttsInput.value.trim();
            if (!text) {
                showToast("Vui lòng nhập hoặc dán nội dung cần đọc!", "warning");
                return;
            }

            btnSpeak.disabled = true;
            btnSpeak.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-label">Đang tạo âm thanh...</span>';
            if (statusText) statusText.textContent = "Đang tổng hợp giọng nói Neural...";

            try {
                const voice = voiceSelect ? voiceSelect.value : "vi-VN-NamMinhNeural";
                const speed = speedSelect ? (parseFloat(speedSelect.value) || 1.0) : 1.0;
                const normalize = normalizeCheck ? normalizeCheck.checked : true;

                const res = await ServiceBridge.speakTts(
                    text,
                    voice,
                    speed,
                    normalize,
                    (pct, cur, total, msg) => {
                        if (statusText) {
                            statusText.textContent = `⏳ ${msg || "Đang tạo âm thanh..."} (${pct}%)`;
                        }
                        btnSpeak.innerHTML = `<span class="btn-icon">⏳</span><span class="btn-label">Đang đọc: ${pct}%</span>`;
                    }
                );
                if (res && res.success && res.audio_url) {
                    if (audioContainer) audioContainer.style.display = "block";
                    if (audioPlayer) {
                        audioPlayer.src = res.audio_url;
                        audioPlayer.load();
                        audioPlayer.play().catch(e => console.log("Auto-play prevented:", e));
                    }
                    if (audioFilename) audioFilename.textContent = res.filename;
                    if (btnDownload) {
                        btnDownload.href = res.audio_url;
                        btnDownload.style.display = "inline-flex";
                    }
                    if (statusText) statusText.textContent = "✅ Đã tạo âm thanh thành công!";

                    if (audioPlayer) {
                        audioPlayer.onloadedmetadata = () => {
                            const m = Math.floor(audioPlayer.duration / 60);
                            const s = Math.floor(audioPlayer.duration % 60);
                            if (audioDuration) audioDuration.textContent = `${m}:${s < 10 ? '0' : ''}${s}`;
                        };
                    }
                    showToast("Đã tạo âm thanh thành công! Đang phát...", "success", 2500);
                } else {
                    let err = (res && res.error) ? res.error : "Không thể tạo file audio";
                    if (err.includes("Load failed") || err.includes("Failed to fetch")) {
                        err = "Không thể kết nối đến TTS Service (vui lòng thử lại sau vài giây)";
                    }
                    if (statusText) statusText.textContent = "❌ " + err;
                    showToast("Lỗi tạo audio: " + err, "error", 4000);
                }
            } catch (err) {
                let msg = String(err);
                if (msg.includes("Load failed") || msg.includes("Failed to fetch")) {
                    msg = "Không thể kết nối đến TTS Service (vui lòng thử lại sau vài giây)";
                }
                if (statusText) statusText.textContent = "❌ " + msg;
                showToast("Lỗi kết nối TTS Service: " + msg, "error", 4000);
            } finally {
                btnSpeak.disabled = false;
                btnSpeak.innerHTML = '<span class="btn-icon">▶️</span><span class="btn-label">Bắt Đầu Đọc / Tạo Audio</span><div class="btn-shimmer"></div>';
            }
        });
    }

    // BATCH AUDIOBOOK CONTROLS
    const batchInputFolder = document.getElementById("batch-tts-input-folder");
    const batchOutputFolder = document.getElementById("batch-tts-output-folder");
    const btnSelectBatchInput = document.getElementById("btn-select-batch-tts-input");
    const btnSelectBatchOutput = document.getElementById("btn-select-batch-tts-output");
    const btnBatchScan = document.getElementById("btn-batch-tts-scan");
    const btnBatchStart = document.getElementById("btn-batch-tts-start");
    const btnBatchStop = document.getElementById("btn-batch-tts-stop");
    const batchStatusText = document.getElementById("batch-tts-status-text");
    const batchPercentage = document.getElementById("batch-tts-percentage");
    const batchProgressBar = document.getElementById("batch-tts-progress-bar");
    const batchLogContent = document.getElementById("batch-tts-log-content");

    if (btnSelectBatchInput) {
        btnSelectBatchInput.addEventListener("click", async () => {
            const folder = await ServiceBridge.selectFolder();
            if (folder) batchInputFolder.value = folder;
        });
    }

    if (btnSelectBatchOutput) {
        btnSelectBatchOutput.addEventListener("click", async () => {
            const folder = await ServiceBridge.selectFolder();
            if (folder) batchOutputFolder.value = folder;
        });
    }

    if (btnBatchScan) {
        btnBatchScan.addEventListener("click", async () => {
            const folder = batchInputFolder.value.trim();
            if (!folder) {
                showToast("Vui lòng chọn thư mục nguồn cần quét!", "warning");
                return;
            }
            try {
                const res = await ServiceBridge.checkFolder(folder);
                if (res && res.count !== undefined) {
                    showToast(`Tìm thấy ${res.count} file .txt trong thư mục!`, "info", 3000);
                    if (batchStatusText) batchStatusText.textContent = `Tìm thấy ${res.count} chương truyện .txt`;
                } else if (res && res.error) {
                    showToast("Lỗi: " + res.error, "error");
                }
            } catch (e) {
                showToast("Lỗi quét thư mục: " + e, "error");
            }
        });
    }

    if (btnBatchStart) {
        btnBatchStart.addEventListener("click", async () => {
            const inF = batchInputFolder.value.trim();
            if (!inF) {
                showToast("Vui lòng chọn thư mục chứa các file .txt chương truyện!", "warning");
                return;
            }
            const outF = batchOutputFolder.value.trim();
            const voice = batchVoiceSelect ? batchVoiceSelect.value : "vi-VN-NamMinhNeural";
            const speed = batchSpeedSelect ? (parseFloat(batchSpeedSelect.value) || 1.0) : 1.0;
            const normalize = batchNormalizeCheck ? batchNormalizeCheck.checked : true;

            btnBatchStart.disabled = true;
            btnBatchStop.disabled = false;

            try {
                const res = await ServiceBridge.startBatchTts(inF, outF, voice, speed, normalize);
                if (res && res.success) {
                    showToast("Đã khởi động tiến trình tạo Audiobook hàng loạt!", "success", 2500);
                    startBatchTtsPolling();
                } else {
                    showToast("Lỗi khởi chạy: " + ((res && res.error) || "Không xác định"), "error");
                    btnBatchStart.disabled = false;
                    btnBatchStop.disabled = true;
                }
            } catch (e) {
                showToast("Lỗi kết nối: " + e, "error");
                btnBatchStart.disabled = false;
                btnBatchStop.disabled = true;
            }
        });
    }

    if (btnBatchStop) {
        btnBatchStop.addEventListener("click", async () => {
            try {
                await ServiceBridge.stopBatchTts();
                showToast("Đã gửi yêu cầu dừng tạo Audiobook!", "warning");
            } catch (e) {
                showToast("Lỗi: " + e, "error");
            }
        });
    }

    function startBatchTtsPolling() {
        if (batchTtsInterval) clearInterval(batchTtsInterval);
        batchTtsInterval = setInterval(async () => {
            try {
                const st = await ServiceBridge.getBatchTtsStatus();
                if (!st) return;

                if (batchStatusText) batchStatusText.textContent = st.status_msg || "Đang xử lý...";
                const pct = st.progress || 0;
                if (batchPercentage) batchPercentage.textContent = `${pct}%`;
                if (batchProgressBar) batchProgressBar.style.width = `${pct}%`;

                if (st.logs && st.logs.length > 0 && batchLogContent) {
                    batchLogContent.textContent = st.logs.join("\n");
                    batchLogContent.scrollTop = batchLogContent.scrollHeight;
                }

                if (!st.is_running) {
                    clearInterval(batchTtsInterval);
                    batchTtsInterval = null;
                    if (btnBatchStart) btnBatchStart.disabled = false;
                    if (btnBatchStop) btnBatchStop.disabled = true;
                    if (pct >= 100) {
                        showToast("🎉 Hoàn tất tạo toàn bộ Audiobook MP3!", "success", 4000);
                    }
                }
            } catch (e) {
                console.error("Lỗi polling batch TTS:", e);
            }
        }, 600);
    }
}

// ==========================================
// TAB 4: QUẢN LÝ TỪ ĐIỂN
// ==========================================
function initDictionary() {
    const dictArea = document.getElementById("dict-content-area");
    const btnReload = document.getElementById("btn-reload-dict");
    const btnSave = document.getElementById("btn-save-dict");
    const btnAdd = document.getElementById("btn-add-dict-entry");
    const srcInput = document.getElementById("dict-src-input");
    const tgtInput = document.getElementById("dict-tgt-input");

    async function loadDict() {
        try {
            const res = await ServiceBridge.getDictionary();
            if (res && res.content !== undefined) {
                dictArea.value = res.content;
            }
        } catch (e) {
            console.error("Lỗi nạp từ điển:", e);
        }
    }

    btnReload.addEventListener("click", async () => {
        await loadDict();
        showToast("Đã tải lại danh sách từ điển", "info", 1800);
    });

    btnSave.addEventListener("click", async () => {
        try {
            const res = await ServiceBridge.saveDictionary(dictArea.value);
            if (res && res.status === "saved") {
                btnSave.textContent = "✅ Đã lưu";
                showToast("Đã lưu từ điển names.txt thành công!", "success", 2500);
                setTimeout(() => btnSave.textContent = "💾 Lưu thay đổi", 1800);
            }
        } catch (e) {
            showToast("Lỗi lưu từ điển: " + e, "error");
        }
    });

    btnAdd.addEventListener("click", async () => {
        const src = srcInput.value.trim();
        const tgt = tgtInput.value.trim();
        if (!src || !tgt) {
            showToast("Vui lòng nhập cả từ gốc và từ dịch tiếng Việt!", "warning");
            return;
        }

        try {
            const res = await ServiceBridge.addDictEntry(src, tgt);
            if (res && res.content) {
                dictArea.value = res.content;
                srcInput.value = "";
                tgtInput.value = "";
                showToast(`Đã thêm "${src} = ${tgt}" vào từ điển!`, "success", 2500);
            }
        } catch (e) {
            showToast("Lỗi thêm từ điển: " + e, "error");
        }
    });

    loadDict();
}

// ==========================================
// TAB: STUDIO BIÊN TẬP SONG NGỮ
// ==========================================
function initBilingualStudio() {
    const btnSync = document.getElementById("btn-bilingual-sync-from-text");
    const btnRealign = document.getElementById("btn-bilingual-realign");
    const btnSave = document.getElementById("btn-bilingual-save");
    const btnCopy = document.getElementById("btn-bilingual-copy");
    const searchInput = document.getElementById("bilingual-quick-search");
    const btnLookup = document.getElementById("btn-bilingual-lookup");
    const lookupResult = document.getElementById("bilingual-lookup-result");
    const btnAddName = document.getElementById("btn-bilingual-add-name");
    const rowsContainer = document.getElementById("bilingual-rows");
    const statsLabel = document.getElementById("bilingual-stats");

    let currentPairs = [];

    window.loadBilingualStudio = async function(src, tgt) {
        if (!src && !tgt) {
            const s = document.getElementById("src-text") ? document.getElementById("src-text").value : "";
            const t = document.getElementById("tgt-text") ? document.getElementById("tgt-text").value : "";
            src = s;
            tgt = t;
        }

        if (!src.trim() && !tgt.trim()) {
            showToast("Vui lòng có ít nhất văn bản tiếng Trung hoặc bản dịch để nạp vào Studio!", "warning");
            return;
        }

        rowsContainer.innerHTML = '<div style="padding: 40px; text-align: center; color: var(--neon-cyan);">⏳ Đang phân tích và đối chiếu từng câu/đoạn song ngữ...</div>';

        try {
            const res = await ServiceBridge.alignBilingual(src, tgt);
            if (res && res.pairs) {
                currentPairs = res.pairs;
                renderRows(res.pairs);
                showToast(`Đã căn chỉnh thành công ${res.pairs.length} đoạn văn song ngữ!`, "success");
            } else {
                showToast("Lỗi căn chỉnh song ngữ", "error");
            }
        } catch (e) {
            showToast("Lỗi kết nối Studio: " + e, "error");
        }
    };

    function renderRows(pairs) {
        if (!pairs || pairs.length === 0) {
            rowsContainer.innerHTML = `
                <div class="bilingual-empty-state">
                    <span class="empty-icon">📑</span>
                    <h4>Chưa có dữ liệu biên tập</h4>
                    <p>Dán văn bản ở tab "Dịch văn bản" rồi bấm <strong>"📑 Mở Studio"</strong></p>
                </div>
            `;
            statsLabel.textContent = "0 đoạn văn";
            return;
        }

        statsLabel.textContent = `${pairs.length} đoạn văn`;
        rowsContainer.innerHTML = "";

        pairs.forEach((p, idx) => {
            const row = document.createElement("div");
            row.className = "bilingual-row";
            row.id = `bilingual-row-${idx}`;

            row.innerHTML = `
                <div class="bilingual-cell bilingual-cell-zh" title="Bôi đen hoặc click đúp để tra Hán-Việt">${escapeHtml(p.src || "")}</div>
                <div class="bilingual-cell bilingual-cell-hv">${escapeHtml(p.hanviet || "")}</div>
                <div class="bilingual-cell bilingual-cell-vi">
                    <textarea class="bilingual-edit-input" data-index="${idx}">${escapeHtml(p.tgt || "")}</textarea>
                </div>
            `;

            const zhCell = row.querySelector(".bilingual-cell-zh");
            zhCell.addEventListener("mouseup", () => {
                const sel = window.getSelection().toString().trim();
                if (sel && sel.length <= 10) {
                    searchInput.value = sel;
                    doLookup(sel);
                }
            });

            const editInput = row.querySelector(".bilingual-edit-input");
            editInput.addEventListener("input", (e) => {
                if (currentPairs[idx]) {
                    currentPairs[idx].tgt = e.target.value;
                }
            });

            rowsContainer.appendChild(row);
        });
    }

    async function doLookup(text) {
        if (!text) return;
        try {
            const res = await ServiceBridge.lookupGlossary(text);
            if (res && res.hanviet) {
                lookupResult.textContent = `${res.term} ➔ ${res.hanviet}`;
                lookupResult.style.display = "inline-block";
                btnAddName.style.display = "inline-block";
                btnAddName.onclick = async () => {
                    await ServiceBridge.batchAddGlossary([{ src: res.term, tgt: res.hanviet }]);
                    showToast(`Đã thêm "${res.term} = ${res.hanviet}" vào names.txt!`, "success");
                    btnAddName.style.display = "none";
                    const dictArea = document.getElementById("dict-content-area");
                    if (dictArea) {
                        const dRes = await ServiceBridge.getDictionary();
                        if (dRes && dRes.content) dictArea.value = dRes.content;
                    }
                };
            }
        } catch (e) {
            console.error(e);
        }
    }

    if (btnLookup) {
        btnLookup.addEventListener("click", () => {
            const val = searchInput.value.trim();
            if (val) doLookup(val);
        });
    }

    if (btnSync) {
        btnSync.addEventListener("click", () => {
            window.loadBilingualStudio();
        });
    }

    if (btnRealign) {
        btnRealign.addEventListener("click", () => {
            const srcAll = currentPairs.map(p => p.src).join("\n\n");
            const tgtAll = currentPairs.map(p => p.tgt).join("\n\n");
            window.loadBilingualStudio(srcAll, tgtAll);
        });
    }

    if (btnCopy) {
        btnCopy.addEventListener("click", async () => {
            const fullTgt = currentPairs.map(p => p.tgt).join("\n\n");
            if (!fullTgt.trim()) {
                showToast("Bản dịch đang rỗng!", "warning");
                return;
            }
            try {
                await navigator.clipboard.writeText(fullTgt);
                showToast("Đã sao chép toàn bộ bản dịch đã biên tập!", "success");
            } catch (e) {
                showToast("Lỗi sao chép: " + e, "error");
            }
        });
    }

    if (btnSave) {
        btnSave.addEventListener("click", () => {
            const fullTgt = currentPairs.map(p => p.tgt).join("\n\n");
            if (!fullTgt.trim()) {
                showToast("Bản dịch đang rỗng!", "warning");
                return;
            }
            const blob = new Blob([fullTgt], { type: "text/plain;charset=utf-8" });
            const fname = `chuong_dich_${Date.now()}.txt`;
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = fname;
            a.click();
            showToast("Đã tải xuống file bản dịch đã biên tập!", "success");
        });
    }
}

// ==========================================
// TÍNH NĂNG: TRÍCH XUẤT TÊN RIÊNG AI (AUTO-GLOSSARY)
// ==========================================
function initAutoGlossary() {
    const inputArea = document.getElementById("glossary-input-text");
    const methodSelect = document.getElementById("glossary-method-select");
    const btnFromTab = document.getElementById("btn-glossary-from-tab");
    const btnScan = document.getElementById("btn-glossary-scan");
    const resultsBox = document.getElementById("glossary-results-box");
    const countLabel = document.getElementById("glossary-count-label");
    const checkAll = document.getElementById("glossary-check-all");
    const btnSelectAll = document.getElementById("btn-glossary-select-all");
    const btnBatchAdd = document.getElementById("btn-glossary-batch-add");
    const tableBody = document.getElementById("glossary-table-body");

    let currentEntities = [];

    if (btnFromTab) {
        btnFromTab.addEventListener("click", () => {
            const src = document.getElementById("src-text") ? document.getElementById("src-text").value : "";
            if (src.trim()) {
                inputArea.value = src;
                showToast("Đã nạp văn bản từ tab Dịch!", "info");
            } else {
                showToast("Tab Dịch đang trống!", "warning");
            }
        });
    }

    window.triggerQuickScanFromText = function(text) {
        if (!text) return;
        inputArea.value = text;
        switchTab("tab-dict");
        setTimeout(() => {
            runScan();
        }, 250);
    };

    async function runScan() {
        const text = inputArea.value.trim();
        if (!text) {
            showToast("Vui lòng dán văn bản tiếng Trung cần quét!", "warning");
            return;
        }

        btnScan.disabled = true;
        btnScan.innerHTML = '<span>⏳</span><span>Đang quét...</span>';

        const method = methodSelect ? methodSelect.value : "auto";
        try {
            const res = await ServiceBridge.extractGlossary(text, method);
            if (res && res.entities) {
                currentEntities = res.entities;
                renderGlossaryTable(res.entities);
                resultsBox.style.display = "block";
                countLabel.textContent = `Đã tìm thấy: ${res.entities.length} thực thể`;
                showToast(`Đã quét xong! Tìm thấy ${res.entities.length} thực thể riêng biệt.`, "success");
            } else {
                showToast("Không tìm thấy thực thể mới hoặc có lỗi.", "info");
            }
        } catch (e) {
            showToast("Lỗi quét tên riêng: " + e, "error");
        } finally {
            btnScan.disabled = false;
            btnScan.innerHTML = '<span>🔍</span><span>Quét Tên Riêng Ngay</span>';
        }
    }

    if (btnScan) {
        btnScan.addEventListener("click", runScan);
    }

    function renderGlossaryTable(entities) {
        tableBody.innerHTML = "";
        if (!entities || entities.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--text-muted);">Không tìm thấy thực thể mới (có thể các từ đã có sẵn trong names.txt).</td></tr>';
            return;
        }

        entities.forEach((ent, idx) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td style="text-align: center; padding: 6px;"><input type="checkbox" class="glossary-item-check" data-index="${idx}" checked/></td>
                <td style="padding: 6px; font-weight: 700; color: #f1f5f9;">${escapeHtml(ent.src)}</td>
                <td style="padding: 6px;"><input type="text" class="glossary-edit-tgt" data-index="${idx}" value="${escapeHtml(ent.tgt)}"/></td>
                <td style="padding: 6px;"><span class="glossary-cat-badge">${escapeHtml(ent.category || "Chung")}</span></td>
                <td style="text-align: center; padding: 6px; color: #94a3b8;">${ent.count || 1}</td>
                <td style="text-align: center; padding: 6px;">
                    <button class="btn-tool ripple btn-add-single-entity" data-index="${idx}" title="Thêm từ này vào từ điển" style="color: #f59e0b; padding: 2px 8px; font-size: 11px;">➕ Thêm</button>
                </td>
            `;

            const editTgt = tr.querySelector(".glossary-edit-tgt");
            editTgt.addEventListener("input", (e) => {
                if (currentEntities[idx]) currentEntities[idx].tgt = e.target.value.trim();
            });

            const btnAddSingle = tr.querySelector(".btn-add-single-entity");
            btnAddSingle.addEventListener("click", async () => {
                const targetEntry = currentEntities[idx];
                if (targetEntry) {
                    await ServiceBridge.batchAddGlossary([targetEntry]);
                    showToast(`Đã thêm "${targetEntry.src} = ${targetEntry.tgt}" vào Names!`, "success");
                    btnAddSingle.textContent = "✓ Đã thêm";
                    btnAddSingle.disabled = true;
                    const dictArea = document.getElementById("dict-content-area");
                    if (dictArea) {
                        const dRes = await ServiceBridge.getDictionary();
                        if (dRes && dRes.content) dictArea.value = dRes.content;
                    }
                }
            });

            tableBody.appendChild(tr);
        });
    }

    if (checkAll) {
        checkAll.addEventListener("change", (e) => {
            const checkboxes = document.querySelectorAll(".glossary-item-check");
            checkboxes.forEach(cb => cb.checked = e.target.checked);
        });
    }

    if (btnSelectAll) {
        btnSelectAll.addEventListener("click", () => {
            const checkboxes = document.querySelectorAll(".glossary-item-check");
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => cb.checked = !allChecked);
            if (checkAll) checkAll.checked = !allChecked;
        });
    }

    if (btnBatchAdd) {
        btnBatchAdd.addEventListener("click", async () => {
            const checkedBoxes = document.querySelectorAll(".glossary-item-check:checked");
            if (checkedBoxes.length === 0) {
                showToast("Vui lòng tích chọn ít nhất 1 thực thể cần thêm!", "warning");
                return;
            }

            const toAdd = [];
            checkedBoxes.forEach(cb => {
                const idx = parseInt(cb.getAttribute("data-index"));
                if (currentEntities[idx]) {
                    toAdd.push({
                        src: currentEntities[idx].src,
                        tgt: currentEntities[idx].tgt
                    });
                }
            });

            btnBatchAdd.disabled = true;
            try {
                const res = await ServiceBridge.batchAddGlossary(toAdd);
                if (res && res.success) {
                    showToast(`Đã thêm thành công ${res.added} thực thể mới vào names.txt!`, "success", 3000);
                    const dictArea = document.getElementById("dict-content-area");
                    if (dictArea) {
                        const dRes = await ServiceBridge.getDictionary();
                        if (dRes && dRes.content) dictArea.value = dRes.content;
                    }
                    checkedBoxes.forEach(cb => {
                        cb.checked = false;
                        cb.disabled = true;
                        const tr = cb.closest("tr");
                        if (tr) tr.style.opacity = "0.5";
                    });
                } else {
                    showToast("Lỗi khi thêm vào từ điển!", "error");
                }
            } catch (e) {
                showToast("Lỗi: " + e, "error");
            } finally {
                btnBatchAdd.disabled = false;
            }
        });
    }
}

// ==========================================
// TAB 4: CÀI ĐẶT & MÔ HÌNH
// ==========================================
let modelsLoaded = false;

async function initSettings() {
    const modelContainer = document.getElementById("model-cards-container");
    const quickSelect = document.getElementById("quick-model-select");
    const batchSelect = document.getElementById("batch-model-select");
    const geminiInput = document.getElementById("setting-gemini-key");
    const deepseekInput = document.getElementById("setting-deepseek-key");
    const geminiStatus = document.getElementById("gemini-key-status");
    const deepseekStatus = document.getElementById("deepseek-key-status");
    const btnSaveGemini = document.getElementById("btn-save-gemini-key");
    const btnSaveDeepseek = document.getElementById("btn-save-deepseek-key");

    // Tải cấu hình API Keys
    async function loadApiSettings() {
        try {
            const cfg = await ServiceBridge.getSettings();
            if (cfg) {
                if (geminiStatus) {
                    if (cfg.has_gemini_key) {
                        geminiStatus.textContent = `✅ Đã lưu (${cfg.gemini_masked})`;
                        geminiStatus.style.color = "var(--neon-green)";
                    } else {
                        geminiStatus.textContent = "Chưa cấu hình API Key";
                        geminiStatus.style.color = "var(--neon-amber)";
                    }
                }
                if (deepseekStatus) {
                    if (cfg.has_deepseek_key) {
                        deepseekStatus.textContent = `✅ Đã lưu (${cfg.deepseek_masked})`;
                        deepseekStatus.style.color = "var(--neon-green)";
                    } else {
                        deepseekStatus.textContent = "Chưa cấu hình API Key";
                        deepseekStatus.style.color = "var(--neon-amber)";
                    }
                }
            }
        } catch (e) {
            console.error("Lỗi nạp settings:", e);
        }
    }

    if (btnSaveGemini) {
        btnSaveGemini.addEventListener("click", async () => {
            const key = geminiInput.value.trim();
            if (!key) {
                showToast("Vui lòng nhập Gemini API Key!", "warning");
                return;
            }
            btnSaveGemini.disabled = true;
            try {
                const res = await ServiceBridge.saveSettings({ gemini_api_key: key });
                if (res && res.success) {
                    showToast("Đã lưu Google Gemini API Key!", "success", 2500);
                    geminiInput.value = "";
                    await loadApiSettings();
                } else {
                    showToast("Lỗi khi lưu key", "error");
                }
            } catch (e) {
                showToast("Lỗi lưu Gemini key: " + e, "error");
            } finally {
                btnSaveGemini.disabled = false;
            }
        });
    }

    if (btnSaveDeepseek) {
        btnSaveDeepseek.addEventListener("click", async () => {
            const key = deepseekInput.value.trim();
            if (!key) {
                showToast("Vui lòng nhập DeepSeek API Key!", "warning");
                return;
            }
            btnSaveDeepseek.disabled = true;
            try {
                const res = await ServiceBridge.saveSettings({ deepseek_api_key: key });
                if (res && res.success) {
                    showToast("Đã lưu DeepSeek API Key!", "success", 2500);
                    deepseekInput.value = "";
                    await loadApiSettings();
                } else {
                    showToast("Lỗi khi lưu key", "error");
                }
            } catch (e) {
                showToast("Lỗi lưu DeepSeek key: " + e, "error");
            } finally {
                btnSaveDeepseek.disabled = false;
            }
        });
    }

    await loadApiSettings();

    try {
        const res = await ServiceBridge.getModels();
        if (res && res.models && res.models.length > 0) {
            quickSelect.innerHTML = "";
            batchSelect.innerHTML = "";
            modelContainer.innerHTML = "";

            res.models.forEach(m => {
                const opt1 = document.createElement("option");
                opt1.value = m.name;
                opt1.textContent = m.name;
                quickSelect.appendChild(opt1);

                const opt2 = document.createElement("option");
                opt2.value = m.name;
                opt2.textContent = m.name;
                batchSelect.appendChild(opt2);

                const card = document.createElement("div");
                card.className = "model-item";
                const isLlm = m.type === "llm";
                const badgeText = isLlm ? "🌐 Cloud AI (Online)" : (m.downloaded ? "✓ Sẵn sàng (Offline)" : "Cần tải");
                const badgeClass = isLlm ? "badge-neon" : "badge-success";
                card.innerHTML = `
                    <div class="model-title">${isLlm ? "🧠" : "📦"} ${m.name}</div>
                    <span class="${badgeClass}">${badgeText}</span>
                `;
                modelContainer.appendChild(card);
            });
            modelsLoaded = true;
        }
    } catch (e) {
        console.error("Lỗi lấy models:", e);
    }
}

// ==========================================
// MONITOR SỨC KHỎE KẾT NỐI (HEALTH HUD)
// ==========================================
function startHealthMonitor() {
    const statusText = document.getElementById("global-status");
    const statusModel = document.getElementById("global-model");
    const statusDot = document.querySelector(".status-dot");
    const rings = document.querySelectorAll(".status-ring, .status-ring-2");

    async function check() {
        try {
            const health = await ServiceBridge.checkHealth();
            if (health.ok) {
                statusText.textContent = "AI CORE: SẴN SÀNG";
                statusText.style.color = "var(--neon-green)";
                statusText.style.textShadow = "0 0 10px rgba(16, 185, 129, 0.6)";
                statusDot.style.backgroundColor = "var(--neon-green)";
                statusDot.style.boxShadow = "0 0 10px var(--neon-green)";
                rings.forEach(r => r.style.borderColor = "var(--neon-green)");
                
                if (health.data && health.data.model) {
                    statusModel.textContent = health.data.model.split("/").pop();
                } else {
                    statusModel.textContent = "CTranslate2 int8";
                }

                // Nếu chưa nạp được models, nạp ngay khi service sẵn sàng
                if (!modelsLoaded) {
                    initSettings();
                    const dictArea = document.getElementById("dict-content-area");
                    if (!dictArea.value) {
                        const dictRes = await ServiceBridge.getDictionary();
                        if (dictRes && dictRes.content) dictArea.value = dictRes.content;
                    }
                }
            } else {
                setConnectingState();
            }
        } catch (e) {
            setConnectingState();
        }
    }

    function setConnectingState() {
        statusText.textContent = "AI CORE: ĐANG KẾT NỐI...";
        statusText.style.color = "var(--neon-amber)";
        statusText.style.textShadow = "0 0 8px rgba(245, 158, 11, 0.5)";
        statusDot.style.backgroundColor = "var(--neon-amber)";
        statusDot.style.boxShadow = "0 0 10px var(--neon-amber)";
        rings.forEach(r => r.style.borderColor = "var(--neon-amber)");
    }

    check();
    setInterval(check, 1800);
}
