"""Internal retrieval contracts. Scores and metadata never certify applicable law."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Callable
from skills.schemas import JurisdictionContext


class RetrievalError(ValueError):
    pass


class SourceClass(str, Enum):
    LEGISLATION = 'official_legislation'
    JUDICIAL = 'judicial_decision'
    REGULATORY = 'administrative_regulatory'
    CONTRACT = 'contractual_evidence'
    DRAFT = 'drafting_precedent'
    POLICY = 'internal_policy'
    COMMENTARY = 'external_commentary'
    UNKNOWN = 'unknown'


FAMILIES = ('legislation', 'drafts', 'contracts', 'notices', 'poa')
AUTHORITY_CLASSES = frozenset({SourceClass.LEGISLATION, SourceClass.JUDICIAL, SourceClass.REGULATORY})


@dataclass(frozen=True)
class RetrievalContext:
    jurisdiction: JurisdictionContext = field(default_factory=JurisdictionContext)
    as_of: date | None = None
    unsupported: bool = False


@dataclass(frozen=True)
class RetrievalRequest:
    query: str
    family: str
    context: RetrievalContext = field(default_factory=RetrievalContext)

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise RetrievalError('Unsupported document family')
        if not isinstance(self.query, str) or len(self.query) > 20000 or '\x00' in self.query:
            raise RetrievalError('Invalid or oversized retrieval query')


@dataclass(frozen=True)
class LegalReference:
    kind: str
    value: str


@dataclass(frozen=True)
class Provenance:
    source_class: SourceClass = SourceClass.UNKNOWN
    declared_source_class: SourceClass = SourceClass.UNKNOWN
    instrument_id: str | None = None
    issuing_authority: str | None = None
    official_url: str | None = None
    original_title: str | None = None
    article_reference: str | None = None
    clause_reference: str | None = None
    jurisdiction: JurisdictionContext = field(default_factory=JurisdictionContext)
    jurisdiction_verified: bool = False
    language: str | None = None
    publication_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    amendment_version: str | None = None
    verified_at: date | None = None
    temporal_verified_through: date | None = None
    identity_verified: bool = False
    source_document_id: str | None = None
    content_checksum: str | None = None
    ai_generated: bool = False


@dataclass(frozen=True)
class Eligibility:
    decision: str  # compatible / unknown / incompatible
    reasons: tuple[str, ...] = ()
    temporal_status: str = 'unverified'
    jurisdiction_status: str = 'unverified'
    identity_status: str = 'unverified'


@dataclass(frozen=True)
class Candidate:
    family: str
    chunk_id: str
    title: str
    text: str
    provenance: Provenance = field(default_factory=Provenance)
    similarity: float | None = None
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    fusion_score: float = 0.0
    exact_basis: tuple[str, ...] = ()
    eligibility: Eligibility | None = None

    @property
    def identity(self) -> tuple[str, str]:
        return self.family, self.chunk_id


@dataclass(frozen=True)
class BranchResult:
    name: str
    rows: tuple[dict, ...] = ()
    status: str = 'ok'
    elapsed_ms: float = 0.0


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[Candidate, ...]
    status: str
    diagnostics: dict
