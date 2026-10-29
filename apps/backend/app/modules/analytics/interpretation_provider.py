"""Validation for historical indicator interpretations.

Classic personal/group generation has no approved Gemini queue contract yet.
Persisted historical results remain readable, but new generation is disabled.
"""
import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "reading-evidence-v10-required-contributions"


class ProviderError(Exception):
    pass


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str
    interpretation: str = Field(min_length=1, max_length=700)


class Interpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1500)
    observations: list[Observation] = Field(min_length=1, max_length=5)
    suggestions: list[str] = Field(max_length=4)
    limitations: list[str] = Field(min_length=1, max_length=5)


def validate_interpretation(content, metric_codes):
    result = Interpretation.model_validate(content)
    if any(item.metric not in metric_codes for item in result.observations):
        raise ValueError("Unsupported evidence")
    texts = [result.title, result.summary, *result.suggestions, *result.limitations,
             *(item.interpretation for item in result.observations)]
    allowed = {Decimal(str(item["value"])) for item in metric_codes.values()} if isinstance(metric_codes, dict) else set()
    if "RATING" in metric_codes or "G_RATING" in metric_codes:
        allowed.add(Decimal(5))
    for value in texts:
        if not value.strip() or len(value) > 1500:
            raise ValueError("Invalid narrative length")
        for number in re.findall(r"[-+]?\d+(?:[.,]\d+)?", value):
            if Decimal(number.replace(",", ".")) not in allowed:
                raise ValueError("Narrative must not invent numerical evidence")
    return result.model_dump()


def provider_ready():
    return False


def generate_interpretation(*_args, **_kwargs):
    raise ProviderError("indicator_interpretation_not_migrated")
