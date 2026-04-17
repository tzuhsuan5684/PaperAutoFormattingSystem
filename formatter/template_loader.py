"""
模板載入模組。

職責：
  - 根據 school_id 查找 templates/{school_id}.docx
  - 將模板的 Word Styles 注入到使用者的 Document 物件中
    （已存在的 style 不覆蓋，缺少的才補入）

新增學校模板：在 templates/ 放一個 {school_id}.docx 即可，不需修改程式碼。
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def get_template_path(school_id: str) -> Path | None:
    """
    回傳該學校的模板 .docx 路徑。
    若模板不存在則回傳 None（系統退回純 JSON config 修正模式）。
    """
    path = TEMPLATES_DIR / f"{school_id}.docx"
    return path if path.exists() else None


def inject_styles_from_template(template_path: Path, target_doc: Document) -> list[str]:
    """
    將模板 .docx 的 Word Styles 注入 target_doc。

    規則：
      - target_doc 已有同 styleId 的 style → 跳過（不覆蓋使用者既有設定）
      - target_doc 缺少的 style → 複製模板的定義進去

    回傳：本次實際注入的 styleId 清單（供 debug / logging 使用）。
    """
    template_doc = Document(str(template_path))

    target_styles_elem   = target_doc.part.styles._element
    template_styles_elem = template_doc.part.styles._element

    # 收集 target 已有的 styleId
    existing_ids: set[str] = {
        s.get(qn("w:styleId"), "")
        for s in target_styles_elem.findall(qn("w:style"))
    }

    injected: list[str] = []
    for style_elem in template_styles_elem.findall(qn("w:style")):
        style_id = style_elem.get(qn("w:styleId"), "")
        if style_id and style_id not in existing_ids:
            target_styles_elem.append(deepcopy(style_elem))
            injected.append(style_id)

    return injected
