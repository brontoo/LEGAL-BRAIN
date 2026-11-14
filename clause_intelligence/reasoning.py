"""Quotation presence never proves arbitrary interpretations or legal enforceability."""
from .schemas import ClauseError, Finding, SupportStatus as S
from .evidence import from_payload
from authority import asserted_without_source

LEGAL_CUES = ('enforceab', 'invalid under', 'liable under', 'applicable law', 'قابل للتنفيذ', 'باطل', 'نافذ قانونا', 'يستحق قانونا')


def assess(document, clauses, data, number=1):
    allowed = {'claim_text', 'claim_type', 'evidence', 'contradictory_evidence'}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ClauseError('Invalid claim fields')
    text, kind = data.get('claim_text'), data.get('claim_type', 'inference')
    if not isinstance(text, str) or not 1 <= len(text) <= 1200:
        raise ClauseError('Invalid claim text')
    if kind not in ('exact_quote', 'text_observation', 'inference', 'legal_conclusion', 'denies_quotation', 'not_assessed'):
        raise ClauseError('Invalid claim type')
    spans, contrary = [], []
    invalid = False
    for key, target in (('evidence', spans), ('contradictory_evidence', contrary)):
        raw = data.get(key, [])
        if not isinstance(raw, list) or len(raw) > 6:
            raise ClauseError('Invalid claim evidence list')
        for item in raw:
            try:
                target.append(from_payload(document, clauses, item))
            except ClauseError:
                invalid = True
    legal = kind == 'legal_conclusion' or any(cue in text.lower() for cue in LEGAL_CUES) or bool(asserted_without_source(text))
    status, basis = S.INSUFFICIENT, 'No semantic entailment has been established.'
    missing = []
    if invalid:
        basis = 'One or more evidence spans were rejected; an invalid quote cannot verify a claim.'
        missing.append('valid_source_span')
    elif kind == 'not_assessed':
        status, basis = S.NOT_ASSESSED, 'Assessment was not requested.'
    elif legal:
        status, basis = S.LEGAL, 'Contract wording alone cannot establish enforceability or applicable law.'
    elif kind == 'denies_quotation' and text in ('The cited clause does not contain the quoted text.', 'البند المشار إليه لا يتضمن النص المقتبس.') and spans:
        status, basis = S.CONTRADICTED, 'The exact supplied quotation is present in the cited clause; only its alleged absence is contradicted.'
    elif kind in ('exact_quote', 'text_observation') and len(spans) == 1 and text == spans[0].quote and not contrary:
        status, basis = S.SUPPORTED, 'Narrow quotation-presence observation only; interpretation and truth are not verified.'
    elif spans and contrary:
        status, basis = S.AMBIGUOUS, 'Competing supplied evidence requires interpretation; neither reading is automatically verified.'
    elif spans:
        status, basis = S.AMBIGUOUS, 'Quotation is present, but its support for the proposed interpretation is unverified.'
    if not spans:
        missing.append('supporting_documentary_evidence')
    return Finding(f'CLAIM-{number:04d}', 'claim_assessment', text, kind, tuple(spans), status.value, basis,
                   tuple(contrary), tuple(missing), ('verified_applicable_authority', 'qualified_lawyer_review') if legal else ())
