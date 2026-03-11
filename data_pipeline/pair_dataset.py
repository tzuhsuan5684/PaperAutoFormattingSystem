"""
Week 1 | Step 3 — 訓練資料配對生成
將 data/processed/ 的 IEEE LaTeX 論文轉換為
<輸入文字大綱, 輸出 IEEE LaTeX 片段> 訓練配對，
存成 JSONL 格式（data/training_pairs.jsonl）。

訓練對格式（instruction-tuning）：
{
  "instruction": "將以下學術文字大綱轉換為符合 IEEEtran 格式的 LaTeX 程式碼",
  "input": "...(純文字描述)...",
  "output": "...(對應的 IEEE LaTeX)..."
}
"""

import json
import re
from pathlib import Path
from typing import Iterator

from loguru import logger
from tqdm import tqdm


PROCESSED_DIR = Path("data/processed")
OUTPUT_FILE = Path("data/training_pairs.jsonl")

INSTRUCTION = (
    "將以下學術論文段落轉換為符合 IEEEtran 格式的 LaTeX 程式碼。"
    "請確保使用正確的標題層級、引用格式，以及 IEEE 雙欄版面規範。"
)

# 最小/最大 token 估算（字元數 / 4）
MIN_OUTPUT_CHARS = 200
MAX_OUTPUT_CHARS = 4000


def latex_to_plain_text(latex: str) -> str:
    """
    將 LaTeX 段落轉換為純文字（作為訓練輸入）。
    移除 LaTeX 命令，保留文字語意。
    """
    text = latex
    # 移除常見命令但保留內容
    text = re.sub(r"\\(?:textbf|textit|emph|text)\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\(?:label|ref|cite|footnote)\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"\{|\}", "", text)
    text = re.sub(r"\$[^$]+\$", "[EQUATION]", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def generate_pairs_from_tex(tex_path: Path) -> Iterator[dict]:
    """
    從單篇 .tex 檔生成多個訓練配對：
    1. 每個 section → LaTeX 配對
    2. 完整 document skeleton 配對
    """
    content = tex_path.read_text(encoding="utf-8", errors="ignore")

    # ── 配對類型 1: 各 section 的文字↔LaTeX ─────────────────
    section_pattern = re.compile(
        r"(\\(?:sub)*section\*?\{[^}]+\}.*?)(?=\\(?:sub)*section\*?\{|\\end\{document\})",
        re.DOTALL,
    )
    for match in section_pattern.finditer(content):
        latex_chunk = match.group(1).strip()
        if not (MIN_OUTPUT_CHARS <= len(latex_chunk) <= MAX_OUTPUT_CHARS):
            continue

        plain_input = latex_to_plain_text(latex_chunk)
        if len(plain_input) < 100:
            continue

        yield {
            "instruction": INSTRUCTION,
            "input": plain_input,
            "output": latex_chunk,
            "type": "section",
        }

    # ── 配對類型 2: 文件骨架（preamble + structure）────────────
    skeleton_match = re.search(
        r"(\\documentclass.*?\\begin\{document\}.*?\\maketitle)",
        content,
        re.DOTALL,
    )
    if skeleton_match:
        skeleton = skeleton_match.group(1).strip()
        if MIN_OUTPUT_CHARS <= len(skeleton) <= MAX_OUTPUT_CHARS:
            # 從 abstract 和 title 推斷輸入
            title_match = re.search(r"\\title\{([^}]+)\}", skeleton)
            abstract_match = re.search(
                r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL
            )

            if title_match and abstract_match:
                plain_input = (
                    f"論文標題：{title_match.group(1).strip()}\n\n"
                    f"摘要：{latex_to_plain_text(abstract_match.group(1))[:500]}"
                )
                yield {
                    "instruction": "為以下 IEEE 論文生成符合 IEEEtran 格式的 LaTeX 文件骨架，"
                    "包含 documentclass、packages、title、author、abstract。",
                    "input": plain_input,
                    "output": skeleton,
                    "type": "skeleton",
                }

    # ── 配對類型 3: 參考文獻格式 ─────────────────────────────
    bib_match = re.search(
        r"(\\begin\{thebibliography\}.*?\\end\{thebibliography\})",
        content,
        re.DOTALL,
    )
    if bib_match:
        bib_latex = bib_match.group(1).strip()
        if MIN_OUTPUT_CHARS <= len(bib_latex) <= 3000:
            plain_refs = latex_to_plain_text(bib_latex)
            yield {
                "instruction": "將以下參考文獻列表轉換為符合 IEEE 格式的 LaTeX \\bibitem 格式。",
                "input": plain_refs[:1000],
                "output": bib_latex,
                "type": "references",
            }


def build_dataset(
    processed_dir: Path = PROCESSED_DIR, output_file: Path = OUTPUT_FILE
) -> int:
    """讀取所有 processed .tex，生成 JSONL 訓練集。"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tex_files = list(processed_dir.glob("*.tex"))
    logger.info(f"處理 {len(tex_files)} 個 .tex 檔案")

    total_pairs = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for tex_path in tqdm(tex_files, desc="生成訓練配對"):
            try:
                for pair in generate_pairs_from_tex(tex_path):
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    total_pairs += 1
            except Exception as e:
                logger.warning(f"{tex_path.name} 處理失敗: {e}")

    logger.info(f"訓練配對生成完成: {total_pairs} 筆 → {output_file}")
    return total_pairs


if __name__ == "__main__":
    count = build_dataset()
    print(f"\n✅ 共生成 {count} 筆訓練配對，儲存於 {OUTPUT_FILE}")
