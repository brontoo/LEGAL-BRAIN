"""Narrow field-presence predicates, distinct from semantic or legal entailment."""
from dataclasses import replace
from . import reasoning
from .evidence import from_payload
from .schemas import ClauseError, SupportStatus as S
from .role_contracts import SupportFinding


def assess(document, clauses, data, number, duties, conditions, financial):
    if not isinstance(data, dict):
        raise ClauseError('Invalid claim')
    if data.get('claim_type') != 'structural_observation':
        original = reasoning.assess(document, clauses, data, number)
        level = ('legal_applicability' if original.evidence_status == S.LEGAL.value else
                 'exact_textual_evidence' if original.evidence_status in (S.SUPPORTED.value, S.CONTRADICTED.value) else 'interpretive_inference')
        return SupportFinding(**original.__dict__, support_level=level)
    if set(data)-{'claim_text', 'claim_type', 'evidence', 'contradictory_evidence', 'predicate'}:
        raise ClauseError('Invalid structural claim fields')
    predicate = data.get('predicate')
    if not isinstance(predicate, dict) or set(predicate) != {'field', 'value'}:
        raise ClauseError('Invalid structural predicate')
    field, value = predicate['field'], predicate['value']
    if field not in ('actor', 'action', 'beneficiary', 'trigger', 'exception', 'amount') or not isinstance(value, str) or not 1 <= len(value) <= 500:
        raise ClauseError('Unsupported structural predicate')
    base_data = {k: v for k, v in data.items() if k != 'predicate'}
    base_data['claim_type'] = 'inference'
    original = reasoning.assess(document, clauses, base_data, number)
    status, basis = original.evidence_status, original.analytical_basis
    expected = f'Source contains {field}: {value}'
    if (data.get('claim_text') == expected and len(original.evidence) == 1 and not original.contradictory_evidence
            and 'valid_source_span' not in original.missing_information and status != S.LEGAL.value):
        span = original.evidence[0]
        supported = False
        if value == span.quote:
            if field in ('actor', 'action', 'beneficiary'):
                supported = any(getattr(o.semantic_role, field).status not in ('unknown', 'ambiguous')
                                and span in getattr(o.semantic_role, field).evidence for o in duties)
            elif field in ('trigger', 'exception'):
                supported = any(span == c.evidence and c.relationship_type == field for c in conditions)
            elif field == 'amount':
                supported = any(span == m.evidence for m in financial)
        if supported:
            status, basis = S.SUPPORTED.value, 'Exact source field-expression presence only; role correctness, fulfilment and legal effect are unverified.'
    return SupportFinding(**{**original.__dict__, 'claim_type': 'structural_observation',
                             'evidence_status': status, 'analytical_basis': basis}, support_level='structural_support')
