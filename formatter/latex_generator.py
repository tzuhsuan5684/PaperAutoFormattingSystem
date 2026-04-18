"""
呼叫 OpenAI API，將 extract_content() 的結果生成為符合學校格式的 LaTeX 原始碼。
"""
import json
import os
import time
from typing import Any

from openai import OpenAI, APIStatusError

_MODELS = [
    "gpt-4o-mini",
]
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # 秒


def generate_latex(content: dict[str, Any], config: dict[str, Any]) -> str:
    """
    content : extract_content() 回傳的 dict
    config  : load_config() 回傳的學校設定 dict
    回傳完整 .tex 原始碼字串。
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    m  = config["margins"]
    f  = config["font"]
    ls = config["line_spacing"]["value"]

    format_rules = (
        f"學校名稱：{config['school_name']}\n"
        f"頁邊距：上 {m['top_cm']}cm、下 {m['bottom_cm']}cm、"
        f"左 {m['left_cm']}cm、右 {m['right_cm']}cm\n"
        f"中文字型：{f['main_chinese']}，英文字型：{f['main_english']}，"
        f"字型大小：{f['size_pt']}pt\n"
        f"行距：{ls} 倍\n"
        f"頁碼：前置部分（封面～目錄）小寫羅馬數字，正文起阿拉伯數字，底端置中\n"
        f"章標題格式：「第一章　標題名稱」，置中\n"
        f"節標題編號：1-1、1-2（連字號，非點）\n"
        f"圖說：放圖片下方；表說：放表格上方\n"
        f"引用格式：方括號數字，如 [1]、[2]\n"
    )

    content_json = json.dumps(content, ensure_ascii=False, indent=2)

    prompt = (
        "你是 LaTeX 排版專家。根據以下論文內容與格式規則，輸出一份完整的 LaTeX 原始碼。\n\n"
        f"【格式規則】\n{format_rules}\n"
        f"【論文內容（JSON）】\n{content_json}\n\n"
        "【輸出規範】\n"
        "1. 只輸出合法的 LaTeX 原始碼，嚴禁包含 Markdown 標記（如 ```latex）或任何說明文字。\n"
        "2. \\documentclass 使用 report，12pt，a4paper。\n"
        "3. 使用 xelatex 相容套件：xeCJK、fontspec、geometry、setspace、fancyhdr、graphicx、booktabs、hyperref。\n"
        f"4. \\setCJKmainfont{{{f['main_chinese']}}}，\\setmainfont{{{f['main_english']}}}。\n"
        "5. 以 fancyhdr 設定頁碼：封面到目錄用 \\pagenumbering{roman}，正文起用 \\pagenumbering{arabic}，置中底端。\n"
        "6. 章標題：使用 \\chapter，在 preamble 以 \\CTEXsetup 或 \\renewcommand 設定「第X章　標題」格式並置中。\n"
        "7. 節編號改用連字號，在 preamble 加入：\n"
        "   \\renewcommand{\\thesection}{\\thechapter-\\arabic{section}}\n"
        "   \\renewcommand{\\thesubsection}{\\thesection-\\arabic{subsection}}\n"
        "8. 表格用 table 環境，\\caption 放上方；圖片用 figure 環境，\\caption 放下方。\n"
        "9. 原始 .docx 中無法取出的圖片，在對應位置插入：\n"
        "   \\begin{figure}[htbp]\\centering\\fbox{[圖片：說明文字]}\\end{figure}\n"
        "10. 參考文獻用 thebibliography，引用格式 [1]、[2]。\n"
        "11. 從 \\documentclass 開始直接輸出，不加任何前後綴。\n"
    )

    last_err: Exception | None = None
    for model in _MODELS:
        for attempt in range(_MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=16384,
                )
                raw = response.choices[0].message.content.strip()

                # 移除可能的 markdown code fence
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    end = len(lines) - 1
                    while end > 0 and lines[end].strip() in ("```", ""):
                        end -= 1
                    raw = "\n".join(lines[1 : end + 1])

                return raw

            except APIStatusError as e:
                last_err = e
                is_retryable = e.status_code in (429, 503)
                if is_retryable and attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                break  # 換下一個模型
            except Exception as e:
                last_err = e
                break

    raise RuntimeError(f"所有模型均無法回應，最後錯誤：{last_err}")
