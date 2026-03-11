"""
Week 1 | Step 2 — LaTeX 原始碼萃取與過濾
從 data/raw/ 的每個論文資料夾中：
1. 找到主 .tex 檔（含 \\documentclass{IEEEtran}）
2. 驗證為 IEEE 格式
3. 萃取結構化內容（abstract, sections, references）
4. 將清洗後的 LaTeX 存入 data/processed/
"""

import re
import shutil
from pathlib import Path
from typing import Optional

from loguru import logger
from tqdm import tqdm


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

# IEEE 必要標記
IEEE_MARKERS = [
    r"\\documentclass.*IEEEtran",
    r"\\documentclass.*ieeetran",
]
# 最低字元數（排除空殼 .tex）
MIN_LATEX_CHARS = 3000


def is_ieee_latex(tex_content: str) -> bool:
    """確認此 .tex 使用 IEEEtran documentclass。"""
    for pattern in IEEE_MARKERS:
        if re.search(pattern, tex_content, re.IGNORECASE):
            return True
    return False


def find_main_tex(paper_dir: Path) -> Optional[Path]:
    """
    找到論文主 .tex 檔。
    優先選含 \\documentclass 的檔案；有多個時選最大的。
    """
    candidates = list(paper_dir.rglob("*.tex"))
    if not candidates:
        return None

    ieee_files = []
    for f in candidates:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if "\\documentclass" in content and len(content) >= MIN_LATEX_CHARS:
                ieee_files.append((f, len(content)))
        except Exception:
            continue

    if not ieee_files:
        return None

    # 選最大的（通常是主檔）
    ieee_files.sort(key=lambda x: x[1], reverse=True)
    return ieee_files[0][0]


def clean_latex(content: str) -> str:
    """
    基本清洗：
    - 移除純注釋行
    - 移除過長的空白
    - 保留結構完整性
    """
    lines = content.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 跳過純注釋行（但保留行內注釋）
        if stripped.startswith("%") and not stripped.startswith("%%"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_sections(content: str) -> dict:
    """
    萃取論文各節的文字內容（用於生成訓練輸入）。
    回傳 dict: { "abstract": str, "sections": [(title, body), ...] }
    """
    result = {"abstract": "", "sections": []}

    # 萃取 abstract
    abs_match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL
    )
    if abs_match:
        result["abstract"] = abs_match.group(1).strip()

    # 萃取 section 標題與內容
    section_pattern = re.compile(
        r"\\section\{([^}]+)\}(.*?)(?=\\section\{|\\end\{document\})", re.DOTALL
    )
    for match in section_pattern.finditer(content):
        title = match.group(1).strip()
        body = match.group(2).strip()
        if len(body) > 100:  # 過濾空節
            result["sections"].append((title, body))

    return result


def process_paper(paper_dir: Path, out_dir: Path) -> bool:
    """處理單篇論文：找主 tex → 驗證 → 清洗 → 存檔。"""
    main_tex = find_main_tex(paper_dir)
    if not main_tex:
        return False

    try:
        content = main_tex.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False

    if not is_ieee_latex(content):
        return False

    if len(content) < MIN_LATEX_CHARS:
        return False

    cleaned = clean_latex(content)
    sections = extract_sections(cleaned)

    # 需至少有 abstract 或 2 個 section
    if not sections["abstract"] and len(sections["sections"]) < 2:
        return False

    out_path = out_dir / f"{paper_dir.name}.tex"
    out_path.write_text(cleaned, encoding="utf-8")

    # 同時儲存結構化 metadata
    import json
    meta_path = out_dir / f"{paper_dir.name}.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "paper_id": paper_dir.name,
                "abstract": sections["abstract"][:500],
                "num_sections": len(sections["sections"]),
                "section_titles": [s[0] for s in sections["sections"]],
                "char_count": len(cleaned),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return True


def run_extraction(raw_dir: Path = RAW_DIR, out_dir: Path = PROCESSED_DIR):
    """批次處理所有下載論文。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    paper_dirs = [d for d in raw_dir.iterdir() if d.is_dir()]
    logger.info(f"待處理論文資料夾: {len(paper_dirs)}")

    success, skipped = 0, 0
    for pdir in tqdm(paper_dirs, desc="萃取 LaTeX"):
        if process_paper(pdir, out_dir):
            success += 1
        else:
            skipped += 1

    logger.info(f"萃取完成 — IEEE 格式: {success}, 跳過: {skipped}")
    return success


if __name__ == "__main__":
    run_extraction()
