from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.incident import Category

Mention = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
AnalysisStatus = Literal["not_started", "processing", "completed", "failed", "unavailable"]
ReviewStatus = Literal["pending", "corroborated", "verified", "rejected"]
AnalysisError = Literal["provider_not_configured", "provider_timeout", "provider_unavailable", "invalid_output", "missing_description", "processing_interrupted"]


class Suggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    category: Category
    severity: int = Field(ge=1, le=5)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=360)]
    classification_confidence: float = Field(ge=0, le=1)
    requires_review: Literal[True]


class Classification(Suggestion):
    language: Literal["en", "ur", "roman_ur", "mixed", "other"]
    subcategory: Annotated[str, StringConstraints(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")] | None
    entities: list[Mention] = Field(max_length=10)
    mentioned_time: Mention | None
    mentioned_location: Mention | None


class DuplicateCandidate(BaseModel):
    incident_id: UUID
    similarity: float = Field(ge=0, le=1)
    reasons: list[Literal["same_category", "within_100m", "within_20_minutes", "text_overlap", "shared_entities"]]
    manual_review_recommended: Literal[True] = True


class EvidenceAssessment(BaseModel):
    evidence_available: list[Literal["description", "submitted_location", "submitted_time", "evidence_link_uninspected"]]
    evidence_missing: list[Literal["supporting_attachment", "confirmed_independent_corroboration"]]
    potential_inconsistencies: list[Literal["category_disagreement", "mentioned_time_differs"]]
    completeness: Literal["essential_fields_present"]
    corroboration: Literal["none_identified", "potential_related_reports", "moderator_corroborated", "moderator_verified"]
    related_reports_from_other_accounts: int = Field(ge=0)
    manual_review_recommended: Literal[True] = True


class ModerationAnalysis(BaseModel):
    classification: Classification
    duplicate_candidates: list[DuplicateCandidate]
    assessment: EvidenceAssessment


class IncidentAnalysis(BaseModel):
    incident_id: UUID
    status: AnalysisStatus
    review_status: ReviewStatus
    suggestion: Suggestion | None = None
    moderation: ModerationAnalysis | None = None
    provider: str | None = None
    model: str | None = None
    attempts: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    processing_error: AnalysisError | None = None
