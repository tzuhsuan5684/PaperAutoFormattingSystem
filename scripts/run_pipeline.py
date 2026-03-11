"""
端對端 Pipeline 執行腳本（Week 1 完整流程）
一鍵執行：下載 → 萃取 → 配對 → 驗證

使用方式：
    python scripts/run_pipeline.py                    # 完整流程
    python scripts/run_pipeline.py --step download    # 只下載
    python scripts/run_pipeline.py --step extract     # 只萃取
    python scripts/run_pipeline.py --step pair        # 只配對
    python scripts/run_pipeline.py --step validate    # 只驗證
    python scripts/run_pipeline.py --max-papers 1000  # 限制下載數
"""

import argparse
import sys
import time
from pathlib import Path

from loguru import logger

# 確保 project root 在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))


def step_download(max_papers: int):
    logger.info("=" * 60)
    logger.info(f"Step 1/4 — 下載 arXiv IEEE 論文（最多 {max_papers} 篇）")
    logger.info("=" * 60)
    from data_pipeline.download_arxiv import run_download
    count = run_download(max_results=max_papers)
    logger.info(f"✅ 下載完成：{count} 篇")
    return count


def step_extract():
    logger.info("=" * 60)
    logger.info("Step 2/4 — 萃取 IEEE LaTeX 原始碼")
    logger.info("=" * 60)
    from data_pipeline.extract_latex import run_extraction
    count = run_extraction()
    logger.info(f"✅ 萃取完成：{count} 篇 IEEE 論文")
    return count


def step_pair():
    logger.info("=" * 60)
    logger.info("Step 3/4 — 生成訓練配對")
    logger.info("=" * 60)
    from data_pipeline.pair_dataset import build_dataset
    count = build_dataset()
    logger.info(f"✅ 配對完成：{count} 筆訓練資料")
    return count


def step_validate():
    logger.info("=" * 60)
    logger.info("Step 4/4 — 驗證資料品質")
    logger.info("=" * 60)
    from data_pipeline.validate_dataset import validate_and_filter, print_samples
    stats = validate_and_filter()
    print_samples()
    return stats


def run_full_pipeline(max_papers: int = 10_000):
    start = time.time()
    logger.info("🚀 IEEE LaTeX 排版系統 — 資料 Pipeline 啟動")

    results = {}
    results["downloaded"] = step_download(max_papers)
    results["extracted"] = step_extract()
    results["pairs_raw"] = step_pair()
    stats = step_validate()
    results["pairs_clean"] = stats.get("passed", 0)

    elapsed = time.time() - start
    logger.info("=" * 60)
    logger.info("🎉 Pipeline 完成摘要：")
    logger.info(f"  ⏱  總耗時: {elapsed/60:.1f} 分鐘")
    logger.info(f"  📥 下載論文: {results['downloaded']} 篇")
    logger.info(f"  📄 IEEE 論文: {results['extracted']} 篇")
    logger.info(f"  📊 原始配對: {results['pairs_raw']} 筆")
    logger.info(f"  ✅ 驗證通過: {results['pairs_clean']} 筆")

    target = 5000
    if results["pairs_clean"] >= target:
        logger.info(f"  🏆 已達成 Week 1 目標（{target}+ 筆訓練資料）")
    else:
        logger.warning(
            f"  ⚠️  未達目標（{results['pairs_clean']} < {target}），"
            "請增加 --max-papers 或調整過濾條件"
        )
    logger.info("=" * 60)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IEEE LaTeX 資料 Pipeline")
    parser.add_argument(
        "--step",
        choices=["download", "extract", "pair", "validate", "all"],
        default="all",
        help="執行哪個步驟（預設：all）",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=10_000,
        help="最多下載幾篇論文（預設：10000）",
    )
    args = parser.parse_args()

    if args.step == "all":
        run_full_pipeline(args.max_papers)
    elif args.step == "download":
        step_download(args.max_papers)
    elif args.step == "extract":
        step_extract()
    elif args.step == "pair":
        step_pair()
    elif args.step == "validate":
        step_validate()
