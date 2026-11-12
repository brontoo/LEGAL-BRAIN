"""Request-local, offline core; external interpretation/research are separately opt-in."""
from dataclasses import asdict, is_dataclass, replace
import time
import untrusted
from . import parser, classification, entities, obligations, conditions, terms, references, consistency
from . import risks, reasoning, evidence, playbook_adapter, model_assistance, research, diagnostics, config
from .schemas import AnalysisRequest, ClauseError, Finding, SupportStatus as S


def serializable(value):
    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serializable(v) for v in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def analyze(request: AnalysisRequest, *, model_invoke=None, external_search=None):
    started = time.perf_counter()
    clauses = classification.classify(parser.parse(request.document))
    parties = entities.extract(clauses)
    definitions = entities.defined_terms(clauses)
    relationships = conditions.extract(clauses, parties)
    money = terms.financial(clauses)
    dates = terms.dates(clauses, relationships)
    duties = obligations.extract(clauses, parties, relationships, dates)
    refs, cycles, duplicate_labels = references.resolve(clauses)
    relationships = tuple(replace(c, target_clauses=tuple(dict.fromkeys(
        target for ref in refs if ref.source_clause == c.source_clause
        and c.evidence.start <= ref.evidence.start < c.evidence.end for target in ref.target_clauses)))
        for c in relationships)
    if any(len(records) > config.MAX_RECORDS for records in (parties, definitions, relationships, money, dates, duties, refs)):
        raise ClauseError('Extraction exceeds analysis limits')
    conflicts = consistency.detect(clauses, duties, money, dates, definitions)
    issues, risk = risks.register(clauses, parties, refs, cycles, duplicate_labels, conflicts, request.language)
    # Narrow observation: the quotation appears. No arbitrary paraphrase is marked supported.
    observations = tuple(Finding(f'OBS-{i+1:04d}', 'source_observation', c.span.quote, 'source_observation', (c.span,),
                                 S.SUPPORTED.value, 'نص تعاقدي حرفي فقط؛ الأثر القانوني والتنفيذ والأصالة غير متحققة.' if request.language == 'ar' else
                                 'Exact contractual text only; legal effect, performance and authenticity unverified.')
                         for i, c in enumerate(clauses))
    assessments = tuple(reasoning.assess(request.document, clauses, item, i+1) for i, item in enumerate(request.claims))
    findings = observations + issues + assessments
    bridge = evidence.citation_bridge(request.document, clauses, findings)
    ledger = evidence.fact_ledger(findings)
    workflow = playbook_adapter.adapt(request, clauses, duties, findings)
    interpretation = model_assistance.interpret(request, clauses, model_invoke)
    external = research.research(request, external_search)
    injection = untrusted.scan_injection(request.document.text, locus='supplied_document')
    report = {
        'schema_version': 'phase2b.v1',
        'document': {'document_id': request.document.document_id, 'version': request.document.version,
                     'content_sha256': request.document.digest, 'offset_convention': 'unicode_code_points_end_exclusive',
                     'document_type': request.document_type, 'language': request.language,
                     'jurisdiction_context': asdict(request.jurisdiction), 'authenticity': 'not_verified'},
        'clauses': clauses, 'parties': parties, 'defined_terms': definitions, 'obligations': duties, 'financial_terms': money, 'dates': dates,
        'conditions': relationships, 'cross_references': refs, 'circular_clause_ids': cycles,
        'duplicate_labels': duplicate_labels, 'findings': findings, 'risk_assessment': risk,
        'citations': bridge, 'fact_ledger': {'count': len(ledger.facts), 'standing': 'uncertain', 'agreed_facts_created': False},
        'playbook': workflow, 'model_assistance': interpretation, 'external_research': external,
        'missing_information': ['document_completeness', 'performance_evidence', 'confirmed_trigger_dates', 'document_authenticity'],
        'legal_verification_requirements': ['applicable_jurisdiction', 'current_verified_authority', 'qualified_lawyer_review'],
        'human_review_status': 'pending', 'signature_approval': 'not_provided',
        'security': {'injection_candidates': len(injection), 'document_stored': False, 'source_instructions_executed': False},
        'diagnostics': diagnostics.summary(clauses, parties, duties, findings, (time.perf_counter()-started)*1000),
    }
    return serializable(report)
