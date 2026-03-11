"""
HuggingFace Spaces 入口點。
在 Spaces 上，模型直接載入（不需要外部 API 服務）。
"""

import os
os.environ["BACKEND_MODE"] = "hf"  # Spaces 使用 HF 後端

from ui.gradio_app import build_ui

if __name__ == "__main__":
    demo = build_ui()
    demo.launch()
