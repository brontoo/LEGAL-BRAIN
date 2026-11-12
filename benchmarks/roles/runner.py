"""Same frozen inputs/labels for legacy and v2; offline predictions, not scripted roles."""
import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time
import tracemalloc
from unittest.mock import patch
from clause_intelligence import AnalysisRequest, Document, analyze
from clause_intelligence import parser
from clause_intelligence.evidence import validate_span
from clause_intelligence.schemas import EvidenceSpan
from .metrics import FIELDS, add, empty_counts, finalize, normalize
from clause_intelligence.review_priority import priority_for

# Presentation-only adapter for legacy's first action token. It never searches
# the rest of the sentence or supplies roles missing from legacy output.
LEGACY_ACTIONS = {
 'pay': 'pay', 'payable': 'pay', 'deliver': 'deliver', 'provide': 'provide', 'refund': 'refund', 'recover': 'refund',
 'disclose': 'disclose', 'terminate': 'terminate', 'assign': 'assign', 'transfer': 'transfer', 'complete': 'complete',
 'inspect': 'inspect', 'repair': 'repair', 'notify': 'notify', 'deduct': 'deduct', 'adjust': 'adjust', 'retain': 'retain',
 'return': 'return', 'reject': 'reject', 'appoint': 'appoint', 'solicit': 'solicit', 'resign': 'resign', 'withhold': 'withhold',
 'sign': 'sign', 'collect': 'collect', 'reimburse': 'reimburse', 'preserve': 'preserve',
 'سداد': 'pay', 'السداد': 'pay', 'دفع': 'pay', 'تسليم': 'deliver', 'تقديم': 'provide', 'استرداد': 'refund',
 'الافصاح': 'disclose', 'انهاء': 'terminate', 'التنازل': 'assign', 'نقل': 'transfer', 'اتمام': 'complete',
 'فحص': 'inspect', 'اصلاح': 'repair', 'اخطار': 'notify', 'خصم': 'deduct', 'تعديل': 'adjust', 'الاحتفاظ': 'retain',
 'رد': 'return', 'رفض': 'reject', 'استقطاب': 'solicit', 'الاستقالة': 'resign', 'حجز': 'withhold',
 'التوقيع': 'sign', 'تحصيل': 'collect', 'حفظ': 'preserve',
}


def projection(report, item, improved):
    conditions = {c['relationship_id']: c for c in report['conditions']}
    dates = {d['date_id']: d for d in report['dates']}
    if improved:
        role = item['semantic_role']
        return {'actor': role['actor']['value'], 'action': role['action']['value'], 'object': role['object']['value'],
                'beneficiary': role['beneficiary']['value'], 'modality': role['modality'], 'polarity': role['polarity'],
                'conditional': role['conditional'],
                'trigger': [conditions[k]['referenced_condition'] for k in role['trigger_ids']],
                'condition': [conditions[k]['referenced_condition'] for k in role['condition_ids']],
                'exception': [conditions[k]['referenced_condition'] for k in role['exception_ids']],
                'deadline': [dates[k]['expression'] for k in role['deadline_ids']]}
    first = (item['action'].split() or [''])[0].lower().strip('.,;')
    from clause_intelligence.classification import fold
    first = fold(first)
    if first.startswith('ب') and first[1:] in LEGACY_ACTIONS:
        first = first[1:]
    kind = item['kind']
    mode = {'mandatory': 'mandatory', 'conditional_obligation': 'mandatory', 'prohibited': 'prohibited',
            'right': 'permitted', 'discretionary_right': 'permitted', 'representation': 'representation',
            'statement_of_fact': 'fact', 'right_lapse': 'fact'}.get(kind, 'ambiguous')
    return {'actor': item['obligated_party'], 'action': LEGACY_ACTIONS.get(first, first or None),
            'object': item['subject'], 'beneficiary': item['beneficiary'], 'modality': mode,
            'polarity': 'negative' if kind == 'prohibited' else 'positive',
            'conditional': bool(item['trigger'] or item['conditions'] or any(
                conditions[k]['referenced_condition'].lower().startswith(('unless', 'ما لم')) for k in item['exceptions'])),
            'trigger': item['trigger'],
            'condition': [conditions[k]['referenced_condition'] for k in item['conditions'] if conditions[k]['relationship_type'] != 'trigger'],
            'exception': [conditions[k]['referenced_condition'] for k in item['exceptions']],
            'deadline': [dates[k]['expression'] for k in item['deadlines']]}


def expected(role):
    return {**role, 'actor': role['actor_value']}


def walk_spans(value):
    if isinstance(value, dict):
        if set(EvidenceSpan.__dataclass_fields__) <= set(value):
            yield EvidenceSpan(**{k: value[k] for k in EvidenceSpan.__dataclass_fields__})
        for item in value.values():
            yield from walk_spans(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_spans(item)


def evaluate(*, measure_memory=False, corpus_path=None):
    corpus_path = Path(corpus_path) if corpus_path else Path(__file__).with_name('corpus.json')
    directory = corpus_path.parent
    raw = corpus_path.read_bytes()
    manifest = json.loads((directory/'manifest.json').read_text())
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest['sha256']:
        raise ValueError('Frozen corpus digest mismatch')
    documents = json.loads(raw)['documents']
    aggregates = {mode: defaultdict(empty_counts) for mode in ('legacy', 'role_v2')}
    rows, span_checks, attacks = [], {}, {}
    times = defaultdict(list)
    memory = defaultdict(list)
    for doc in documents:
        source = Document(doc['document_id'], doc['text'], doc['version'])
        clauses = parser.parse(source)
        first = asdict(clauses[1].span)
        attack_claims = [
            {'claim_text': 'The transaction is completed.', 'claim_type': 'inference', 'evidence': [first]},
            {'claim_text': 'The provision is enforceable.', 'claim_type': 'legal_conclusion', 'evidence': [first]},
            {'claim_text': 'Invented source quotation.', 'claim_type': 'exact_quote', 'evidence': [{**first, 'quote': 'Invented source quotation.'}]},
            {'claim_text': first['quote'], 'claim_type': 'exact_quote', 'evidence': [{**first, 'version': 'wrong-version'}]},
        ]
        req = AnalysisRequest(source, language=doc['language'], claims=tuple(attack_claims))
        mode_errors = {}
        for mode in ('legacy', 'role_v2'):
            env = {'ENABLE_CLAUSE_ROLE_V2': str(mode == 'role_v2').lower(), 'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false',
                   'ENABLE_LEGAL_SKILLS': 'false', 'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'false'}
            with patch.dict(os.environ, env):
                start = time.perf_counter()
                report = analyze(req)
                times[mode].append((time.perf_counter()-start)*1000)
                if measure_memory:
                    tracemalloc.start()
                    analyze(req)
                    memory[mode].append(tracemalloc.get_traced_memory()[1])
                    tracemalloc.stop()
            spans = list(walk_spans(report))
            valid = sum(validate_span(source, clauses, s) for s in spans)
            previous = span_checks.setdefault(mode, {'valid': 0, 'total': 0})
            previous['valid'] += valid
            previous['total'] += len(spans)
            assessed = [f for f in report['findings'] if f['category'] == 'claim_assessment']
            rejected = sum(f['evidence_status'] not in ('SUPPORTED_BY_TEXT', 'CONTRADICTED_BY_TEXT') for f in assessed)
            previous = attacks.setdefault(mode, {'rejected': 0, 'total': 0})
            previous['rejected'] += rejected
            previous['total'] += len(assessed)
            if valid != len(spans) or rejected != len(assessed) or report['signature_approval'] != 'not_provided':
                raise AssertionError('Critical evidence/legal-safety gate failed')
            predictions = defaultdict(list)
            for item in report['obligations']:
                span = next(c['span'] for c in report['clauses'] if c['clause_id'] == item['source_clause'])
                predictions[(span['start'], span['end'])].append(projection(report, item, mode == 'role_v2'))
            errors = []
            for provision in doc['provisions']:
                gold = [expected(r) for r in provision['roles']]
                predicted = predictions.pop((provision['start'], provision['end']), [])
                for slot in range(max(len(gold), len(predicted))):
                    g, p = gold[slot] if slot < len(gold) else None, predicted[slot] if slot < len(predicted) else None
                    groups = ['all', doc['language'], 'category:'+doc['category']]
                    if provision['tags']:
                        groups += ['complex_or_negative'] + ['tag:'+tag for tag in provision['tags']]
                    mismatch = []
                    for group in groups:
                        mismatch = add(aggregates[mode][group], g, p)
                    if mismatch:
                        errors.append({'provision_start': provision['start'], 'slot': slot, 'fields': mismatch,
                                       'gold': {k: g.get(k) for k in FIELDS} if g else None, 'predicted': p,
                                       'kind': 'false_positive_record' if g is None else 'false_negative_record' if p is None else 'partial_role_error',
                                       'machine_review_priority': priority_for(mismatch), 'reviewer_adjudication': 'NOT_RUN'})
            # Segmentation errors outside gold boundaries remain false positives, never discarded.
            for boundary, predicted in predictions.items():
                for p in predicted:
                    for group in ('all', doc['language'], 'category:'+doc['category']):
                        add(aggregates[mode][group], None, p)
                    errors.append({'provision_start': boundary[0], 'kind': 'unmatched_boundary_false_positive', 'predicted': p})
            mode_errors[mode] = errors
        rows.append({'document_id': doc['document_id'], 'language': doc['language'], 'category': doc['category'],
                     'errors': mode_errors, 'legacy_error_slots': len(mode_errors['legacy']), 'v2_error_slots': len(mode_errors['role_v2'])})
    metrics = {mode: {group: finalize(values) for group, values in groups.items()} for mode, groups in aggregates.items()}
    for value in attacks.values():
        value['rate'] = value['rejected']/value['total']
    latency = {mode: {'mean_ms': sum(values)/len(values), 'max_ms': max(values),
                      'p95_ms': sorted(values)[int(.95*(len(values)-1))],
                      'peak_python_bytes': max(memory[mode]) if memory[mode] else None}
               for mode, values in times.items()}
    return {'schema_version': 'phase2c.shadow.results.v1', 'fixture_sha256': digest, 'documents': len(documents),
            'provisions': sum(len(d['provisions']) for d in documents), 'bilingual_documents': sum(d['language'] == 'bilingual' for d in documents),
            'tagged_adversarial_or_complex_provisions': sum(bool(p['tags']) for d in documents for p in d['provisions']),
            'gold_role_records': sum(len(p['roles']) for d in documents for p in d['provisions']),
            'matching': 'Exact provision start/end + extraction ordinal, one-to-one, no fuzzy or best-match pairing.',
            'metrics': metrics, 'evidence_span_checks': span_checks, 'unsupported_interpretation_rejection': attacks,
            'performance': latency, 'per_document': rows,
            'corrected_documents': [r['document_id'] for r in rows if r['v2_error_slots'] < r['legacy_error_slots']],
            'regressed_documents': [r['document_id'] for r in rows if r['v2_error_slots'] > r['legacy_error_slots']],
            'lawyer_evaluation': 'NOT_RUN', 'live_gemini': 'BLOCKED', 'live_supabase': 'BLOCKED',
            'provenance': 'Frozen engineering-authored synthetic shadow corpus; development-visible, no independent expert validation.'}


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--output', required=True)
    cli.add_argument('--memory', action='store_true')
    cli.add_argument('--corpus', help='Explicit separately authored corpus with sibling frozen manifest.json')
    args = cli.parse_args()
    result = evaluate(measure_memory=args.memory, corpus_path=args.corpus)
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('metrics', 'per_document')}, indent=2))
    print(json.dumps({mode: {group: values for group, values in metrics.items() if group in ('all', 'en', 'ar', 'bilingual')}
                      for mode, metrics in result['metrics'].items()}, indent=2))
