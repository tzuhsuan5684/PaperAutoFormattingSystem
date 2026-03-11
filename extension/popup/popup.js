/**
 * Chrome Extension Popup 控制邏輯
 */

// ── DOM 元素 ───────────────────────────────────────────────────────────────────
const statusBadge   = document.getElementById("status-badge");
const enableToggle  = document.getElementById("enabled-toggle");
const inputText     = document.getElementById("input-text");
const formatBtn     = document.getElementById("format-btn");
const formatStatus  = document.getElementById("format-status");
const outputSection = document.getElementById("output-section");
const latexOutput   = document.getElementById("latex-output");
const copyBtn       = document.getElementById("copy-btn");
const apiUrlInput   = document.getElementById("api-url");
const triggerDelay  = document.getElementById("trigger-delay");
const delayValue    = document.getElementById("trigger-delay-value");
const saveBtn       = document.getElementById("save-btn");
const testBtn       = document.getElementById("test-btn");
const settingsStatus = document.getElementById("settings-status");


// ── 初始化 ─────────────────────────────────────────────────────────────────────
async function init() {
  const config = await chrome.runtime.sendMessage({ type: "GET_CONFIG" });

  enableToggle.checked = config.enabled;
  apiUrlInput.value    = config.apiUrl;
  triggerDelay.value   = config.triggerDelay;
  delayValue.textContent = `${config.triggerDelay}ms`;

  // 非同步檢查 API 狀態
  checkApiStatus(config.apiUrl);
}

async function checkApiStatus(apiUrl) {
  statusBadge.textContent = "檢查中...";
  statusBadge.className = "badge badge-checking";

  const result = await chrome.runtime.sendMessage({
    type: "HEALTH_CHECK",
    apiUrl,
  });

  if (result.ok) {
    statusBadge.textContent = `✓ 已連線`;
    statusBadge.className = "badge badge-ok";
  } else {
    statusBadge.textContent = "✗ 未連線";
    statusBadge.className = "badge badge-error";
  }
}


// ── 格式化功能 ─────────────────────────────────────────────────────────────────
formatBtn.addEventListener("click", async () => {
  const text = inputText.value.trim();
  if (!text) {
    setStatus(formatStatus, "請輸入文字大綱", "error");
    return;
  }

  formatBtn.disabled = true;
  formatBtn.textContent = "處理中...";
  setStatus(formatStatus, "呼叫推理服務...", "");

  const result = await chrome.runtime.sendMessage({
    type: "FORMAT",
    payload: { text },
  });

  formatBtn.disabled = false;
  formatBtn.textContent = "✨ 生成 IEEE LaTeX";

  if (result.error) {
    setStatus(formatStatus, `❌ ${result.error}`, "error");
    outputSection.style.display = "none";
  } else {
    setStatus(formatStatus, `✓ 完成（${result.latency}ms）`, "success");
    latexOutput.textContent = result.latex;
    outputSection.style.display = "block";
  }
});


// ── 複製 LaTeX ─────────────────────────────────────────────────────────────────
copyBtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(latexOutput.textContent);
    copyBtn.textContent = "✓ 已複製！";
    setTimeout(() => { copyBtn.textContent = "📋 複製 LaTeX"; }, 1500);
  } catch {
    copyBtn.textContent = "複製失敗";
  }
});


// ── 設定儲存 ───────────────────────────────────────────────────────────────────
saveBtn.addEventListener("click", async () => {
  const newConfig = {
    enabled: enableToggle.checked,
    apiUrl: apiUrlInput.value.trim() || "http://localhost:8000",
    triggerDelay: parseInt(triggerDelay.value),
  };
  await chrome.storage.sync.set(newConfig);
  setStatus(settingsStatus, "✓ 設定已儲存", "success");
  setTimeout(() => setStatus(settingsStatus, "", ""), 2000);
});

testBtn.addEventListener("click", () => {
  const url = apiUrlInput.value.trim() || "http://localhost:8000";
  setStatus(settingsStatus, "測試中...", "");
  checkApiStatus(url).then(() => {
    const ok = statusBadge.className.includes("ok");
    setStatus(settingsStatus, ok ? "✓ 連線成功" : "✗ 無法連線", ok ? "success" : "error");
  });
});

enableToggle.addEventListener("change", async () => {
  await chrome.storage.sync.set({ enabled: enableToggle.checked });
});

triggerDelay.addEventListener("input", () => {
  delayValue.textContent = `${triggerDelay.value}ms`;
});


// ── 工具函式 ───────────────────────────────────────────────────────────────────
function setStatus(el, msg, type) {
  el.textContent = msg;
  el.className = `status-msg ${type}`;
}


// ── 啟動 ──────────────────────────────────────────────────────────────────────
init();
