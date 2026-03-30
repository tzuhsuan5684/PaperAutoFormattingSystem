"""
輸出模組：儲存 .docx 並用 LibreOffice CLI 轉換為 PDF。
"""
import shutil
import subprocess
import tempfile
from pathlib import Path


def save_docx(doc, output_path: str) -> None:
    """儲存 Document 物件為 .docx 檔案。"""
    doc.save(output_path)


def export_pdf(docx_path: str, output_path: str) -> None:
    """
    使用 LibreOffice CLI 將 .docx 轉換為 PDF。

    LibreOffice 預設會把 PDF 輸出到與 docx 相同的目錄，
    所以我們先轉到暫存目錄再複製到目標路徑。

    Raises:
        RuntimeError: 找不到 LibreOffice 或轉換失敗。
    """
    lo_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if lo_bin is None:
        raise RuntimeError(
            "找不到 LibreOffice，請安裝後再試。"
            "（Windows 可至 https://www.libreoffice.org 下載）"
        )

    docx_path = Path(docx_path).resolve()
    if not docx_path.exists():
        raise FileNotFoundError(f"找不到輸入檔案：{docx_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = subprocess.run(
            [
                lo_bin,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", tmp_dir,
                str(docx_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"PDF 轉換失敗（LibreOffice 回傳碼 {result.returncode}）：\n{result.stderr}"
            )

        # LibreOffice 輸出的 PDF 名稱與輸入同名（副檔名改為 .pdf）
        converted = Path(tmp_dir) / (docx_path.stem + ".pdf")
        if not converted.exists():
            raise RuntimeError(
                "LibreOffice 執行完畢，但找不到輸出的 PDF 檔案。"
            )

        shutil.copy2(str(converted), output_path)
