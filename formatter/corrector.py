"""
論文格式自動修正模組。
依照學校 JSON config 修正 .docx 文件的頁邊距、行距、頁碼、圖表說明位置等。
"""
import re
from copy import deepcopy
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt
from docx.enum.text import WD_LINE_SPACING
from lxml import etree


# ── 正則：圖說 / 表說 / 資料來源 ──────────────────────────────────────────
_RE_FIGURE = re.compile(r"^(圖|Figure)\s*\d+", re.IGNORECASE)
_RE_TABLE  = re.compile(r"^(表|Table)\s*\d+",  re.IGNORECASE)
_RE_SOURCE = re.compile(r"^(資料來源|Source\s*[:：])", re.IGNORECASE)


class ThesisCorrector:
    """依照 config 自動修正論文格式。"""

    # ── 1. 頁邊距 ──────────────────────────────────────────────────────────
    def fix_margins(self, doc: Document, config: dict[str, Any]) -> None:
        """套用頁邊距到所有 section。"""
        m = config["margins"]
        top    = Cm(m["top_cm"])
        bottom = Cm(m["bottom_cm"])
        left   = Cm(m["left_cm"])
        right  = Cm(m["right_cm"])
        print(f"top: {top}, bottom: {bottom}, left: {left}, right: {right}")

        for section in doc.sections:
            section.top_margin    = top
            section.bottom_margin = bottom
            section.left_margin   = left
            section.right_margin  = right

    # ── 2. 行距 ────────────────────────────────────────────────────────────
    def fix_line_spacing(self, doc: Document, config: dict[str, Any]) -> None:
        """所有段落套用 1.5 倍行距；章標題後套用雙倍行距。"""
        ls_cfg  = config["line_spacing"]
        spacing = ls_cfg["value"]  # 1.5

        for para in doc.paragraphs:
            pf = para.paragraph_format
            pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            pf.line_spacing      = spacing

            # 章標題段落後加大行距（雙倍）
            style_name = (para.style.name or "").lower()
            if "heading 1" in style_name or "chapter" in style_name:
                pf.space_after = Pt(24)

    # ── 3. 頁碼 ────────────────────────────────────────────────────────────
    def fix_page_numbers(self, doc: Document, config: dict[str, Any]) -> None:
        """
        在文件中插入頁碼：
        - 前置部分（第一個 section）：小寫羅馬數字，置中底端
        - 正文部分（第二個 section 起，或在遇到「第一章」時建立新 section）：
          阿拉伯數字從 1 開始，置中底端

        python-docx 的 section break 需要操作底層 XML。
        """
        pg_cfg = config["page_number"]

        # 確保至少有兩個 section（前置 / 正文）
        self._ensure_two_sections(doc)

        sections = list(doc.sections)

        # 前置：section 0
        self._set_footer_page_number(
            sections[0],
            fmt="lowerRoman",
            start=1,
            distance_cm=pg_cfg["distance_from_bottom_cm"],
        )

        # 正文：section 1+
        for sec in sections[1:]:
            self._set_footer_page_number(
                sec,
                fmt="decimal",
                start=1,
                distance_cm=pg_cfg["distance_from_bottom_cm"],
            )

    def _ensure_two_sections(self, doc: Document) -> None:
        """若文件只有一個 section，在偵測到正文第一章時插入分節符號。"""
        if len(doc.sections) >= 2:
            return

        # 找到「第一章」或 Heading 1 段落，插入連續分節（奇偶分頁也可改 evenPage）
        for para in doc.paragraphs:
            style_name = (para.style.name or "").lower()
            text       = para.text.strip()
            is_chapter = (
                "heading 1" in style_name
                or re.match(r"^第[一二三四五六七八九十]+章", text)
            )
            if is_chapter:
                self._insert_section_break_before(para, break_type="nextPage")
                break

    @staticmethod
    def _insert_section_break_before(para, break_type: str = "nextPage") -> None:
        """在指定段落之前插入分節符號（操作底層 XML）。"""
        # 建立新的 <w:p> 用來承載分節符號
        new_p = OxmlElement("w:p")
        pPr   = OxmlElement("w:pPr")
        sectPr = OxmlElement("w:sectPr")
        pgSz   = OxmlElement("w:type")
        pgSz.set(qn("w:val"), break_type)
        sectPr.append(pgSz)
        pPr.append(sectPr)
        new_p.append(pPr)
        para._p.addprevious(new_p)

    @staticmethod
    def _set_footer_page_number(
        section,
        fmt: str,
        start: int,
        distance_cm: float,
    ) -> None:
        """
        在 section 的 footer 中心插入頁碼欄位，設定格式與起始頁。

        fmt 可為 "decimal" | "lowerRoman" | "upperRoman" 等（OOXML numFmt 值）。
        """
        # 設定 footer 距底端距離
        section.footer_distance = Cm(distance_cm)
        section.different_first_page_header_footer = False

        footer = section.footer
        # 清空現有 footer 段落
        for p in footer.paragraphs:
            p.clear()

        # 取得（或建立）第一個段落
        if footer.paragraphs:
            fp = footer.paragraphs[0]
        else:
            fp = footer.add_paragraph()

        # 置中
        fp.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER

        # 插入頁碼欄位 XML： <w:fldChar> + <w:instrText> + <w:fldChar>
        run = fp.add_run()
        r_elem = run._r

        def _make_fld(fld_type: str):
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), fld_type)
            return fc

        r_elem.append(_make_fld("begin"))

        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = " PAGE "
        r_elem.append(instr)
        r_elem.append(_make_fld("separate"))
        r_elem.append(_make_fld("end"))

        # 設定頁碼格式與起始頁（操作 sectPr）
        sect_pr = section._sectPr
        # 移除舊的 pgNumType
        for old in sect_pr.findall(qn("w:pgNumType")):
            sect_pr.remove(old)
        pg_num_type = OxmlElement("w:pgNumType")
        pg_num_type.set(qn("w:fmt"),   fmt)
        pg_num_type.set(qn("w:start"), str(start))
        sect_pr.append(pg_num_type)

    # ── 4. 圖表說明位置 ────────────────────────────────────────────────────
    def fix_figure_table_captions(self, doc: Document, config: dict[str, Any]) -> None:
        """
        偵測圖說 / 表說 / 資料來源，確保：
        - 圖說在圖片（含圖片的段落）下方
        - 表說在表格上方
        - 資料來源永遠在圖表下方
        """
        body_elem = doc.element.body
        children  = list(body_elem)  # w:p 或 w:tbl

        i = 0
        while i < len(children):
            child = children[i]
            tag   = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            # ── 圖說：應在含圖片的段落後面 ──
            if tag == "p":
                text = _para_text(child)
                if _RE_FIGURE.match(text):
                    # 往前找圖片段落
                    if i > 0:
                        prev = children[i - 1]
                        prev_tag = prev.tag.split("}")[-1] if "}" in prev.tag else prev.tag
                        # 若前一個不是含圖片的段落，把圖說移到圖片下方
                        # （MVP：已在圖片後則不動；若偵測到圖說在圖片前則交換）
                        if prev_tag == "p" and not _has_image(prev):
                            # 找最近的含圖片段落
                            img_idx = self._find_nearest_image_before(children, i)
                            if img_idx is not None and img_idx != i - 1:
                                # 移動圖說到圖片下方
                                body_elem.remove(child)
                                children.pop(i)
                                insert_at = img_idx + 1
                                ref_elem  = children[insert_at] if insert_at < len(children) else None
                                if ref_elem is not None:
                                    body_elem.insert(list(body_elem).index(ref_elem), child)
                                else:
                                    body_elem.append(child)
                                children.insert(insert_at, child)
                                i = insert_at + 1
                                continue

            # ── 表說：應在 <w:tbl> 上方 ──
            if tag == "p":
                text = _para_text(child)
                if _RE_TABLE.match(text):
                    if i + 1 < len(children):
                        nxt     = children[i + 1]
                        nxt_tag = nxt.tag.split("}")[-1] if "}" in nxt.tag else nxt.tag
                        if nxt_tag == "tbl":
                            pass  # 已在正確位置
                        else:
                            # 找後方最近的表格
                            tbl_idx = self._find_nearest_table_after(children, i)
                            if tbl_idx is not None:
                                body_elem.remove(child)
                                children.pop(i)
                                tbl_idx -= 1  # 因為移除後 index 前移
                                ref_elem = children[tbl_idx]
                                body_elem.insert(list(body_elem).index(ref_elem), child)
                                children.insert(tbl_idx, child)
                                i = tbl_idx + 1
                                continue

            # ── 資料來源：移到最近圖/表後方 ──
            if tag == "p":
                text = _para_text(child)
                if _RE_SOURCE.match(text):
                    # 確保資料來源不在圖/表之前
                    if i + 1 < len(children):
                        nxt_tag = children[i + 1].tag.split("}")[-1]
                        if nxt_tag in ("drawing", "tbl"):
                            # 資料來源跑到圖表前面了，移到後面
                            target = children[i + 1]
                            body_elem.remove(child)
                            children.pop(i)
                            insert_at = children.index(target) + 1
                            ref_elem  = children[insert_at] if insert_at < len(children) else None
                            if ref_elem is not None:
                                body_elem.insert(list(body_elem).index(ref_elem), child)
                            else:
                                body_elem.append(child)
                            children.insert(insert_at, child)
                            i = insert_at + 1
                            continue

            i += 1

    @staticmethod
    def _find_nearest_image_before(children, current_idx: int):
        for j in range(current_idx - 1, -1, -1):
            if _has_image(children[j]):
                return j
        return None

    @staticmethod
    def _find_nearest_table_after(children, current_idx: int):
        for j in range(current_idx + 1, len(children)):
            tag = children[j].tag.split("}")[-1] if "}" in children[j].tag else children[j].tag
            if tag == "tbl":
                return j
        return None

    # ── 5. run_all ─────────────────────────────────────────────────────────
    def run_all(self, doc: Document, config: dict[str, Any]) -> Document:
        """依序執行所有格式修正，回傳修正後的 doc。"""
        self.fix_margins(doc, config)
        self.fix_line_spacing(doc, config)
        self.fix_page_numbers(doc, config)
        self.fix_figure_table_captions(doc, config)
        return doc


# ── 工具函式 ────────────────────────────────────────────────────────────────

def _para_text(p_elem) -> str:
    """取得 <w:p> 元素的純文字。"""
    return "".join(t.text or "" for t in p_elem.iter(qn("w:t")))


def _has_image(p_elem) -> bool:
    """判斷 <w:p> 元素中是否含有圖片（drawing / pict）。"""
    for tag in (qn("w:drawing"), qn("w:pict"), qn("a:blip")):
        if p_elem.find(".//" + tag) is not None:
            return True
    return False
