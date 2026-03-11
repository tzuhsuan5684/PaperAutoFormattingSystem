"""
Week 3 — FastAPI 推理服務
OpenAI-compatible API，供 Gradio UI 與 Chrome Extension 呼叫。

啟動方式：
    # 方式 1: 直接啟動（HF 後端）
    python inference/server.py

    # 方式 2: 搭配 vLLM（生產環境，需 GPU）
    python -m vllm.entrypoints.openai.api_server \
        --model ./models/ieee-qwen2.5-1.5b-lora \
        --port 8001
    python inference/server.py --mode vllm

API 端點：
    POST /format       → 格式化 IEEE LaTeX（主要功能）
    POST /complete     → 即時補全（Chrome Extension 用）
    GET  /health       → 健康檢查
    GET  /docs         → Swagger UI
"""

import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(
    title="IEEE LaTeX Formatter API",
    description="基於 SLM 的 IEEE 論文自動排版服務",
    version="1.0.0",
)

# CORS（允許 Chrome Extension 跨域呼叫）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── 模型後端（延遲載入）───────────────────────────────────────────────────────
_backend = None
_backend_mode = os.getenv("BACKEND_MODE", "auto")


def get_backend():
    global _backend
    if _backend is None:
        from inference.model_loader import load_backend
        _backend = load_backend(_backend_mode)
    return _backend


# ── Request / Response 模型 ───────────────────────────────────────────────────
class FormatRequest(BaseModel):
    text: str = Field(..., description="待格式化的純文字或草稿 LaTeX", min_length=10)
    instruction: Optional[str] = Field(
        None, description="自訂指令（預設：IEEE LaTeX 格式化）"
    )
    max_tokens: int = Field(1024, ge=64, le=4096)
    temperature: float = Field(0.1, ge=0.0, le=1.0)


class FormatResponse(BaseModel):
    latex: str
    latency_ms: float
    model: str = "ieee-qwen2.5-1.5b"


class CompleteRequest(BaseModel):
    prefix: str = Field(..., description="游標前的 LaTeX 文字", min_length=5)
    max_tokens: int = Field(128, ge=16, le=512)


class CompleteResponse(BaseModel):
    completion: str
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    backend: str


# ── 端點 ──────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model_loaded=_backend is not None,
        backend=_backend_mode,
    )


@app.post("/format", response_model=FormatResponse)
async def format_latex(req: FormatRequest):
    """
    主要功能：將文字大綱轉換為 IEEE LaTeX。
    """
    from inference.model_loader import build_prompt, DEFAULT_INSTRUCTION

    instruction = req.instruction or DEFAULT_INSTRUCTION
    prompt = build_prompt(req.text, instruction=instruction)

    start = time.perf_counter()
    try:
        backend = get_backend()
        latex = backend.generate(
            prompt,
            max_new_tokens=req.max_tokens,
            temperature=req.temperature,
        )
    except Exception as e:
        logger.error(f"推理失敗: {e}")
        raise HTTPException(status_code=500, detail=f"模型推理失敗: {str(e)}")

    latency = (time.perf_counter() - start) * 1000
    logger.info(f"格式化完成，延遲: {latency:.0f}ms")

    return FormatResponse(latex=latex, latency_ms=round(latency, 1))


@app.post("/complete", response_model=CompleteResponse)
async def complete_latex(req: CompleteRequest):
    """
    即時補全：給定游標前的 LaTeX，預測後續內容。
    供 Chrome Extension 觸發（目標延遲 < 800ms）。
    """
    completion_instruction = (
        "根據以下 IEEE LaTeX 文字的前綴，補全後續的 LaTeX 程式碼，"
        "確保符合 IEEEtran 格式規範。"
    )
    from inference.model_loader import build_prompt

    prompt = build_prompt(req.prefix, instruction=completion_instruction)

    start = time.perf_counter()
    try:
        backend = get_backend()
        completion = backend.generate(
            prompt,
            max_new_tokens=req.max_tokens,
            temperature=0.05,  # 補全用更低溫度
        )
    except Exception as e:
        logger.error(f"補全失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    latency = (time.perf_counter() - start) * 1000
    return CompleteResponse(completion=completion, latency_ms=round(latency, 1))


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", 8000)))
    parser.add_argument("--mode", default="auto", choices=["auto", "vllm", "hf"])
    args = parser.parse_args()

    _backend_mode = args.mode
    logger.info(f"啟動 IEEE LaTeX API 服務 — {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
