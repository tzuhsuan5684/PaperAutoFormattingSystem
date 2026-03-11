/**
 * Week 5-7 — Overleaf Content Script
 * 注入至 overleaf.com/project/* 頁面：
 * 1. 監聽 CodeMirror 編輯器的游標變動
 * 2. 使用者停止打字 500ms 後觸發補全
 * 3. 在游標位置顯示灰色補全建議
 * 4. Tab 鍵接受補全，Esc 鍵取消
 */

const EXT_PREFIX = "[IEEE-EXT]";
let config = {};
let debounceTimer = null;
let currentSuggestion = null;
let isWaiting = false;

// ── 初始化 ─────────────────────────────────────────────────────────────────────
async function init() {
  config = await chrome.runtime.sendMessage({ type: "GET_CONFIG" });
  if (!config.enabled) {
    console.log(`${EXT_PREFIX} 已停用`);
    return;
  }

  console.log(`${EXT_PREFIX} 初始化完成，API: ${config.apiUrl}`);
  waitForEditor();
}

// ── 等待 Overleaf CodeMirror 編輯器載入 ────────────────────────────────────────
function waitForEditor() {
  const observer = new MutationObserver(() => {
    const editor = findCodeMirrorEditor();
    if (editor) {
      observer.disconnect();
      attachToEditor(editor);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // 立即檢查一次
  const editor = findCodeMirrorEditor();
  if (editor) {
    observer.disconnect();
    attachToEditor(editor);
  }
}

function findCodeMirrorEditor() {
  // Overleaf 使用 CodeMirror 6，編輯器容器 selector
  return (
    document.querySelector(".cm-editor .cm-content") ||
    document.querySelector(".CodeMirror-code")
  );
}

// ── 附加至編輯器 ───────────────────────────────────────────────────────────────
function attachToEditor(editorEl) {
  console.log(`${EXT_PREFIX} 已找到 Overleaf 編輯器，掛載補全功能`);

  // 注入補全提示 CSS
  injectStyles();

  // 監聽鍵盤事件（在 editorEl 的父容器）
  const container = editorEl.closest(".cm-editor") || editorEl.parentElement;

  container.addEventListener("keydown", onKeyDown, true);
  container.addEventListener("input", onInput, { passive: true });
}

// ── 鍵盤事件 ───────────────────────────────────────────────────────────────────
function onKeyDown(e) {
  if (e.key === "Tab" && currentSuggestion) {
    e.preventDefault();
    e.stopPropagation();
    acceptSuggestion();
    return;
  }
  if (e.key === "Escape" && currentSuggestion) {
    clearSuggestion();
    return;
  }
}

function onInput() {
  clearSuggestion();
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(triggerCompletion, config.triggerDelay || 500);
}

// ── 補全觸發 ───────────────────────────────────────────────────────────────────
async function triggerCompletion() {
  if (isWaiting) return;
  const prefix = getTextBeforeCursor();
  if (!prefix || prefix.length < 20) return;

  isWaiting = true;
  showLoadingIndicator();

  const result = await chrome.runtime.sendMessage({
    type: "COMPLETE",
    payload: { prefix: prefix.slice(-800) },  // 最後 800 字元
  });

  isWaiting = false;
  hideLoadingIndicator();

  if (result.error || !result.completion) return;

  // 延遲警告
  if (result.latency > 800) {
    console.warn(`${EXT_PREFIX} 延遲 ${result.latency}ms 超過目標 800ms`);
  }

  showSuggestion(result.completion, result.latency);
}

// ── 取得游標前文字 ─────────────────────────────────────────────────────────────
function getTextBeforeCursor() {
  // CodeMirror 6 方式
  try {
    const cmEditor = document.querySelector(".cm-editor");
    if (cmEditor && cmEditor.cmView) {
      const view = cmEditor.cmView.view;
      const state = view.state;
      const pos = state.selection.main.head;
      return state.sliceDoc(0, pos);
    }
  } catch {}

  // Fallback：使用 Selection API
  const sel = window.getSelection();
  if (!sel || !sel.anchorNode) return "";
  const range = document.createRange();
  range.setStart(sel.anchorNode.parentElement, 0);
  range.setEnd(sel.anchorNode, sel.anchorOffset);
  return range.toString();
}

// ── 補全顯示 ──────────────────────────────────────────────────────────────────
function showSuggestion(text, latency) {
  clearSuggestion();

  const hint = document.createElement("span");
  hint.className = "ieee-completion-hint";
  hint.textContent = text;
  hint.title = `IEEE LaTeX 補全（${latency}ms）｜Tab 接受，Esc 取消`;

  // 插入至游標後方
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return;

  const range = sel.getRangeAt(0).cloneRange();
  range.collapse(false);
  range.insertNode(hint);

  currentSuggestion = { element: hint, text };
}

function clearSuggestion() {
  if (currentSuggestion?.element) {
    currentSuggestion.element.remove();
  }
  currentSuggestion = null;
}

function acceptSuggestion() {
  if (!currentSuggestion) return;
  const { element, text } = currentSuggestion;

  // 將建議文字插入實際編輯器（使用 document.execCommand 保持撤銷歷史）
  element.remove();
  currentSuggestion = null;
  document.execCommand("insertText", false, text);
}

// ── Loading 指示器 ─────────────────────────────────────────────────────────────
function showLoadingIndicator() {
  const existing = document.getElementById("ieee-loading");
  if (existing) return;
  const indicator = document.createElement("div");
  indicator.id = "ieee-loading";
  indicator.innerHTML = `<span>IEEE</span> ···`;
  document.body.appendChild(indicator);
}

function hideLoadingIndicator() {
  document.getElementById("ieee-loading")?.remove();
}

// ── 注入 CSS ──────────────────────────────────────────────────────────────────
function injectStyles() {
  if (document.getElementById("ieee-ext-styles")) return;
  const style = document.createElement("style");
  style.id = "ieee-ext-styles";
  style.textContent = `
    .ieee-completion-hint {
      color: #999;
      font-style: italic;
      pointer-events: none;
      user-select: none;
      white-space: pre;
    }
    #ieee-loading {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #1a73e8;
      color: white;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      z-index: 99999;
      font-family: monospace;
      opacity: 0.85;
    }
  `;
  document.head.appendChild(style);
}

// ── 啟動 ──────────────────────────────────────────────────────────────────────
init();
