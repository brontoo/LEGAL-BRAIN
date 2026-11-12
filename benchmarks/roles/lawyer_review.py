"""Supplied-review validation and disagreement arithmetic. Never invent reviewers."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from clause_intelligence.schemas import ClauseError, EvidenceSpan
from clause_intelligence.evidence import validate_span
from clause_intelligence.review_priority import ERROR_TAXONOMY

REVIEW_FIELDS = ('actor', 'action', 'beneficiary', 'object', 'modality', 'polarity', 'conditions', 'exceptions',
                 'trigger', 'deadline', 'interpretation_support', 'legal_applicability', 'error_severity', 'approval')


def agreement_math(left, right):
    """Pure categorical arithmetic; not an assertion that reviewers actually exist."""
    if len(left) != len(right) or not left:
        raise ValueError('Agreement requires equal nonempty label sequences')
    n = len(left)
    observed = sum(a == b for a, b in zip(left, right))/n
    ca, cb = Counter(left), Counter(right)
    expected = sum(ca[key]*cb[key] for key in ca.keys() | cb.keys())/(n*n)
    return {'items': n, 'observed_agreement': observed, 'expected_agreement': expected,
            'cohen_kappa': (observed-expected)/(1-expected) if expected < 1 else None}


def validate_review(review, corpus_sha256, cases=None):
    if not isinstance(review, dict) or review.get('corpus_sha256') != corpus_sha256:
        raise ValueError('Reviewer corpus/version mismatch')
    if review.get('origin') != 'human_supplied' or review.get('qualification_attested') is not True or review.get('independence_attested') is not True:
        raise ValueError('Independent qualified human-supplied annotations are required; attestations are not independently verified credentials')
    reviewer = review.get('reviewer_id')
    if not isinstance(reviewer, str) or not 1 <= len(reviewer) <= 80:
        raise ValueError('Reviewer identifier required')
    items = review.get('annotations')
    if not isinstance(items, list) or not items:
        raise ValueError('No human annotations supplied')
    by_unit = {}
    for item in items:
        if not isinstance(item, dict) or set(item)-{'case_id', 'unit_id', 'field', 'label', 'evidence', 'notes'}:
            raise ValueError('Invalid annotation fields')
        if item.get('field') not in REVIEW_FIELDS or not isinstance(item.get('label'), str) or len(item['label']) > 1200:
            raise ValueError('Invalid annotation label')
        if not all(isinstance(item.get(k), str) and 1 <= len(item[k]) <= 80 for k in ('case_id', 'unit_id')):
            raise ValueError('Annotation identity required')
        unit = (item['case_id'], item['unit_id'], item['field'])
        if unit in by_unit:
            raise ValueError('Duplicate reviewer unit')
        by_unit[unit] = item
        if cases is not None:
            if item['case_id'] not in cases:
                raise ValueError('Unknown review case')
            document, clauses = cases[item['case_id']]
            evidence = item.get('evidence', [])
            if not isinstance(evidence, list) or len(evidence) > 6:
                raise ValueError('Invalid reviewer evidence list')
            from clause_intelligence.evidence import from_payload
            for span in evidence:
                from_payload(document, clauses, span)
            if item['field'] in ('actor', 'action', 'beneficiary', 'conditions', 'exceptions', 'trigger', 'deadline') and item['label'] not in ('unknown', 'not_present', 'ambiguous') and not evidence:
                raise ValueError('Positive documentary role annotation requires exact evidence')
    return by_unit


def evaluate_reviews(first=None, second=None, *, corpus_sha256, cases=None):
    if not first or not second or not first.get('annotations') or not second.get('annotations'):
        return {'status': 'NOT_RUN', 'reason': 'Two actual independent lawyer annotation sets have not been supplied.',
                'agreement': None, 'disagreements': [], 'legal_approval': 'not_provided'}
    a, b = validate_review(first, corpus_sha256, cases), validate_review(second, corpus_sha256, cases)
    if first['reviewer_id'] == second['reviewer_id']:
        raise ValueError('Reviewers must be distinct')
    common = sorted(a.keys() & b.keys())
    if not common:
        return {'status': 'INSUFFICIENT_OVERLAP', 'agreement': None, 'disagreements': [], 'legal_approval': 'not_provided'}
    disagreements = [{'case_id': u[0], 'unit_id': u[1], 'field': u[2], 'first_label': a[u]['label'], 'second_label': b[u]['label'],
                       'status': 'awaiting_adjudication'} for u in common if a[u]['label'] != b[u]['label']]
    per_field = {}
    for field in REVIEW_FIELDS:
        units = [u for u in common if u[2] == field]
        if units:
            per_field[field] = agreement_math([a[u]['label'] for u in units], [b[u]['label'] for u in units])
    # Never pool actor names, legal support and severity into a meaningless single kappa.
    return {'status': 'SUPPLIED_REVIEWS_COMPARED', 'common_units': len(common),
            'annotation_union': len(a.keys() | b.keys()), 'agreement_by_field': per_field,
            'disagreements': disagreements, 'qualification_status': 'reviewer_attestation_not_independently_verified',
            'legal_approval': 'not_provided'}


def adjudicate(disagreement, decision, *, first_reviewer, second_reviewer, document, clauses):
    if not isinstance(decision, dict) or set(decision) != {'adjudicator_id', 'label', 'reason', 'evidence'}:
        raise ValueError('Invalid adjudication fields')
    reviewer = decision['adjudicator_id']
    if not isinstance(reviewer, str) or not reviewer.strip() or reviewer in (first_reviewer, second_reviewer):
        raise ValueError('A distinct adjudicator is required')
    if not isinstance(decision['reason'], str) or not 20 <= len(decision['reason']) <= 2000 or not isinstance(decision['label'], str):
        raise ValueError('A bounded reasoned adjudication is required')
    from clause_intelligence.evidence import from_payload
    evidence = decision['evidence']
    if not isinstance(evidence, list) or not evidence or len(evidence) > 6:
        raise ValueError('Adjudication requires exact source evidence')
    for span in evidence:
        from_payload(document, clauses, span)
    return {'original_disagreement': disagreement, 'adjudication': decision, 'status': 'recorded_human_adjudication',
            'legal_approval': 'not_provided'}
