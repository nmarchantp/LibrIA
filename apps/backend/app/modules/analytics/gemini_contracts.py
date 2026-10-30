"""Validated business contracts for the two Gemini flows.

Provider adapters only transport structured JSON.  These models define what
LibrIA accepts and deliberately avoid psychological or medical profiling.
"""

from __future__ import annotations
from typing import Literal

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


READING_FIELDS = ('valued_elements','friction_points','themes_and_interests','emotional_response','rating_observations')


class ReadingTransportClaim(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class ReadingTransport(StrictModel):
    event_kind: Literal['finish','abandon']
    experience_summary: ReadingTransportClaim
    valued_elements: list[ReadingTransportClaim] = Field(default_factory=list,max_length=12)
    friction_points: list[ReadingTransportClaim] = Field(default_factory=list,max_length=12)
    themes_and_interests: list[ReadingTransportClaim] = Field(default_factory=list,max_length=12)
    emotional_response: list[ReadingTransportClaim] = Field(default_factory=list,max_length=12)
    rating_observations: list[ReadingTransportClaim] = Field(default_factory=list,max_length=12)


def normalize_reading_transport(value):
    # Historical flat payloads retain their existing validation. New provider
    # output attaches citations to claims so indices cannot drift independently.
    if not isinstance(value,dict) or not isinstance(value.get('experience_summary'),dict):
        return value
    parsed=ReadingTransport.model_validate(value).model_dump()
    result={'event_kind':parsed['event_kind'],'experience_summary':parsed['experience_summary']['text']}
    citations=[{'field':'experience_summary','index':0,
                'evidence_ids':list(dict.fromkeys(parsed['experience_summary']['evidence_ids']))}]
    for field in READING_FIELDS:
        result[field]=[item['text'] for item in parsed[field]]
        citations.extend({'field':field,'index':index,'evidence_ids':list(dict.fromkeys(item['evidence_ids']))}
                         for index,item in enumerate(parsed[field]))
    result['observation_evidence']=citations
    result['evidence_ids']=sorted({key for item in citations for key in item['evidence_ids']})
    return result


def reading_transport_json_schema(*, evidence_ids: list[str] | None = None, event_kind: str | None = None) -> dict:
    """Small inline transport grammar; business limits stay in ReadingAnalysis.

    Multiplying bounded citation arrays creates an unnecessarily large provider
    grammar. Keep those bounds in local validation instead of unrolling them.
    """
    import copy
    schema = ReadingTransport.model_json_schema()
    definitions = schema.get('$defs', {})

    def inline(node):
        if isinstance(node, list):
            return [inline(item) for item in node]
        if not isinstance(node, dict):
            return node
        if '$ref' in node:
            return inline(copy.deepcopy(definitions[node['$ref'].split('/')[-1]]))
        return {key: inline(value) for key, value in node.items()
                if key not in {'$defs', 'title', 'default', 'minLength', 'maxLength', 'maxItems'}}

    transport = inline(schema)
    if evidence_ids:
        identifier = {'type':'string','enum': sorted(set(evidence_ids))}
        transport['properties']['experience_summary']['properties']['evidence_ids']['items'] = identifier
        for field in READING_FIELDS:
            transport['properties'][field]['items']['properties']['evidence_ids']['items'] = identifier
    if event_kind:
        transport['properties']['event_kind']['enum'] = [event_kind]
    return transport


class ObservationEvidence(StrictModel):
    field: Literal['experience_summary','valued_elements','friction_points','themes_and_interests','emotional_response','rating_observations']
    index: int = Field(ge=0, description='Zero-based array index; experience_summary always uses 0.')
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class ReadingAnalysis(StrictModel):
    event_kind: str
    experience_summary: str = Field(min_length=1, max_length=4_000)
    observation_evidence: list[ObservationEvidence] = Field(min_length=1, max_length=61)
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
