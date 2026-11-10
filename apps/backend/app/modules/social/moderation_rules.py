"""Deterministic review signals, not an AI judgment or an automatic rejection."""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.config import get_settings

Category = Literal['racism_xenophobia', 'homophobia_transphobia', 'misogyny_sexism',
                   'hate_speech', 'harassment_insults', 'threats', 'sexual_harassment', 'spam']


class Rule(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    id: str = Field(min_length=1, max_length=80, pattern=r'^[a-z0-9-]+$')
    category: Category
    reason: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    pattern: str = Field(min_length=1, max_length=500)
    enabled: bool = True

    @field_validator('pattern')
    @classmethod
    def valid_regex(cls, value):
        try:
            compiled = re.compile(value)
        except re.error as error:
            raise ValueError(f'Invalid moderation regex: {error}') from error
        if compiled.search('') is not None:
            raise ValueError('A moderation regex must not match an empty string')
        return value


class Ruleset(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    version: str = Field(min_length=1, max_length=80)
    max_text_length: int = Field(ge=3000, le=20000)
    rules: tuple[Rule, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError('Moderation rule IDs must be unique')
        return self


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)
    rule_id: str
    category: Category
    reason: str
    confidence: float


class Analysis(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal['approved', 'pending_review']
    flagged: bool
    findings: tuple[Finding, ...]
    ruleset_version: str


def normalize_text(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).casefold()
    value = ''.join(char for char in unicodedata.normalize('NFKD', value)
                    if unicodedata.category(char) not in ('Mn', 'Cf'))
    # Narrow, deterministic evasion handling. Original text is never rewritten.
    value = value.translate(str.maketrans({'0':'o', '3':'e', '4':'a', '@':'a', '5':'s'}))
    return re.sub(r'\s+', ' ', value).strip()


@dataclass(frozen=True)
class Moderator:
    ruleset: Ruleset
    compiled: tuple

    @classmethod
    def from_file(cls, path):
        # Invalid operator configuration raises, never silently approves content.
        config = Ruleset.model_validate(json.loads(Path(path).read_text(encoding='utf-8')))
        return cls(config, tuple((rule, re.compile(rule.pattern)) for rule in config.rules if rule.enabled))

    def analyze(self, text: str) -> Analysis:
        if not isinstance(text, str):
            raise TypeError('Moderation expects text')
        if len(text) > self.ruleset.max_text_length:
            raise ValueError('Text exceeds the configured moderation limit')
        normalized = normalize_text(text)
        findings = tuple(Finding(rule_id=rule.id, category=rule.category, reason=rule.reason,
                                  confidence=rule.confidence)
                         for rule, pattern in self.compiled if pattern.search(normalized))
        return Analysis(status='pending_review' if findings else 'approved', flagged=bool(findings),
                        findings=findings, ruleset_version=self.ruleset.version)


@lru_cache(maxsize=8)
def _load(path: str):
    return Moderator.from_file(path)


def analyze_content(text: str) -> Analysis:
    configured = get_settings().moderation_rules_path
    path = Path(configured) if configured else Path(__file__).with_name('moderation_rules.json')
    return _load(str(path.resolve())).analyze(text)
