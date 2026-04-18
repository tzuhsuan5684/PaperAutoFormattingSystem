"""
AI 結構分析模組。

輸入：content_extractor.extract_content() 的結果（段落 + 表格清單）
輸出：PaperSchema（論文結構化資料）

流程：
  1. 將萃取的段落 / 表格序列化為 JSON 字串
  2. 以 OpenAI structured output（JSON Schema 模式）請 AI 辨識結構
  3. 解析回傳的 JSON → PaperSchema Pydantic 物件
"""
from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI, APIStatusError

from formatter.schema import (
    AbstractSection,
    Chapter,
    ContentBlock,
    CoverInfo,
    FigureBlock,
    PaperSchema,
    ParagraphBlock,
    Section,
    SubSection,
    TableBlock,
)


# ── OpenAI JSON Schema（對應 PaperSchema 結構）────────────────────────────────
# 用於 response_format={"type": "json_schema", ...} 確保輸出格式正確

_PAPER_JSON_SCHEMA = {
    "name": "paper_schema",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "cover": {
                "type": "object",
                "properties": {
                    "title_zh":    {"type": ["string", "null"]},
                    "title_en":    {"type": ["string", "null"]},
                    "author":      {"type": ["string", "null"]},
                    "student_id":  {"type": ["string", "null"]},
                    "advisor":     {"type": ["string", "null"]},
                    "co_advisor":  {"type": ["string", "null"]},
                    "department":  {"type": ["string", "null"]},
                    "university":  {"type": ["string", "null"]},
                    "degree":      {"type": ["string", "null"]},
                    "year":        {"type": ["string", "null"]},
                    "month":       {"type": ["string", "null"]},
                },
                "required": [
                    "title_zh", "title_en", "author", "student_id",
                    "advisor", "co_advisor", "department", "university",
                    "degree", "year", "month",
                ],
                "additionalProperties": False,
            },
            "abstract_zh": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "content":  {"type": "string"},
                            "keywords": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["content", "keywords"],
                        "additionalProperties": False,
                    },
                    {"type": "null"},
                ]
            },
            "abstract_en": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "content":  {"type": "string"},
                            "keywords": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["content", "keywords"],
                        "additionalProperties": False,
                    },
                    {"type": "null"},
                ]
            },
            "acknowledgments": {"type": ["string", "null"]},
            "chapters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "integer"},
                        "title":  {"type": "string"},
                        "intro_content": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/ContentBlock"},
                        },
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "number": {"type": "string"},
                                    "title":  {"type": "string"},
                                    "content": {
                                        "type": "array",
                                        "items": {"$ref": "#/$defs/ContentBlock"},
                                    },
                                    "subsections": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "number":  {"type": "string"},
                                                "title":   {"type": "string"},
                                                "content": {
                                                    "type": "array",
                                                    "items": {"$ref": "#/$defs/ContentBlock"},
                                                },
                                            },
                                            "required": ["number", "title", "content"],
                                            "additionalProperties": False,
                                        },
                                    },
                                },
                                "required": ["number", "title", "content", "subsections"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["number", "title", "intro_content", "sections"],
                    "additionalProperties": False,
                },
            },
            "references": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "cover", "abstract_zh", "abstract_en",
            "acknowledgments", "chapters", "references",
        ],
        "additionalProperties": False,
        "$defs": {
            "ContentBlock": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["paragraph"]},
                            "text": {"type": "string"},
                        },
                        "required": ["type", "text"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "type":    {"type": "string", "enum": ["figure"]},
                            "caption": {"type": "string"},
                        },
                        "required": ["type", "caption"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "type":    {"type": "string", "enum": ["table"]},
                            "caption": {"type": "string"},
                            "rows": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                        "required": ["type", "caption", "rows"],
                        "additionalProperties": False,
                    },
                ]
            }
        },
    },
}


# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
你是論文結構分析專家。使用者會提供一份尚未排版的論文草稿（以 JSON 格式呈現段落與表格清單）。
你的任務是辨識各段落所屬的論文區塊，並將整份草稿轉換為指定的結構化 JSON 格式。

【辨識規則】
1. 封面資訊（cover）：
   - 位於文件最前方，包含校名、系所、論文題目（中英文）、作者、學號、指導教授、年月。
   - 若段落樣式為 Heading 1 且內容為論文題目，視為 title_zh 或 title_en。

2. 摘要（abstract_zh / abstract_en）：
   - 中文摘要：段落含「摘要」或「中文摘要」標題後的內文，關鍵字以「關鍵字：」或「Keywords:」引導。
   - 英文摘要：段落含「Abstract」或「英文摘要」標題後的內文。

3. 誌謝（acknowledgments）：段落含「誌謝」或「致謝」後的內文合併為一字串。

4. 章節（chapters）：
   - 章標題：「第一章」「第二章」… 或 Heading 1 樣式且含章序號，number 填阿拉伯數字（1、2、3…）。
   - 節標題：「1-1」「2-3」形式，或 Heading 2 樣式，number 填「1-1」格式。
   - 子節標題：「1-1-1」形式，或 Heading 3 樣式，number 填「1-1-1」格式。
   - 章標題之後、第一節之前的內文放入 intro_content。

5. 圖片（FigureBlock）：
   - 含「圖 X-X」「圖 X」「Figure」等開頭的段落視為圖說，type = "figure"，caption = 說明文字。
   - 圖說所代表的實際圖片以 placeholder 方式保留。

6. 表格（TableBlock）：
   - 草稿 tables 陣列中的表格，以其索引順序配對最近的「表 X-X」「表 X」表說段落，
     type = "table"，caption = 表說，rows = 實際儲存格資料。

7. 參考文獻（references）：
   - 段落含「參考文獻」或「References」標題後的每一條文獻視為一個字串元素。

8. 其餘內文段落一律歸為 ParagraphBlock，type = "paragraph"，text = 段落文字。

【注意事項】
- 不要虛構或補充草稿中沒有的內容。
- cover 的所有欄位若草稿中找不到，填 null。
- 所有 content / intro_content 陣列若無資料，填空陣列 []。
- 保持原文，不得翻譯或改寫任何段落文字。
"""


def analyze(extracted: dict[str, Any]) -> PaperSchema:
    """
    呼叫 OpenAI 分析 extract_content() 的結果，回傳 PaperSchema。

    extracted : formatter.content_extractor.extract_content() 的輸出
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    user_content = (
        "以下是論文草稿的段落與表格資料（JSON 格式），請依照系統指示進行結構辨識：\n\n"
        + json.dumps(extracted, ensure_ascii=False, indent=2)
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        response_format={
            "type":        "json_schema",
            "json_schema": _PAPER_JSON_SCHEMA,
        },
        temperature=0.0,
        max_tokens=16384,
    )

    raw_json: str = response.choices[0].message.content.strip()
    data: dict = json.loads(raw_json)

    return _dict_to_schema(data)


# ── 解析 dict → Pydantic ──────────────────────────────────────────────────────

def _parse_content_blocks(blocks: list[dict]) -> list[ContentBlock]:
    result: list[ContentBlock] = []
    for b in blocks:
        t = b.get("type")
        if t == "paragraph":
            result.append(ParagraphBlock(text=b.get("text", "")))
        elif t == "figure":
            result.append(FigureBlock(caption=b.get("caption", "")))
        elif t == "table":
            result.append(TableBlock(
                caption=b.get("caption", ""),
                rows=b.get("rows", []),
            ))
    return result


def _dict_to_schema(data: dict) -> PaperSchema:
    cover_d = data.get("cover") or {}
    cover   = CoverInfo(**{k: cover_d.get(k) for k in CoverInfo.model_fields})

    def _parse_abstract(d) -> AbstractSection | None:
        if not d:
            return None
        return AbstractSection(
            content=d.get("content", ""),
            keywords=d.get("keywords", []),
        )

    chapters: list[Chapter] = []
    for ch in data.get("chapters") or []:
        sections: list[Section] = []
        for sec in ch.get("sections") or []:
            subsections: list[SubSection] = []
            for sub in sec.get("subsections") or []:
                subsections.append(SubSection(
                    number=sub["number"],
                    title=sub["title"],
                    content=_parse_content_blocks(sub.get("content") or []),
                ))
            sections.append(Section(
                number=sec["number"],
                title=sec["title"],
                content=_parse_content_blocks(sec.get("content") or []),
                subsections=subsections,
            ))
        chapters.append(Chapter(
            number=ch["number"],
            title=ch["title"],
            intro_content=_parse_content_blocks(ch.get("intro_content") or []),
            sections=sections,
        ))

    return PaperSchema(
        cover=cover,
        abstract_zh=_parse_abstract(data.get("abstract_zh")),
        abstract_en=_parse_abstract(data.get("abstract_en")),
        acknowledgments=data.get("acknowledgments"),
        chapters=chapters,
        references=data.get("references") or [],
    )
