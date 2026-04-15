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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.staticfiles import StaticFiles

from formatter.checker import FormatIssue, ThesisChecker
from formatter.corrector import ThesisCorrector
from formatter.exporter import save_docx
from formatter.loader import load_config

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="論文格式自動修正服務",
    description="上傳 .docx，系統自動依照學校格式規則修正並輸出修正後的 .docx。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.post("/parse-format-pdf")
async def parse_format_pdf(file: UploadFile = File(...)):
    import google.genai as genai
    import google.genai.types as types
    import base64, os, json

    pdf_bytes = await file.read()
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = (
        "請扮演專業排版解析工程師。"
        "請先閱讀「目次序」確認論文應包含的項目，"
        "接著從我提供的附件中萃取各項目的排版規則，並嚴格輸出為指定的 JSON 格式。\n\n"
        "【任務要求】\n"
        "1. 僅輸出合法 JSON，嚴禁包含 Markdown 標記（如 ```json）、問候語或任何解釋文字。\n"
        "2. 尺寸須轉換為純數字型別（例如：「2.5公分」填 2.5）。\n"
        "3. 若內文提及附件，將附件號填入 \"attachment\"（例如：附件九）。\n"
        "4. 查無資訊的欄位一律填寫 null。\n\n"
        "【指定的 JSON 輸出格式】\n"
        "{\n"
        "  \"global_rules\": {\n"
        "    \"margins\": {\n"
        "      \"top\": \"頂端留邊公分數 (number)\",\n"
        "      \"bottom\": \"底端留邊公分數 (number)\",\n"
        "      \"left\": \"左側留邊公分數 (number)\",\n"
        "      \"right\": \"右側留邊公分數 (number)\"\n"
        "    }\n"
        "  },\n"
        "  \"thesis_sections\": [\n"
        "    {\n"
        "      \"section_name\": \"章節名稱 (string)\",\n"
        "      \"content_requirements\": [\n"
        "        \"該章節必須包含的資訊，例如：校名、論文題目等 (array of strings)\"\n"
        "      ],\n"
        "      \"specific_constraints\": [\n"
        "        \"該章節特有的排版或顏色限制，請拆解成一條一條的獨立規則 (array of strings)\"\n"
        "      ],\n"
        "      \"attachment\": \"對應的附件號碼 (string)\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                ),
                prompt
            ]
        )
    except genai.errors.APIError as e:
        raise HTTPException(status_code=503, detail=f"Gemini API Error: {e.message}")
    
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:-1])
    rules_display = json.loads(raw)
    return {"rules_display": rules_display}


# ── Serve frontend ────────────────────────────────────────────────────────────
_FRONTEND_DIR = Path(__file__).parent / "frontend"
if _FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


# ── 啟動方式提示 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
