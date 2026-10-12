"""Strict application-owned output schemas; no SDK types leak into stored briefs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(StrictModel):
    statement: str
    evidence_ids: list[str] = Field(min_length=1)


class Missing(StrictModel):
    description: str
    reason: str
    related_evidence_ids: list[str]


class Conflict(StrictModel):
    description: str
    evidence_ids: list[str] = Field(min_length=2)


class Action(StrictModel):
    action: str
    rationale: str
    evidence_ids: list[str]


class ReviewBrief(StrictModel):
    schema_version: Literal[1]
    case_id: str
    policy_version_ids: list[str]
    semantic_release_id: str
    projection_id: str
    evidence_bundle_ids: list[str] = Field(min_length=1)
    evidence_status: Literal["sufficient", "incomplete", "conflicted"]
    observations: list[Observation] = Field(min_length=1)
    missing_information: list[Missing]
    conflicts: list[Conflict]
    suggested_next_actions: list[Action]
    limitations: list[str]


class OntologyReview(StrictModel):
    schema_version: Literal[1]
    release_id: str
    projection_id: str
    observations: list[str]
    unresolved_mapping_questions: list[str]
    suggested_review_actions: list[str]
    report_references: list[str]
