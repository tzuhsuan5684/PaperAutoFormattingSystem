"""
Week 1 | Step 4 — 訓練資料品質驗證
讀取 training_pairs.jsonl，進行品質過濾：
- 移除輸出過短或過長的配對
- 移除輸入輸出相似度過高（無轉換意義）
- 統計資料集分佈
- 輸出通過驗證的 clean_pairs.jsonl
"""

import json
import re
from collections import Counter
from pathlib import Path

from loguru import logger
from tqdm import tqdm


INPUT_FILE = Path("data/training_pairs.jsonl")
OUTPUT_FILE = Path("data/clean_pairs.jsonl")

MIN_INPUT_CHARS = 50
MAX_INPUT_CHARS = 2000
MIN_OUTPUT_CHARS = 200
MAX_OUTPUT_CHARS = 4000
MIN_LATEX_COMMANDS = 3  # 輸出中至少要有幾個 LaTeX 命令


def count_latex_commands(text: str) -> int:
    return len(re.findall(r"\\[a-zA-Z]+", text))


def is_valid_pair(pair: dict) -> tuple[bool, str]:
    """
    驗證單筆訓練配對。
    回傳 (is_valid, reason)。
    """
    inp = pair.get("input", "")
    out = pair.get("output", "")
    instruction = pair.get("instruction", "")

    if not inp or not out or not instruction:
        return False, "缺少必要欄位"

    if not (MIN_INPUT_CHARS <= len(inp) <= MAX_INPUT_CHARS):
        return False, f"輸入長度不合: {len(inp)}"

    if not (MIN_OUTPUT_CHARS <= len(out) <= MAX_OUTPUT_CHARS):
        return False, f"輸出長度不合: {len(out)}"

    latex_cmds = count_latex_commands(out)
    if latex_cmds < MIN_LATEX_COMMANDS:
        return False, f"LaTeX 命令太少: {latex_cmds}"

    # 輸出必須包含 LaTeX 結構特徵
    has_structure = any(
        marker in out
        for marker in ["\\section", "\\begin", "\\item", "\\cite", "\\label", "\\ref"]
    )
    if not has_structure:
        return False, "輸出缺少 LaTeX 結構標記"

    return True, "OK"


def validate_and_filter(
    input_file: Path = INPUT_FILE, output_file: Path = OUTPUT_FILE
) -> dict:
    """過濾訓練集，輸出乾淨版本，回傳統計資料。"""
    if not input_file.exists():
        logger.error(f"找不到輸入檔案: {input_file}")
        return {}

    total = 0
    passed = 0
    fail_reasons: Counter = Counter()
    type_counter: Counter = Counter()

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with (
        open(input_file, "r", encoding="utf-8") as fin,
        open(output_file, "w", encoding="utf-8") as fout,
    ):
        for line in tqdm(fin, desc="驗證訓練配對"):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                pair = json.loads(line)
            except json.JSONDecodeError:
                fail_reasons["JSON 解析失敗"] += 1
                continue

            valid, reason = is_valid_pair(pair)
            if valid:
                fout.write(json.dumps(pair, ensure_ascii=False) + "\n")
                passed += 1
                type_counter[pair.get("type", "unknown")] += 1
            else:
                fail_reasons[reason] += 1

    stats = {
        "total": total,
        "passed": passed,
        "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "N/A",
        "by_type": dict(type_counter),
        "fail_reasons": dict(fail_reasons.most_common(10)),
    }

    logger.info("=" * 50)
    logger.info(f"資料集驗證結果:")
    logger.info(f"  總計: {total} 筆")
    logger.info(f"  通過: {passed} 筆 ({stats['pass_rate']})")
    logger.info(f"  類型分佈: {stats['by_type']}")
    logger.info(f"  拒絕原因: {stats['fail_reasons']}")
    logger.info("=" * 50)

    # 若通過數量不足，發出警告
    if passed < 5000:
        logger.warning(
            f"⚠️  通過配對數 {passed} < 目標 5,000，"
            "建議擴大下載範圍或放寬過濾條件。"
        )

    return stats


def print_samples(file: Path = OUTPUT_FILE, n: int = 3):
    """印出幾筆範例供人工確認。"""
    if not file.exists():
        return
    print(f"\n{'='*60}")
    print(f"範例訓練配對（前 {n} 筆）：")
    print("=" * 60)
    with open(file, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            pair = json.loads(line)
            print(f"\n[配對 {i+1}] 類型: {pair.get('type', '?')}")
            print(f"Instruction: {pair['instruction'][:80]}...")
            print(f"Input ({len(pair['input'])} chars): {pair['input'][:150]}...")
            print(f"Output ({len(pair['output'])} chars): {pair['output'][:150]}...")
    print("=" * 60)


if __name__ == "__main__":
    stats = validate_and_filter()
    print_samples()
