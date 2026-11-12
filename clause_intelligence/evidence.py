"""Exact structural grounding plus adapters to the established citation/fact machinery."""
from dataclasses import replace
from citations import Evidence, Citation, RefAllocator, verify_citations
from facts import Fact, FactLedger, Standing, assert_system_does_not_agree
from .schemas import ClauseError, EvidenceSpan


def subspan(clause, start, end):
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(clause.span.quote):
        raise ClauseError('Invalid evidence offsets')
    return replace(clause.span, start=clause.span.start + start, end=clause.span.start + end,
                   quote=clause.span.quote[start:end])


def validate_span(document, clauses, span):
    if not isinstance(span, EvidenceSpan):
        return False
    if (span.document_id, span.version, span.content_sha256) != (document.document_id, document.version, document.digest):
        return False
    if type(span.start) is not int or type(span.end) is not int or not 0 <= span.start < span.end <= len(document.text):
        return False
    clause = next((c for c in clauses if c.clause_id == span.clause_id), None)
    return bool(clause and clause.span.start <= span.start < span.end <= clause.span.end
                and document.text[span.start:span.end] == span.quote)


def from_payload(document, clauses, data):
    if not isinstance(data, dict) or set(data) != set(EvidenceSpan.__dataclass_fields__):
        raise ClauseError('Invalid evidence fields')
    try:
        span = EvidenceSpan(**data)
    except TypeError:
        raise ClauseError('Invalid evidence fields') from None
    if not validate_span(document, clauses, span):
        raise ClauseError('Evidence does not match supplied document version and clause')
    return span


def citation_bridge(document, clauses, findings):
    """Local refs use the host allocator/checker; no global collector and no law classification."""
    allocator = RefAllocator()
    items, mapping = [], {}
    for finding in findings:
        for span in finding.evidence + finding.contradictory_evidence:
            if not validate_span(document, clauses, span):
                raise ClauseError('Invalid generated evidence')
            if span not in mapping:
                ref = allocator.next_ref('contracts')
                mapping[span] = ref
                items.append(Evidence(ref, f'{document.digest}:{span.start}:{span.end}', document.document_id,
                                      span.quote, tool='contracts'))
    citations = [Citation(ref, span.quote) for span, ref in mapping.items()]
    outcome = verify_citations(citations, items, min_quote_chars=1)
    if outcome.rejected:
        raise ClauseError('Host citation verification rejected evidence')
    return {'source_class': 'contractual_evidence', 'verified_quotes': len(outcome.verified),
            'refs': [{'ref': ref, 'span': span} for span, ref in mapping.items()]}


def fact_ledger(findings):
    facts = tuple(Fact(f'clause.{i}', f.claim_text, f.evidence[0].document_id, f.evidence[0].clause_id,
                       '', 'document_analysis', Standing.UNCERTAIN, f.evidence[0].quote,
                       version=f.evidence[0].version) for i, f in enumerate(findings) if f.evidence)
    assert_system_does_not_agree(facts)
    return FactLedger(facts)
