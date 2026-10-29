"""Validated business contracts for the two Gemini flows.

Provider adapters only transport structured JSON.  These models define what
LibrIA accepts and deliberately avoid psychological or medical profiling.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileInterpretation(StrictModel):
    narrative_preferences: list[str] = Field(default_factory=list, max_length=12)
    character_preferences: list[str] = Field(default_factory=list, max_length=12)
    themes_and_conflicts: list[str] = Field(default_factory=list, max_length=12)
    genres_and_styles: list[str] = Field(default_factory=list, max_length=12)
    emotional_patterns: list[str] = Field(default_factory=list, max_length=12)
    interests_from_notes_and_theories: list[str] = Field(default_factory=list, max_length=12)
    rating_patterns: list[str] = Field(default_factory=list, max_length=12)
    evidence_ids: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Evidence ids must be unique")
        return value


class ProfileChunkSummary(ProfileInterpretation):
    """Reusable interpretation of one complete, traceable context fragment."""


class RecommendationSelection(StrictModel):
    work_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(min_length=1, max_length=500)
    justification: str = Field(min_length=1, max_length=2_000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Recommendation evidence ids must be unique")
        return value


class RecommendationGeneration(StrictModel):
    profile: ProfileInterpretation
    recommendations: list[RecommendationSelection] = Field(min_length=1, max_length=8)


class RecommendationTransportSelection(StrictModel):
    work_id: str = Field(min_length=1, max_length=100)
    justification: str = Field(min_length=1, max_length=2_000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Recommendation evidence ids must be unique")
        return value


class RecommendationTransportGeneration(StrictModel):
    recommendations: list[RecommendationTransportSelection] = Field(min_length=1, max_length=8)


def recommendation_transport_json_schema(
    *, candidate_ids: list[str] | None = None, evidence_ids: list[str] | None = None
) -> dict:
    """Flat schema; catalog metadata is always filled by LibrIA, not Gemini."""
    work_id = {"type": "string"}
    evidence_id = {"type": "string"}
    if candidate_ids:
        work_id["enum"] = candidate_ids
    if evidence_ids:
        evidence_id["enum"] = evidence_ids
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recommendations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "work_id": work_id,
                        "justification": {"type": "string"},
                        "evidence_ids": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 20,
                            "items": evidence_id,
                        },
                    },
                    "required": ["work_id", "justification", "evidence_ids"],
                },
            },
        },
        "required": ["recommendations"],
    }


class ReadingAnalysis(StrictModel):
    event_kind: str
    experience_summary: str = Field(min_length=1, max_length=4_000)
    valued_elements: list[str] = Field(default_factory=list, max_length=12)
    friction_points: list[str] = Field(default_factory=list, max_length=12)
    themes_and_interests: list[str] = Field(default_factory=list, max_length=12)
    emotional_response: list[str] = Field(default_factory=list, max_length=12)
    rating_observations: list[str] = Field(default_factory=list, max_length=12)
    evidence_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("event_kind")
    @classmethod
    def event_is_terminal(cls, value: str) -> str:
        if value not in {"finish", "abandon"}:
            raise ValueError("Only finish and abandon events can be analysed")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Evidence ids must be unique")
        return value
