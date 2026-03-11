"""
Week 1 | Step 1 — arXiv IEEE 論文下載器
透過 arXiv API 搜尋 cs.IT / eess 類別的 IEEE 格式論文，
下載 LaTeX 原始碼（tar.gz），存入 data/raw/。
"""

import os
import time
import tarfile
import hashlib
import requests
from pathlib import Path
from typing import Optional

import arxiv
from tqdm import tqdm
from loguru import logger


# ── 設定 ──────────────────────────────────────────────────────────────────────
RAW_DIR = Path("data/raw")
MAX_RESULTS = 10          # 最多抓取筆數（依需求調整）
DELAY_SECONDS = 3             # 每次請求間隔（避免被封）
IEEE_CATEGORIES = [           # arXiv 分類：與 IEEE 高度相關
    "cs.IT",   # Information Theory
    "cs.NI",   # Networking and Internet Architecture
    "cs.SY",   # Systems and Control
    "eess.SP", # Signal Processing
    "eess.SY", # Systems and Control
]
SEARCH_KEYWORDS = [
    "IEEEtran",
    "IEEE Transactions",
    "ieee conference",
]


def _make_safe_filename(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_").replace(".", "_")


def search_ieee_papers(max_results: int = MAX_RESULTS) -> list[arxiv.Result]:
    """搜尋含有 IEEEtran 關鍵字或 IEEE 分類的論文。"""
    client = arxiv.Client(page_size=100, delay_seconds=DELAY_SECONDS)

    results = []
    for keyword in SEARCH_KEYWORDS:
        logger.info(f"搜尋關鍵字: {keyword}")
        search = arxiv.Search(
            query=keyword,
            max_results=max_results // len(SEARCH_KEYWORDS),
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        for paper in client.results(search):
            results.append(paper)

    # 去重（依 arxiv_id）
    seen = set()
    unique = []
    for r in results:
        if r.entry_id not in seen:
            seen.add(r.entry_id)
            unique.append(r)

    logger.info(f"共找到 {len(unique)} 篇不重複論文")
    return unique


def download_source(paper: arxiv.Result, out_dir: Path) -> Optional[Path]:
    """
    下載論文的 LaTeX 原始碼（tar.gz）。
    arXiv 原始碼 URL 格式：https://arxiv.org/e-print/{id}
    回傳解壓縮後的資料夾路徑，失敗則回傳 None。
    """
    arxiv_id = paper.entry_id.split("/")[-1]
    safe_id = _make_safe_filename(arxiv_id)
    paper_dir = out_dir / safe_id

    if paper_dir.exists():
        return paper_dir  # 已下載，跳過

    paper_dir.mkdir(parents=True, exist_ok=True)
    src_url = f"https://arxiv.org/e-print/{arxiv_id}"
    tar_path = paper_dir / "source.tar.gz"

    try:
        response = requests.get(src_url, timeout=60, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "pdf" in content_type or len(response.content) < 1000:
            logger.warning(f"{arxiv_id}: 無原始碼（PDF only）")
            paper_dir.rmdir()
            return None

        with open(tar_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # 解壓縮
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(paper_dir)
        except tarfile.TarError:
            # 有些是單一 .tex 檔，非 tar
            tar_path.rename(paper_dir / "main.tex")

        tar_path.unlink(missing_ok=True)
        logger.info(f"下載完成: {arxiv_id}")
        return paper_dir

    except Exception as e:
        logger.warning(f"{arxiv_id} 下載失敗: {e}")
        import shutil
        shutil.rmtree(paper_dir, ignore_errors=True)
        return None


def run_download(max_results: int = MAX_RESULTS, out_dir: Path = RAW_DIR):
    """主流程：搜尋 + 批次下載。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    papers = search_ieee_papers(max_results)

    success, failed = 0, 0
    for paper in tqdm(papers, desc="下載 arXiv 論文"):
        path = download_source(paper, out_dir)
        if path:
            success += 1
        else:
            failed += 1
        time.sleep(DELAY_SECONDS)

    logger.info(f"下載完成 — 成功: {success}, 失敗: {failed}")
    return success


if __name__ == "__main__":
    run_download()
