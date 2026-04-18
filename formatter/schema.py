"""
論文結構化資料模型（Schema）。

AI 分析論文草稿後輸出此格式，作為 Word 模板套用的中介資料。

層級：PaperSchema → Chapter → Section → SubSection → ContentBlock
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field


# ── 內文區塊（Content Blocks）────────────────────────────────────────────────

class ParagraphBlock(BaseModel):
    """一般文字段落。"""
    type: Literal["paragraph"] = "paragraph"
    text: str


class FigureBlock(BaseModel):
    """圖片（草稿中無法萃取實際圖檔，保留說明文字）。"""
    type: Literal["figure"] = "figure"
    caption: str


class TableBlock(BaseModel):
    """表格。"""
    type: Literal["table"] = "table"
    caption: str
    rows: list[list[str]] = Field(default_factory=list)


ContentBlock = Annotated[
    Union[ParagraphBlock, FigureBlock, TableBlock],
    Field(discriminator="type"),
]


# ── 章節層級（Sections）──────────────────────────────────────────────────────

class SubSection(BaseModel):
    """子節（例如 1-1-1）。"""
    number: str   # e.g. "1-1-1"
    title: str
    content: list[ContentBlock] = Field(default_factory=list)


class Section(BaseModel):
    """節（例如 1-1）。"""
    number: str   # e.g. "1-1"
    title: str
    content: list[ContentBlock] = Field(default_factory=list)
    subsections: list[SubSection] = Field(default_factory=list)


class Chapter(BaseModel):
    """章（例如 第一章）。"""
    number: int
    title: str
    intro_content: list[ContentBlock] = Field(
        default_factory=list,
        description="第一節標題出現前的章節引言內容",
    )
    sections: list[Section] = Field(default_factory=list)


# ── 前置區段（Front Matter）──────────────────────────────────────────────────

class CoverInfo(BaseModel):
    """封面與書名頁資訊。"""
    title_zh: Optional[str] = None
    title_en: Optional[str] = None
    author: Optional[str] = None
    student_id: Optional[str] = None
    advisor: Optional[str] = None
    co_advisor: Optional[str] = None
    department: Optional[str] = None
    university: Optional[str] = None
    degree: Optional[str] = None   # "碩士" | "博士"
    year: Optional[str] = None     # 民國年，例如 "112"
    month: Optional[str] = None


class AbstractSection(BaseModel):
    """摘要（中文或英文）。"""
    content: str
    keywords: list[str] = Field(default_factory=list)


# ── 頂層 Schema ───────────────────────────────────────────────────────────────

class PaperSchema(BaseModel):
    """
    論文完整結構化資料。

    由 ai_analyzer 從草稿中萃取，
    由 word_builder 套用至 Word 模板產生最終文件。
    """
    cover: CoverInfo = Field(default_factory=CoverInfo)
    abstract_zh: Optional[AbstractSection] = None
    abstract_en: Optional[AbstractSection] = None
    acknowledgments: Optional[str] = None
    chapters: list[Chapter] = Field(default_factory=list)
    references: list[str] = Field(
        default_factory=list,
        description="每個元素為一筆完整的參考文獻字串，含編號，例如 '[1] Author...'",
    )
