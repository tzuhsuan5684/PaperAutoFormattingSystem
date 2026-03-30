"""
論文格式問題檢查模組。
只回傳問題清單，不修改文件。
"""
import re
from dataclasses import dataclass, field
from typing import Any

from docx import Document
from docx.oxml.ns import qn


_RE_FIGURE = re.compile(r"^(圖|Figure)\s*\d+", re.IGNORECASE)
_RE_TABLE  = re.compile(r"^(表|Table)\s*\d+",  re.IGNORECASE)

# 各區段常見標題關鍵字對應
_SECTION_KEYWORDS: dict[str, list[str]] = {
    "封面":         ["封面"],
    "書名頁":       ["書名頁"],
    "授權書":       ["授權書", "授權同意書"],
    "口試委員審定書": ["口試委員", "審定書"],
    "中文摘要":     ["中文摘要", "摘要"],
    "英文摘要":     ["abstract", "英文摘要"],
    "誌謝":         ["誌謝", "致謝"],
    "目錄":         ["目錄"],
    "圖目錄":       ["圖目錄", "圖次"],
    "表目錄":       ["表目錄", "表次"],
    "論文正文":     ["第一章", "第壹章", "chapter 1", "introduction"],
    "參考文獻":     ["參考文獻", "references"],
}

# 需要親筆簽名的實體文件
_PHYSICAL_DOCS = ["授權書", "口試委員審定書"]


@dataclass
class FormatIssue:
    severity:   str   # "error" | "warning" | "info"
    section:    str   # 問題所在區段
    message:    str   # 給使用者看的中文說明
    auto_fixed: bool  # 是否已被 corrector 自動修正


class ThesisChecker:
    """檢查論文格式問題，回傳 FormatIssue 清單。"""

    def check_all(self, doc: Document, config: dict[str, Any]) -> list[FormatIssue]:
        issues: list[FormatIssue] = []
        issues.extend(self.check_required_sections(doc, config))
        issues.extend(self.check_abstract_word_count(doc, config))
        issues.extend(self.check_figure_caption_positions(doc, config))
        issues.extend(self.check_cover_color_reminder())
        issues.extend(self.check_physical_documents_reminder(config))
        return issues

    # ── 1. 缺少必要區段 ──────────────────────────────────────────────────
    def check_required_sections(
        self, doc: Document, config: dict[str, Any]
    ) -> list[FormatIssue]:
        issues   = []
        all_text = "\n".join(p.text.lower() for p in doc.paragraphs)

        for section in config.get("required_sections", []):
            keywords = _SECTION_KEYWORDS.get(section, [section])
            found    = any(kw.lower() in all_text for kw in keywords)
            if not found:
                issues.append(FormatIssue(
                    severity   = "error",
                    section    = section,
                    message    = f"缺少必要區段「{section}」，請確認文件中是否包含此部分。",
                    auto_fixed = False,
                ))
        return issues

    # ── 2. 摘要字數 ──────────────────────────────────────────────────────
    def check_abstract_word_count(
        self, doc: Document, config: dict[str, Any]
    ) -> list[FormatIssue]:
        issues   = []
        wc_cfg   = config.get("abstract_word_count", {})
        min_wc   = wc_cfg.get("min", 300)
        max_wc   = wc_cfg.get("max", 500)

        zh_abstract, en_abstract = self._extract_abstracts(doc)

        for label, text in [("中文摘要", zh_abstract), ("英文摘要", en_abstract)]:
            if text is None:
                continue  # 已由 check_required_sections 報錯
            count = self._count_words(text, is_chinese=(label == "中文摘要"))
            if count < min_wc:
                issues.append(FormatIssue(
                    severity   = "warning",
                    section    = label,
                    message    = (
                        f"{label}字數不足（目前約 {count} 字，建議至少 {min_wc} 字）。"
                    ),
                    auto_fixed = False,
                ))
            elif count > max_wc:
                issues.append(FormatIssue(
                    severity   = "warning",
                    section    = label,
                    message    = (
                        f"{label}字數過多（目前約 {count} 字，建議不超過 {max_wc} 字）。"
                    ),
                    auto_fixed = False,
                ))
        return issues

    def _extract_abstracts(
        self, doc: Document
    ) -> tuple[str | None, str | None]:
        """從文件中抽取中 / 英文摘要的段落文字。"""
        paras  = doc.paragraphs
        zh_buf: list[str] = []
        en_buf: list[str] = []
        mode   = None

        for p in paras:
            t = p.text.strip()
            t_lower = t.lower()
            if "中文摘要" in t or (t == "摘要" and mode is None):
                mode = "zh"
                continue
            if "英文摘要" in t_lower or t_lower == "abstract":
                mode = "en"
                continue
            # 遇到其他主標題（誌謝、目錄等）就停止收集
            if any(kw in t for kw in ["誌謝", "致謝", "目錄", "誌  謝"]):
                mode = None

            if mode == "zh" and t:
                zh_buf.append(t)
            elif mode == "en" and t:
                en_buf.append(t)

        zh = " ".join(zh_buf) if zh_buf else None
        en = " ".join(en_buf) if en_buf else None
        return zh, en

    @staticmethod
    def _count_words(text: str, is_chinese: bool) -> int:
        if is_chinese:
            # 中文以字元計；英文單字以空白切分
            zh_chars    = len(re.findall(r"[\u4e00-\u9fff]", text))
            en_words    = len(re.findall(r"[a-zA-Z]+", text))
            return zh_chars + en_words
        else:
            return len(text.split())

    # ── 3. 圖說位置 ──────────────────────────────────────────────────────
    def check_figure_caption_positions(
        self, doc: Document, config: dict[str, Any]
    ) -> list[FormatIssue]:
        issues   = []
        children = list(doc.element.body)

        for i, child in enumerate(children):
            tag  = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag != "p":
                continue
            text = _para_text(child)
            if not _RE_FIGURE.match(text):
                continue

            # 確認前一個元素是否含圖片
            if i > 0:
                prev     = children[i - 1]
                prev_tag = prev.tag.split("}")[-1] if "}" in prev.tag else prev.tag
                if prev_tag != "p" or not _has_image(prev):
                    issues.append(FormatIssue(
                        severity   = "warning",
                        section    = "圖說",
                        message    = f"「{text[:20]}」的圖說位置不正確，應放在圖片下方，已自動修正。",
                        auto_fixed = True,
                    ))
        return issues

    # ── 4. 封面顏色提醒 ──────────────────────────────────────────────────
    def check_cover_color_reminder(self) -> list[FormatIssue]:
        return [
            FormatIssue(
                severity   = "info",
                section    = "封面",
                message    = (
                    "請注意：碩士論文封面應為暗紅色，博士論文封面應為墨綠色。"
                    "此為印刷問題，無法由程式自動修正，請自行確認。"
                ),
                auto_fixed = False,
            )
        ]

    # ── 5. 實體文件提醒 ──────────────────────────────────────────────────
    def check_physical_documents_reminder(
        self, config: dict[str, Any]
    ) -> list[FormatIssue]:
        issues = []
        for doc_name in _PHYSICAL_DOCS:
            issues.append(FormatIssue(
                severity   = "info",
                section    = doc_name,
                message    = (
                    f"「{doc_name}」需要親筆簽名，無法由程式自動產生，"
                    "請依學校規定準備紙本或掃描件。"
                ),
                auto_fixed = False,
            ))
        return issues


# ── 工具函式 ─────────────────────────────────────────────────────────────────

def _para_text(p_elem) -> str:
    return "".join(t.text or "" for t in p_elem.iter(qn("w:t")))


def _has_image(p_elem) -> bool:
    for tag in (qn("w:drawing"), qn("w:pict"), qn("a:blip")):
        if p_elem.find(".//" + tag) is not None:
            return True
    return False
