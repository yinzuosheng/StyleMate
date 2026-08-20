"""Typed, auditable data exchanged by the wardrobe knowledge retriever."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

KnowledgeTopic = Literal["fabric", "care", "size", "color", "weather", "scenario", "wardrobe", "style", "storage"]


class KnowledgeRecord(BaseModel):
    id: str
    title: str = Field(min_length=4, max_length=80)
    content: str = Field(min_length=40, max_length=900)
    source_url: HttpUrl
    source_name: str
    topic: KnowledgeTopic
    retrieved_at: date


class RetrievalHit(BaseModel):
    title: str
    snippet: str
    source_name: str
    source_url: str
    topic: KnowledgeTopic
    score: float
    record_id: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    section_title: str | None = None


class UserDocumentText(BaseModel):
    filename: str
    mime_type: str
    text: str
    pages: list[str] = Field(default_factory=list)


class UserDocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    text: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None

