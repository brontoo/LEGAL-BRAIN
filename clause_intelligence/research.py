"""Explicit opt-in Phase 2A adapter. Contract text is never implicitly uploaded."""
from dataclasses import asdict


def research(request, search=None):
    if request.research_query is None:
        return {'status': 'not_requested', 'legal_research_gap': True, 'sources': []}
    from retrieval import config as retrieval_config
    if not retrieval_config.enabled():
        return {'status': 'hybrid_disabled', 'legal_research_gap': True, 'sources': []}
    if search is None:
        return {'status': 'unavailable', 'legal_research_gap': True, 'sources': []}
    from retrieval.context import from_payload
    from retrieval.schemas import RetrievalRequest
    from retrieval.schemas import AUTHORITY_CLASSES
    context = from_payload({'jurisdiction': asdict(request.jurisdiction), 'as_of': request.as_of})
    try:
        result = search(RetrievalRequest(request.research_query, 'legislation', context))
        # Already eligible candidates only; no alternate RPC or unfiltered fallback.
        sources = [{'source_class': c.provenance.source_class.value, 'identity': c.chunk_id,
                    'title': c.title, 'text': c.text, 'eligibility': asdict(c.eligibility),
                    'provenance': asdict(c.provenance), 'legal_applicability': 'requires_authority_verification'}
                   for c in result.candidates if c.family == 'legislation'
                   and c.provenance.source_class in AUTHORITY_CLASSES
                   and c.eligibility.decision != 'incompatible']
        return {'status': result.status, 'sources': sources, 'legal_research_gap': True,
                'note': 'Retrieved law still requires existing authority/application checks and lawyer review.'}
    except Exception:
        return {'status': 'unavailable', 'legal_research_gap': True, 'sources': []}
