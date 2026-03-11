"""
Week 2 — 評估指標
衡量微調模型的輸出品質：
1. LaTeX 編譯成功率（呼叫 pdflatex）
2. IEEE 規範符合率（規則檢查）
3. ROUGE-L（文字相似度參考）
目標：編譯率 > 90%，IEEE 符合率 > 85%
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger
from tqdm import tqdm


# ── IEEE 規範檢查規則 ──────────────────────────────────────────────────────────
IEEE_RULES = {
    "has_documentclass_ieeetran": (
        r"\\documentclass.*IEEEtran",
        "使用 IEEEtran documentclass",
    ),
    "has_twocolumn": (
        r"\\documentclass\[.*twocolumn.*\]|IEEEtran",
        "雙欄版面設定",
    ),
    "has_abstract": (
        r"\\begin\{abstract\}",
        "包含 abstract 環境",
    ),
    "has_ieeeauthorblockn": (
        r"\\IEEEauthorblockN|\\author\{",
        "包含作者設定",
    ),
    "cite_format": (
        r"\\cite\{[^}]+\}",
        "使用 \\cite 引用",
    ),
    "section_structure": (
        r"\\section\{",
        "包含 \\section 結構",
    ),
    "no_geometry_pkg": (
        r"(?!.*\\usepackage.*geometry)",
        "未使用 geometry 套件（IEEEtran 不相容）",
    ),
}


def check_ieee_compliance(latex: str) -> dict:
    """
    對 LaTeX 字串執行 IEEE 規範檢查。
    回傳 { rule_name: bool, ... } 與總分。
    """
    results = {}
    for rule_name, (pattern, description) in IEEE_RULES.items():
        if rule_name == "no_geometry_pkg":
            # 負向規則：不應出現
            results[rule_name] = not bool(
                re.search(r"\\usepackage.*\{geometry\}", latex)
            )
        else:
            results[rule_name] = bool(re.search(pattern, latex, re.IGNORECASE))

    score = sum(results.values()) / len(results)
    return {"rules": results, "score": score}


def try_compile_latex(latex: str) -> tuple[bool, str]:
    """
    嘗試用 pdflatex 編譯 LaTeX，回傳 (成功?, 錯誤訊息)。
    需要本機安裝 pdflatex（TeX Live / MiKTeX）。
    """
    # 若 LaTeX 不是完整文件，包裝成最小文件
    if "\\documentclass" not in latex:
        latex = (
            "\\documentclass[conference]{IEEEtran}\n"
            "\\begin{document}\n"
            + latex
            + "\n\\end{document}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "test.tex"
        tex_path.write_text(latex, encoding="utf-8")

        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = result.returncode == 0 and (Path(tmpdir) / "test.pdf").exists()
            error_msg = "" if success else result.stdout[-500:]
            return success, error_msg
        except FileNotFoundError:
            return None, "pdflatex 未安裝"
        except subprocess.TimeoutExpired:
            return False, "編譯超時"


def evaluate_model_output(
    model_outputs: list[dict],
    run_latex_compile: bool = False,
) -> dict:
    """
    評估模型輸出列表。
    每筆: { "prediction": str, "reference": str（可選）}
    """
    total = len(model_outputs)
    compile_success = 0
    compile_attempted = 0
    ieee_scores = []

    for item in tqdm(model_outputs, desc="評估輸出"):
        pred = item.get("prediction", "")
        if not pred:
            continue

        # IEEE 合規率
        compliance = check_ieee_compliance(pred)
        ieee_scores.append(compliance["score"])

        # LaTeX 編譯率（可選，需要 pdflatex）
        if run_latex_compile:
            success, _ = try_compile_latex(pred)
            if success is not None:
                compile_attempted += 1
                if success:
                    compile_success += 1

    results = {
        "total_samples": total,
        "ieee_compliance_avg": sum(ieee_scores) / len(ieee_scores) if ieee_scores else 0,
        "ieee_compliance_target": 0.85,
        "ieee_compliance_pass": (
            sum(ieee_scores) / len(ieee_scores) >= 0.85 if ieee_scores else False
        ),
    }

    if compile_attempted > 0:
        compile_rate = compile_success / compile_attempted
        results["latex_compile_rate"] = compile_rate
        results["latex_compile_target"] = 0.90
        results["latex_compile_pass"] = compile_rate >= 0.90

    return results


def evaluate_from_file(predictions_file: str, run_compile: bool = False) -> dict:
    """從 JSONL 檔案讀取預測結果並評估。"""
    with open(predictions_file, encoding="utf-8") as f:
        outputs = [json.loads(line) for line in f if line.strip()]

    results = evaluate_model_output(outputs, run_latex_compile=run_compile)

    logger.info("=" * 50)
    logger.info("評估結果：")
    for k, v in results.items():
        if isinstance(v, float):
            logger.info(f"  {k}: {v:.3f}")
        else:
            logger.info(f"  {k}: {v}")
    logger.info("=" * 50)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True, help="預測結果 JSONL 檔案")
    parser.add_argument("--compile", action="store_true", help="執行 pdflatex 編譯測試")
    args = parser.parse_args()

    evaluate_from_file(args.predictions, run_compile=args.compile)
