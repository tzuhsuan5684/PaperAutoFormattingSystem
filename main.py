"""
FastAPI 入口：論文格式自動修正服務。
"""
import io
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any

from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from formatter.checker import FormatIssue, ThesisChecker
from formatter.corrector import ThesisCorrector
from formatter.exporter import save_docx
from formatter.loader import load_config

app = FastAPI(
    title="論文格式自動修正服務",
    description="上傳 .docx，系統自動依照學校格式規則修正並輸出修正後的 .docx。",
    version="1.0.0",
)

# ── In-memory token store ────────────────────────────────────────────────────
# { token: {"path": str, "expires_at": float} }
_TOKEN_STORE: dict[str, dict[str, Any]] = {}
_TOKEN_TTL   = 30 * 60  # 30 分鐘（秒）

checker   = ThesisChecker()
corrector = ThesisCorrector()


def _cleanup_expired_tokens() -> None:
    now     = time.time()
    expired = [t for t, v in _TOKEN_STORE.items() if v["expires_at"] < now]
    for t in expired:
        path = Path(_TOKEN_STORE[t]["path"])
        if path.exists():
            path.unlink(missing_ok=True)
        del _TOKEN_STORE[t]


def _issue_to_dict(issue: FormatIssue) -> dict:
    return {
        "severity":   issue.severity,
        "section":    issue.section,
        "message":    issue.message,
        "auto_fixed": issue.auto_fixed,
    }


# ── POST /format ─────────────────────────────────────────────────────────────
@app.post("/format")
async def format_thesis(
    file:      UploadFile = File(..., description=".docx 論文檔案"),
    school_id: str        = Form(..., description="學校代碼，例如 ncu"),
):
    """
    上傳 .docx 論文檔案，執行格式檢查與自動修正。

    回傳：
    - `issues_before`：修正前的問題清單
    - `issues_after`：修正後的剩餘問題清單
    - `download_token`：用於下載修正後 .docx 的憑證（30 分鐘有效）
    """
    _cleanup_expired_tokens()

    # 驗證副檔名
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="只接受 .docx 格式的檔案。")

    # 載入學校設定
    try:
        config = load_config(school_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # 讀取上傳檔案
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="上傳的檔案是空的。")

    try:
        doc = Document(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="無法解析 .docx 檔案，請確認檔案格式正確。")

    # 修正前檢查
    issues_before = checker.check_all(doc, config)

    # 執行格式修正
    doc = corrector.run_all(doc, config)

    # 修正後檢查
    issues_after = checker.check_all(doc, config)

    # 儲存修正後檔案到暫存目錄
    tmp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".docx",
        prefix="thesis_formatted_",
    )
    tmp_path = tmp_file.name
    tmp_file.close()
    save_docx(doc, tmp_path)

    # 建立下載 token
    token = secrets.token_urlsafe(32)
    _TOKEN_STORE[token] = {
        "path":       tmp_path,
        "filename":   f"formatted_{filename}",
        "expires_at": time.time() + _TOKEN_TTL,
    }

    return JSONResponse({
        "issues_before":  [_issue_to_dict(i) for i in issues_before],
        "issues_after":   [_issue_to_dict(i) for i in issues_after],
        "download_token": token,
        "message":        "格式修正完成，請使用 download_token 下載修正後的檔案。",
    })


# ── GET /download/{token} ────────────────────────────────────────────────────
@app.get("/download/{token}")
def download_formatted(token: str):
    """下載修正後的 .docx 檔案（憑證有效期 30 分鐘）。"""
    _cleanup_expired_tokens()

    entry = _TOKEN_STORE.get(token)
    if entry is None:
        raise HTTPException(status_code=404, detail="下載憑證無效或已過期，請重新上傳檔案。")

    path = Path(entry["path"])
    if not path.exists():
        raise HTTPException(status_code=500, detail="修正後的檔案已遺失，請重新上傳。")

    return FileResponse(
        path        = str(path),
        filename    = entry["filename"],
        media_type  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ── GET /schools ─────────────────────────────────────────────────────────────
@app.get("/schools")
def list_schools():
    """列出目前支援的學校清單。"""
    from formatter.loader import list_available_schools
    return {"schools": list_available_schools()}


# ── 啟動方式提示 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
