"""
從 rough .docx 萃取段落、表格等結構化內容，供 Gemini LaTeX 生成使用。
"""
from typing import Any

from docx import Document
from docx.oxml.ns import qn


def extract_content(doc: Document) -> dict[str, Any]:
    """
    回傳結構化內容 dict，直接作為 Gemini prompt 的輸入。

    schema:
    {
      "paragraphs": [
        {
          "style": "Heading 1" | "Normal" | ...,
          "level": 0-6,   # 0 = 非標題
          "text": "...",
        }, ...
      ],
      "tables": [
        {"rows": [["cell", ...], ...]}, ...
      ],
      "image_count": int,
    }
    """
    paragraphs: list[dict] = []
    image_count = 0

    for para in doc.paragraphs:
        # 計算段落內的圖片數量（w:drawing = 現代嵌入圖；v:imagedata = 舊式 VML）
        _VML_IMAGEDATA = "{urn:schemas-microsoft-com:vml}imagedata"
        for _ in para._p.iter(qn("w:drawing")):
            image_count += 1
        for _ in para._p.iter(_VML_IMAGEDATA):
            image_count += 1

        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else "Normal"
        level = 0
        if "Heading" in style_name:
            try:
                level = int(style_name.split()[-1])
            except (ValueError, IndexError):
                level = 1

        paragraphs.append({
            "style": style_name,
            "level": level,
            "text":  text,
        })

    tables: list[dict] = []
    for tbl in doc.tables:
        rows = []
        for row in tbl.rows:
            rows.append([cell.text.strip() for cell in row.cells])
        if rows:
            tables.append({"rows": rows})

    return {
        "paragraphs":  paragraphs,
        "tables":      tables,
        "image_count": image_count,
    }
