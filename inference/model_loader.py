"""
推理服務 — 模型載入工具
支援兩種模式：
1. vLLM（GPU，生產環境，低延遲）
2. HuggingFace Transformers（CPU / 備援）
"""

import os
from pathlib import Path
from typing import Optional

from loguru import logger


MODEL_PATH = os.getenv("MODEL_PATH", "./models/ieee-qwen2.5-1.5b-lora")
BASE_MODEL = os.getenv("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")

# Prompt 模板（與訓練時一致）
ALPACA_SYSTEM = "You are an expert IEEE paper LaTeX formatter."
ALPACA_PROMPT = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{instruction}

### Input:
{input}

### Response:
"""

DEFAULT_INSTRUCTION = (
    "將以下學術論文段落轉換為符合 IEEEtran 格式的 LaTeX 程式碼。"
    "請確保使用正確的標題層級、引用格式，以及 IEEE 雙欄版面規範。"
)


class ModelBackend:
    """統一的模型推理介面。"""

    def generate(self, prompt: str, max_new_tokens: int = 1024, temperature: float = 0.1) -> str:
        raise NotImplementedError


class VLLMBackend(ModelBackend):
    """vLLM 後端（OpenAI-compatible）。"""

    def __init__(self, base_url: str = "http://localhost:8001/v1"):
        import httpx
        self.base_url = base_url
        self.client = httpx.Client(timeout=60)
        logger.info(f"vLLM 後端連接至: {base_url}")

    def generate(self, prompt: str, max_new_tokens: int = 1024, temperature: float = 0.1) -> str:
        response = self.client.post(
            f"{self.base_url}/completions",
            json={
                "model": "ieee-slm",
                "prompt": prompt,
                "max_tokens": max_new_tokens,
                "temperature": temperature,
                "stop": ["### Instruction:", "### Input:"],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["text"].strip()


class HFBackend(ModelBackend):
    """HuggingFace Transformers 後端（備援）。"""

    def __init__(self, model_path: str = MODEL_PATH):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        logger.info(f"載入 HuggingFace 模型: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            trust_remote_code=True,
        )
        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"模型載入完成，使用裝置: {self.device}")

    def generate(self, prompt: str, max_new_tokens: int = 1024, temperature: float = 0.1) -> str:
        import torch

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        # 只取生成部分（去掉 prompt）
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()


def build_prompt(user_text: str, instruction: str = DEFAULT_INSTRUCTION) -> str:
    """將使用者輸入轉換為模型 prompt。"""
    return ALPACA_PROMPT.format(instruction=instruction, input=user_text)


def load_backend(mode: str = "auto") -> ModelBackend:
    """
    根據環境選擇後端：
    - "vllm": 強制使用 vLLM
    - "hf": 強制使用 HuggingFace
    - "auto": 嘗試 vLLM，失敗則回退 HF
    """
    if mode == "vllm":
        return VLLMBackend()
    elif mode == "hf":
        return HFBackend()
    else:  # auto
        try:
            backend = VLLMBackend()
            # 測試連線
            backend.generate("test", max_new_tokens=1)
            return backend
        except Exception:
            logger.info("vLLM 不可用，切換至 HuggingFace 後端")
            return HFBackend()
