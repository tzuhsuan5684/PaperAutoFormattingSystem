/**
 * Week 5 — Chrome Extension Background Service Worker (MV3)
 * 負責：
 * 1. 與 FastAPI 推理服務通訊
 * 2. 管理設定（API URL、延遲閾值）
 * 3. 接收 content.js 的補全請求並回傳結果
 */

const DEFAULT_CONFIG = {
  apiUrl: "http://localhost:8000",
  maxTokens: 128,
  temperature: 0.05,
  triggerDelay: 500,      // ms：使用者停止打字後觸發補全
  enabled: true,
};

// ── 初始化預設設定 ─────────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.sync.get(Object.keys(DEFAULT_CONFIG));
  const toSet = {};
  for (const [key, val] of Object.entries(DEFAULT_CONFIG)) {
    if (existing[key] === undefined) toSet[key] = val;
  }
  if (Object.keys(toSet).length > 0) {
    await chrome.storage.sync.set(toSet);
  }
  console.log("[IEEE-EXT] 擴充功能已安裝/更新，設定初始化完成");
});


// ── 訊息處理 ───────────────────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "COMPLETE") {
    handleCompletion(message.payload).then(sendResponse);
    return true;  // 非同步回應
  }

  if (message.type === "FORMAT") {
    handleFormat(message.payload).then(sendResponse);
    return true;
  }

  if (message.type === "GET_CONFIG") {
    chrome.storage.sync.get(Object.keys(DEFAULT_CONFIG)).then(sendResponse);
    return true;
  }

  if (message.type === "HEALTH_CHECK") {
    checkApiHealth(message.apiUrl).then(sendResponse);
    return true;
  }
});


// ── API 呼叫函式 ────────────────────────────────────────────────────────────────
async function getConfig() {
  return chrome.storage.sync.get(Object.keys(DEFAULT_CONFIG));
}

async function handleCompletion({ prefix }) {
  const config = await getConfig();
  if (!config.enabled) return { error: "擴充功能已停用" };

  const startTime = performance.now();
  try {
    const response = await fetch(`${config.apiUrl}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prefix,
        max_tokens: config.maxTokens,
      }),
      signal: AbortSignal.timeout(2000),  // 2s 超時
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const latency = performance.now() - startTime;

    console.log(`[IEEE-EXT] 補全完成，延遲: ${latency.toFixed(0)}ms`);
    return {
      completion: data.completion,
      latency: Math.round(latency),
    };
  } catch (err) {
    console.warn("[IEEE-EXT] 補全失敗:", err.message);
    return { error: err.message };
  }
}

async function handleFormat({ text, instruction }) {
  const config = await getConfig();
  const startTime = performance.now();

  try {
    const response = await fetch(`${config.apiUrl}/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        instruction: instruction || null,
        max_tokens: 1024,
        temperature: config.temperature,
      }),
      signal: AbortSignal.timeout(30000),  // 30s 超時（格式化較慢）
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return { latex: data.latex, latency: Math.round(performance.now() - startTime) };
  } catch (err) {
    return { error: err.message };
  }
}

async function checkApiHealth(apiUrl) {
  try {
    const response = await fetch(`${apiUrl}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return { ok: false };
    const data = await response.json();
    return { ok: true, ...data };
  } catch {
    return { ok: false, error: "無法連線" };
  }
}
