from datetime import datetime

import pytest

from stylemate.domain.models import UserDocument
from stylemate.rag.user_docs import (
    DocumentLimitError,
    DocumentLimits,
    chunk_user_document,
    extract_user_document,
)


def test_pdf_extraction_rejects_oversized_payload():
    with pytest.raises(DocumentLimitError, match="文件不能超过 4 MB"):
        extract_user_document(
            "guide.pdf",
            "application/pdf",
            b"x" * (4 * 1024 * 1024 + 1),
            DocumentLimits(max_bytes=4 * 1024 * 1024, max_chars=200_000),
        )


def test_text_and_markdown_decode_utf8_bom_and_reject_unsupported_type():
    extracted = extract_user_document(
        "notes.md", "text/markdown", "\ufeff羊毛需要按照洗标清洗。".encode(), DocumentLimits()
    )

    assert extracted.text == "羊毛需要按照洗标清洗。"
    assert extracted.filename == "notes.md"
    with pytest.raises(ValueError, match="不支持"):
        extract_user_document("notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"x", DocumentLimits())


def test_long_pdf_text_is_split_into_overlapping_page_aware_chunks():
    document = UserDocument(
        owner_id="owner-a",
        conversation_id="thread-a",
        document_id="doc-a",
        filename="guide.pdf",
        mime_type="application/pdf",
        text="",
        pages=["甲" * 900, "第二页羊毛只能低温平铺晾干。"],
        created_at=datetime(2026, 8, 17),
    )

    chunks = chunk_user_document(document, chunk_size=600, overlap=80)

    assert [chunk.page_number for chunk in chunks] == [1, 1, 2]
    assert chunks[0].text[-80:] == chunks[1].text[:80]
    assert chunks[2].text == "第二页羊毛只能低温平铺晾干。"
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_markdown_sections_keep_titles_and_neighbor_links():
    body = "第一段说明。" * 80
    document = UserDocument(
        owner_id="owner-a",
        conversation_id="thread-a",
        document_id="doc-sections",
        filename="guide.md",
        mime_type="text/markdown",
        text=f"# 羊毛护理\n\n{body}\n\n## 功能外套\n\n避免使用柔顺剂。",
        created_at=datetime(2026, 8, 17),
    )

    chunks = chunk_user_document(document, chunk_size=300, overlap=50)

    wool_chunks = [item for item in chunks if item.section_title == "羊毛护理"]
    shell_chunks = [item for item in chunks if item.section_title == "功能外套"]
    assert len(wool_chunks) > 1
    assert wool_chunks[0].next_chunk_id == wool_chunks[1].chunk_id
    assert wool_chunks[1].previous_chunk_id == wool_chunks[0].chunk_id
    assert shell_chunks[0].previous_chunk_id is None
    assert shell_chunks[0].text.startswith("功能外套\n")
