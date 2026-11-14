"""Additive role contracts; existing Obligation and phase2b.v1 fields stay intact."""
from dataclasses import dataclass, field
from .schemas import Obligation, Condition, EvidenceSpan, Finding


@dataclass(frozen=True)
class RoleValue:
    value: str | None = None
    evidence: tuple[EvidenceSpan, ...] = ()
    status: str = 'unknown'


@dataclass(frozen=True)
class SemanticRole:
    actor: RoleValue = field(default_factory=RoleValue)
    action: RoleValue = field(default_factory=RoleValue)
    object: RoleValue = field(default_factory=RoleValue)
    beneficiary: RoleValue = field(default_factory=RoleValue)
    modality: str = 'ambiguous'
    polarity: str = 'ambiguous'
    obligation_type: str = 'ambiguous_modal'
    modal_evidence: tuple[EvidenceSpan, ...] = ()
    conditional: bool = False
    condition_ids: tuple[str, ...] = ()
    trigger_ids: tuple[str, ...] = ()
    exception_ids: tuple[str, ...] = ()
    deadline_ids: tuple[str, ...] = ()
    financial_ids: tuple[str, ...] = ()
    consequence: RoleValue = field(default_factory=RoleValue)
    condition_fulfilment: str = 'unknown'
    liability_status: str = 'not_established'
    uncertainty: tuple[str, ...] = ('deterministic_linguistic_candidate_requires_review',)


@dataclass(frozen=True)
class RoleObligation(Obligation):
    semantic_role: SemanticRole = field(default_factory=SemanticRole)


@dataclass(frozen=True)
class QualifiedCondition(Condition):
    condition_role: str = 'dependency'
    parent_relationship: str | None = None


@dataclass(frozen=True)
class SupportFinding(Finding):
    support_level: str = 'interpretive_inference'
