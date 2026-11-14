"""Immutable analysis contracts. Offsets are Python Unicode code points, end-exclusive."""
from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import re
from skills.schemas import JurisdictionContext, SkillError
from . import config


class ClauseError(ValueError):
    """Safe fixed messages only: never include input text in exceptions."""


class SupportStatus(str, Enum):
    SUPPORTED = 'SUPPORTED_BY_TEXT'
    CONTRADICTED = 'CONTRADICTED_BY_TEXT'
    INSUFFICIENT = 'INSUFFICIENT_EVIDENCE'
    AMBIGUOUS = 'AMBIGUOUS'
    LEGAL = 'REQUIRES_LEGAL_VERIFICATION'
    NOT_ASSESSED = 'NOT_ASSESSED'


def identifier(value, name='identifier'):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}', value):
        raise ClauseError('Invalid ' + name)
    return value


@dataclass(frozen=True)
class Document:
    document_id: str
    text: str = field(repr=False)
    version: str = 'unspecified'

    def __post_init__(self):
        identifier(self.document_id, 'document identifier')
        identifier(self.version, 'document version')
        if not isinstance(self.text, str) or not self.text.strip():
            raise ClauseError('Document text is required')
        if len(self.text) > config.MAX_DOCUMENT_CHARS or self.text.count('\n') > config.MAX_LINES:
            raise ClauseError('Document exceeds analysis limits')
        if any(0xD800 <= ord(c) <= 0xDFFF or c == '\x00' for c in self.text):
            raise ClauseError('Document contains unsupported characters')

    @property
    def digest(self):
        return hashlib.sha256(self.text.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class EvidenceSpan:
    document_id: str
    version: str
    content_sha256: str
    clause_id: str
    start: int
    end: int
    quote: str = field(repr=False)


@dataclass(frozen=True)
class Clause:
    clause_id: str
    order: int
    span: EvidenceSpan
    label: str | None = None
    heading: str | None = None
    parent_clause: str | None = None
    structure: str = 'provision'
    boundary_status: str = 'explicit'
    categories: tuple[str, ...] = ()
    classification_status: str = 'deterministic_candidate'


@dataclass(frozen=True)
class Entity:
    entity_id: str
    name: str
    aliases: tuple[str, ...]
    role: str | None
    person_type: str
    evidence: EvidenceSpan
    ambiguity: bool = False
    authority_status: str = 'not_verified'


@dataclass(frozen=True)
class DefinedTerm:
    term_id: str
    term: str
    definition: str
    evidence: EvidenceSpan
    status: str = 'explicit_definition_candidate'


@dataclass(frozen=True)
class Condition:
    relationship_id: str
    source_clause: str
    relationship_type: str
    referenced_condition: str
    parties: tuple[str, ...]
    evidence: EvidenceSpan
    condition_status: str = 'unknown'
    uncertainty: str = 'textual_candidate_requires_review'
    target_clauses: tuple[str, ...] = ()


@dataclass(frozen=True)
class DateTerm:
    date_id: str
    source_clause: str
    kind: str
    expression: str
    evidence: EvidenceSpan
    amount: int | None = None
    unit: str | None = None
    day_basis: str = 'unknown'
    trigger: str | None = None
    resolved_date: str | None = None
    status: str = 'not_calculated'
    contractual_context: str = 'unspecified'


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    source_clause: str
    kind: str
    obligated_party: str | None
    beneficiary: str | None
    action: str
    subject: str
    trigger: str | None
    conditions: tuple[str, ...]
    deadlines: tuple[str, ...]
    exceptions: tuple[str, ...]
    consequences: tuple[str, ...]
    evidence: EvidenceSpan
    interpretation_status: str = 'deterministic_candidate'
    human_review_required: bool = True


@dataclass(frozen=True)
class FinancialTerm:
    financial_id: str
    source_clause: str
    amount: str
    currency: str | None
    kind: str
    evidence: EvidenceSpan
    context: EvidenceSpan
    due_status: str = 'not_established'


@dataclass(frozen=True)
class CrossReference:
    reference_id: str
    source_clause: str
    target_label: str
    target_clauses: tuple[str, ...]
    status: str
    evidence: EvidenceSpan


@dataclass(frozen=True)
class Finding:
    finding_id: str
    category: str
    claim_text: str
    claim_type: str
    evidence: tuple[EvidenceSpan, ...]
    evidence_status: str
    analytical_basis: str
    contradictory_evidence: tuple[EvidenceSpan, ...] = ()
    missing_information: tuple[str, ...] = ()
    legal_verification: tuple[str, ...] = ()
    risk_level: str = 'unknown'
    legal_applicability: str = 'not_assessed'
    human_review_status: str = 'pending'


@dataclass(frozen=True)
class AnalysisRequest:
    document: Document
    document_type: str = 'agreement'
    language: str = 'en'
    client_role: str = 'unspecified'
    jurisdiction: JurisdictionContext = field(default_factory=JurisdictionContext)
    analysis_mode: str = 'deterministic'
    playbook: str | None = None
    claims: tuple[dict, ...] = field(default=(), repr=False)
    research_query: str | None = field(default=None, repr=False)
    as_of: str | None = None

    def __post_init__(self):
        if not isinstance(self.document, Document) or not isinstance(self.jurisdiction, JurisdictionContext):
            raise ClauseError('Invalid document or jurisdiction')
        # Also validate callers constructing the jurisdiction dataclass directly.
        JurisdictionContext.from_mapping(asdict(self.jurisdiction))
        for value in (self.document_type, self.client_role):
            if not isinstance(value, str) or not 1 <= len(value) <= 120 or '\x00' in value:
                raise ClauseError('Invalid document metadata')
        if self.language not in ('en', 'ar', 'bilingual'):
            raise ClauseError('Unsupported output language')
        if self.analysis_mode not in ('deterministic', 'model_assisted'):
            raise ClauseError('Invalid analysis mode')
        if self.playbook is not None:
            identifier(self.playbook, 'playbook')
        if not isinstance(self.claims, (tuple, list)) or len(self.claims) > 30:
            raise ClauseError('Too many claim assessments')
        if any(not isinstance(c, dict) for c in self.claims):
            raise ClauseError('Invalid claim assessments')
        if self.research_query is not None and (not isinstance(self.research_query, str) or not 1 <= len(self.research_query) <= 500):
            raise ClauseError('Invalid research query')
        if self.as_of is not None:
            from datetime import date
            try:
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', self.as_of):
                    raise ValueError
                date.fromisoformat(self.as_of)
            except (ValueError, TypeError):
                raise ClauseError('Invalid research date') from None

    @classmethod
    def from_payload(cls, payload):
        allowed = {'document_id', 'document_text', 'document_version', 'document_type', 'language',
                   'client_role', 'jurisdiction', 'analysis_mode', 'playbook', 'claims', 'research_query', 'as_of'}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ClauseError('Invalid analysis fields')
        try:
            doc = Document(payload.get('document_id', 'supplied-document'), payload.get('document_text'),
                           payload.get('document_version', 'unspecified'))
            options = {k: v for k, v in payload.items() if k not in ('document_id', 'document_text', 'document_version', 'jurisdiction')}
            return cls(doc, jurisdiction=JurisdictionContext.from_mapping(payload.get('jurisdiction')), **options)
        except (TypeError, SkillError):
            raise ClauseError('Invalid analysis request') from None
