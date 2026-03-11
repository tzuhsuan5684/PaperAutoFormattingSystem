"""
Week 3-4 — Month 1 Demo：Gradio Web UI
部署於 HuggingFace Spaces，讓使用者貼上文字大綱
即可獲得完整的 IEEE LaTeX 輸出。

本地啟動：
    python ui/gradio_app.py

HuggingFace Spaces 啟動：
    在 Space 根目錄放置 app.py（見 ui/app.py）
"""

import os
import httpx
import gradio as gr
from loguru import logger


API_URL = os.getenv("API_URL", "http://localhost:8000")


# ── 範例輸入 ──────────────────────────────────────────────────────────────────
EXAMPLES = [
    [
        "Introduction\nDeep learning has revolutionized computer vision. "
        "In this paper, we propose a novel attention mechanism for image classification.\n\n"
        "Related Work\nPrevious works include ResNet [1], VGG [2], and Transformer-based models [3].\n\n"
        "Methodology\nOur method consists of three modules: feature extraction, attention pooling, and classification head.",
        "將以下學術論文段落轉換為符合 IEEEtran 格式的 LaTeX 程式碼。",
    ],
    [
        "Abstract: We present a new algorithm for wireless channel estimation using compressed sensing. "
        "Experiments on 5G NR datasets show 15% improvement in NMSE over baseline methods.",
        "為以下 IEEE 論文摘要生成完整的 LaTeX abstract 環境與文件骨架。",
    ],
    [
        "References:\n[1] Y. LeCun et al., Gradient-based learning applied to document recognition, "
        "Proc. IEEE, 1998.\n[2] K. He et al., Deep Residual Learning, CVPR, 2016.",
        "將以下參考文獻列表轉換為符合 IEEE 格式的 LaTeX \\bibitem 格式。",
    ],
]


# ── API 呼叫 ──────────────────────────────────────────────────────────────────
def call_format_api(text: str, instruction: str, max_tokens: int, temperature: float):
    """呼叫 FastAPI 推理服務。"""
    if not text.strip():
        return "⚠️ 請輸入文字大綱", ""

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{API_URL}/format",
                json={
                    "text": text,
                    "instruction": instruction or None,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            latex = data["latex"]
            latency = data["latency_ms"]
            return latex, f"⏱️ 延遲：{latency:.0f}ms"
    except httpx.ConnectError:
        return (
            "❌ 無法連線至推理服務\n\n"
            "請確認已啟動：\n```\npython inference/server.py\n```",
            "",
        )
    except Exception as e:
        return f"❌ 錯誤：{str(e)}", ""


# ── Gradio UI ─────────────────────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        title="IEEE LaTeX 自動排版系統",
        theme=gr.themes.Soft(),
        css="""
        .header { text-align: center; margin-bottom: 20px; }
        .latex-output { font-family: 'Courier New', monospace; font-size: 13px; }
        """,
    ) as demo:

        gr.HTML("""
        <div class="header">
            <h1>📄 IEEE 論文自動排版系統</h1>
            <p>基於 SLM（Qwen2.5-1.5B QLoRA fine-tune）的智慧排版解決方案</p>
            <p><small>資料本地處理，保護論文隱私</small></p>
        </div>
        """)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 輸入：文字大綱 / 草稿")
                input_text = gr.Textbox(
                    lines=15,
                    placeholder="在此貼上您的論文文字大綱、段落草稿或參考文獻...",
                    label="",
                    show_label=False,
                )

                with gr.Accordion("進階設定", open=False):
                    instruction = gr.Textbox(
                        label="自訂指令（留空使用預設）",
                        placeholder="例如：生成 IEEE 雙欄格式的 Introduction 節...",
                        lines=2,
                    )
                    with gr.Row():
                        max_tokens = gr.Slider(
                            64, 4096, value=1024, step=64, label="最大 Token 數"
                        )
                        temperature = gr.Slider(
                            0.0, 1.0, value=0.1, step=0.05, label="Temperature"
                        )

                with gr.Row():
                    submit_btn = gr.Button("✨ 生成 IEEE LaTeX", variant="primary", scale=3)
                    clear_btn = gr.Button("清除", scale=1)

            with gr.Column(scale=1):
                gr.Markdown("### 輸出：IEEE LaTeX 程式碼")
                output_latex = gr.Code(
                    language="latex",
                    label="",
                    show_label=False,
                    lines=20,
                    elem_classes=["latex-output"],
                )
                status_text = gr.Markdown("")

        # 範例
        gr.Markdown("### 範例輸入")
        gr.Examples(
            examples=EXAMPLES,
            inputs=[input_text, instruction],
            label="點擊載入範例",
        )

        # 評估指標說明
        with gr.Accordion("系統指標目標", open=False):
            gr.Markdown("""
            | 指標 | 目標值 | 衡量方式 |
            |------|--------|---------|
            | LaTeX 編譯成功率 | > 90% | pdflatex 自動編譯 |
            | IEEE 規範符合率 | > 85% | 規則檢查腳本 |
            | 補全觸發延遲 | < 800ms | Chrome Extension 計時 |
            | 相較手動排版時間節省 | > 60% | A/B 對照實驗 |
            """)

        # 事件綁定
        submit_btn.click(
            fn=call_format_api,
            inputs=[input_text, instruction, max_tokens, temperature],
            outputs=[output_latex, status_text],
        )
        clear_btn.click(
            fn=lambda: ("", "", ""),
            outputs=[input_text, output_latex, status_text],
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,  # 設 True 可產生公開連結
    )
