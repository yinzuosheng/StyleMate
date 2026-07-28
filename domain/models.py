from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Garment(BaseModel):
    id: str
    name: str
    category: str = Field(min_length=1)
    primary_color: str = Field(min_length=1)
    material: str | None = None
    seasons: list[str] = Field(min_length=1)
    styles: list[str] = Field(min_length=1)
    image_ref: str | None = None
    image_hash: str | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    source: Literal["ai", "manual", "sample"]
    created_at: datetime = Field(default_factory=datetime.now)


class OutfitRequest(BaseModel):
    scene: str = Field(min_length=1)
    target_date: str | None = None
    city: str | None = None
    style_preference: str | None = None
    extra_constraints: list[str] = Field(default_factory=list)
    candidate_garment_ids: list[str] = Field(default_factory=list)


class OutfitRecommendation(BaseModel):
    id: str
    garment_ids: list[str] = Field(min_length=1)
    score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    weather_note: str | None = None
    constraint_checks: dict[str, bool]
    knowledge_sources: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("garment_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


class AgentTraceStep(BaseModel):
    name: str
    status: Literal["success", "fallback", "failed"]
    summary: str
    duration_ms: int = Field(ge=0)


class AgentTrace(BaseModel):
    skill_name: str
    steps: list[AgentTraceStep]
    tool_calls: list[str] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
    status: Literal["success", "fallback", "failed"]


class FavoriteOutfit(BaseModel):
    owner_id: str
    recommendation: OutfitRecommendation


class OutfitFeedback(BaseModel):
    outfit_id: str
    owner_id: str
    reasons: list[str]
    note: str = ""


class SkillOutcome(BaseModel):
    status: Literal["success", "needs_review", "fallback", "failed"]
    data: dict[str, Any]
    trace: AgentTrace
    user_message: str
