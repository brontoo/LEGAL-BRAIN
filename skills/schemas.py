"""Immutable workflow metadata. No external dependencies or executable hooks."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class SkillError(ValueError):
    """Invalid bundled configuration or invalid explicit selection."""


class Jurisdiction(str, Enum):
    FEDERAL = 'uae_federal'
    ABU_DHABI = 'abu_dhabi'
    DUBAI = 'dubai'
    SHARJAH = 'sharjah'
    OTHER = 'other_uae_emirates'
    ADGM = 'adgm'
    DIFC = 'difc'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class JurisdictionContext:
    governing_law: str = 'unknown'
    court_jurisdiction: str = 'unknown'
    regulatory_jurisdiction: str = 'unknown'
    contractual_choice_of_law: str = 'unknown'
    subject_matter_jurisdiction: str = 'unknown'
    procedural_rules: str = 'unknown'

    @classmethod
    def from_mapping(cls, value: dict | None) -> JurisdictionContext:
        if value is None:
            return cls()
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise SkillError('Invalid jurisdiction context fields')
        try:
            return cls(**{k: Jurisdiction(v).value for k, v in value.items()})
        except (ValueError, TypeError) as exc:
            raise SkillError('Unsupported jurisdiction value; use unknown when unconfirmed') from exc

    def known(self) -> tuple[str, ...]:
        return tuple(v for v in asdict(self).values() if v != 'unknown')


@dataclass(frozen=True)
class OutputContract:
    sections: tuple[str, ...]
    item_fields: tuple[str, ...]


@dataclass(frozen=True)
class SourceAttribution:
    urls: tuple[str, ...]
    adaptation: str


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    name: str
    version: str
    description: str
    jurisdiction: tuple[str, ...]
    supported_languages: tuple[str, ...]
    category: str
    document_types: tuple[str, ...]
    trigger_terms: tuple[str, ...]
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    output_contract: OutputContract
    dependencies: tuple[str, ...]
    review_requirements: tuple[str, ...]
    risk_level: str
    source_attribution: SourceAttribution
    legal_authority_policy: str
    enabled: bool

    def public_metadata(self) -> dict[str, Any]:
        # Deliberate allowlist: never serve instructions, sources, dependencies or paths.
        keys = ('skill_id', 'name', 'version', 'description', 'jurisdiction',
                'supported_languages', 'category', 'document_types', 'required_inputs',
                'optional_inputs', 'output_contract', 'review_requirements', 'risk_level')
        data = asdict(self)
        return {k: data[k] for k in keys}


@dataclass(frozen=True)
class LegalSkill:
    manifest: SkillManifest
    instructions: str


@dataclass(frozen=True)
class Candidate:
    skill_id: str
    version: str
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class RoutingResult:
    status: str
    selected_skill: str | None = None
    candidates: tuple[Candidate, ...] = ()
    warnings: tuple[str, ...] = ()
    reason: str = ''

    def to_dict(self) -> dict:
        return asdict(self)
