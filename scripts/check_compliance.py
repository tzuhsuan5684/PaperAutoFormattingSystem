"""
IEEE 合規性快速檢查工具
對單一 LaTeX 檔或字串執行規則檢查，輸出詳細報告。

使用方式：
    python scripts/check_compliance.py --file my_paper.tex
    python scripts/check_compliance.py --text "\\documentclass[conference]{IEEEtran}..."
    python scripts/check_compliance.py --predictions data/predictions.jsonl --compile
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.evaluate import check_ieee_compliance, try_compile_latex


RULE_DESCRIPTIONS = {
    "has_documentclass_ieeetran": "✅ 使用 IEEEtran documentclass",
    "has_twocolumn": "✅ 雙欄版面設定",
    "has_abstract": "✅ 包含 abstract 環境",
    "has_ieeeauthorblockn": "✅ 包含作者設定",
    "cite_format": "✅ 使用 \\cite 引用",
    "section_structure": "✅ 包含 \\section 結構",
    "no_geometry_pkg": "✅ 未誤用 geometry 套件",
}

FAIL_DESCRIPTIONS = {
    k: v.replace("✅", "❌") for k, v in RULE_DESCRIPTIONS.items()
}


def check_single(latex: str, run_compile: bool = False, label: str = "輸入") -> dict:
    """對單一 LaTeX 執行完整檢查並列印報告。"""
    result = check_ieee_compliance(latex)
    print(f"\n{'='*55}")
    print(f"IEEE 合規性報告：{label}")
    print(f"{'='*55}")

    for rule, passed in result["rules"].items():
        desc = RULE_DESCRIPTIONS[rule] if passed else FAIL_DESCRIPTIONS[rule]
        print(f"  {desc}")

    score_pct = result["score"] * 100
    bar = "█" * int(score_pct / 10) + "░" * (10 - int(score_pct / 10))
    print(f"\n  合規率：[{bar}] {score_pct:.0f}%")
    target_met = "✅ 達標（> 85%）" if score_pct >= 85 else "⚠️ 未達標（< 85%）"
    print(f"  目標：{target_met}")

    if run_compile:
        print("\n  ⚙️  執行 pdflatex 編譯測試...")
        success, error = try_compile_latex(latex)
        if success is None:
            print("  ℹ️  pdflatex 未安裝，跳過編譯測試")
        elif success:
            print("  ✅ 編譯成功")
        else:
            print(f"  ❌ 編譯失敗: {error[:200]}")
        result["compile_success"] = success

    print("=" * 55)
    return result


def check_predictions_file(file_path: str, run_compile: bool = False):
    """批次檢查預測結果 JSONL 檔案。"""
    scores = []
    compile_results = []

    with open(file_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"\n批次評估 {len(lines)} 筆預測結果...")
    for i, line in enumerate(lines):
        item = json.loads(line)
        pred = item.get("prediction", item.get("output", ""))
        result = check_ieee_compliance(pred)
        scores.append(result["score"])

        if run_compile:
            success, _ = try_compile_latex(pred)
            if success is not None:
                compile_results.append(success)

        if (i + 1) % 50 == 0:
            print(f"  進度: {i+1}/{len(lines)}, 目前合規率: {sum(scores)/len(scores)*100:.1f}%")

    avg_score = sum(scores) / len(scores) if scores else 0
    print(f"\n最終結果：")
    print(f"  IEEE 合規率（平均）: {avg_score*100:.1f}% {'✅' if avg_score >= 0.85 else '❌'}")

    if compile_results:
        compile_rate = sum(compile_results) / len(compile_results)
        print(f"  LaTeX 編譯成功率: {compile_rate*100:.1f}% {'✅' if compile_rate >= 0.90 else '❌'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IEEE LaTeX 合規性檢查")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="待檢查的 .tex 檔案路徑")
    group.add_argument("--text", help="直接輸入 LaTeX 字串")
    group.add_argument("--predictions", help="批次評估：預測結果 JSONL 檔案")
    parser.add_argument("--compile", action="store_true", help="執行 pdflatex 編譯測試")
    args = parser.parse_args()

    if args.file:
        latex = Path(args.file).read_text(encoding="utf-8", errors="ignore")
        check_single(latex, run_compile=args.compile, label=args.file)
    elif args.text:
        check_single(args.text, run_compile=args.compile)
    elif args.predictions:
        check_predictions_file(args.predictions, run_compile=args.compile)
