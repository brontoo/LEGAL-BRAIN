"""Run the real offline engine against frozen, independently authored annotations."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch
import os
from clause_intelligence import AnalysisRequest, analyze
from clause_intelligence.classification import TAXONOMY
from .metrics import counts, scores


def evaluate(fixture_path=None):
    path = Path(fixture_path) if fixture_path else Path(__file__).with_name('fixture.json')
    raw = path.read_bytes()
    fixture = json.loads(raw)
    aggregate = defaultdict(lambda: defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0}))
    rows, elapsed = [], []
    span_valid = span_total = unsupported_rejected = unsupported_total = exact_classes = total_classes = 0
    ref_correct = ref_total = class_tn = class_fp = 0
    by_language = defaultdict(lambda: {'span_valid': 0, 'span_total': 0, 'ref_correct': 0, 'ref_total': 0,
                                     'class_exact': 0, 'class_total': 0, 'class_tn': 0, 'class_fp': 0})
    for document in fixture['documents']:
        gold_span = document['clauses'][1]
        span = {'document_id': document['document_id'], 'version': document['version'],
                'content_sha256': hashlib.sha256(document['text'].encode()).hexdigest(), 'clause_id': 'C-0002',
                'start': gold_span['start'], 'end': gold_span['end'], 'quote': gold_span['text']}
        attacks = [
            {'claim_text': 'All duties have been performed.', 'claim_type': 'inference', 'evidence': [span]},
            {'claim_text': 'This is enforceable under applicable law.', 'claim_type': 'legal_conclusion', 'evidence': [span]},
            {'claim_text': 'A fabricated exact quotation.', 'claim_type': 'exact_quote',
             'evidence': [{**span, 'quote': 'A fabricated exact quotation.'}]},
            {'claim_text': span['quote'], 'claim_type': 'exact_quote', 'evidence': [{**span, 'version': 'unavailable-version'}]},
        ]
        req = AnalysisRequest.from_payload({'document_id': document['document_id'], 'document_version': document['version'],
                                          'document_text': document['text'], 'language': document['language'],
                                          'claims': [{'claim_text': claim, 'claim_type': 'legal_conclusion' if i == 0 else 'inference'}
                                                     for i, claim in enumerate(document['unsupported_conclusions'])] + attacks})
        started = time.perf_counter()
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'false', 'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'false',
                                    'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false'}):
            report = analyze(req)
        duration = (time.perf_counter()-started)*1000
        elapsed.append(duration)
        gold = document['clauses']
        actual = report['clauses']
        expected_spans = {(c['start'], c['end']) for c in gold}
        actual_spans = {(c['span']['start'], c['span']['end']) for c in actual}
        clause_index = {c['clause_id']: next((i for i, g in enumerate(gold) if (g['start'], g['end']) ==
                                            (c['span']['start'], c['span']['end'])), -1) for c in actual}
        # Category universe is clause span + taxonomy, so missed boundaries also miss classification.
        expected_labels = {(c['start'], c['end'], label) for c in gold for label in c['categories']}
        actual_labels = {(c['span']['start'], c['span']['end'], label) for c in actual for label in c['categories']}
        expected_entities = {c['entity'] for c in gold if c['entity']}
        actual_entities = {e['name'] for e in report['parties']}
        expected_duties = {(i, c['obligation']) for i, c in enumerate(gold) if c['obligation']}
        actual_duties = {(clause_index.get(o['source_clause'], -1), o['kind']) for o in report['obligations']}
        expected_refs = {(i, status, n) for i, c in enumerate(gold) for n, status in enumerate(c['references'])}
        actual_refs, ordinals = set(), defaultdict(int)
        for ref in report['cross_references']:
            i = clause_index.get(ref['source_clause'], -1)
            actual_refs.add((i, ref['status'], ordinals[i]))
            ordinals[i] += 1
        expected_conflicts = {tuple(sorted(pair)) for pair in document['potential_conflict_pairs']}
        actual_conflicts = set()
        for finding in report['findings']:
            if finding['category'] == 'potential_conflict':
                actual_conflicts.add(tuple(sorted({clause_index.get(s['clause_id'], -1) for s in finding['evidence']})))
        metrics = {'segmentation': (expected_spans, actual_spans), 'classification': (expected_labels, actual_labels),
                   'entities': (expected_entities, actual_entities), 'obligations': (expected_duties, actual_duties),
                   'references': (expected_refs, actual_refs), 'potential_conflicts': (expected_conflicts, actual_conflicts)}
        errors = {}
        for metric, (expected, predicted) in metrics.items():
            count = counts(expected, predicted)
            for group in ('all', document['language']):
                for key, value in count.items():
                    aggregate[group][metric][key] += value
            errors[metric] = {'false_positives': sorted(predicted-expected), 'false_negatives': sorted(expected-predicted)}
        for c in gold:
            matched = next((a for a in actual if (a['span']['start'], a['span']['end']) == (c['start'], c['end'])), None)
            exact = bool(matched and set(matched['categories']) == set(c['categories']))
            exact_classes += exact
            total_classes += 1
            by_language[document['language']]['class_exact'] += exact
            by_language[document['language']]['class_total'] += 1
            predicted = set(matched['categories']) if matched else set()
            absent = set(TAXONOMY)-set(c['categories'])
            tn, fp = len(absent-predicted), len(absent & predicted)
            class_tn += tn
            class_fp += fp
            by_language[document['language']]['class_tn'] += tn
            by_language[document['language']]['class_fp'] += fp
        # Validate every span in every nested report object, not just displayed findings.
        def visit(value):
            nonlocal span_total, span_valid
            if isinstance(value, dict):
                if set(('document_id', 'version', 'content_sha256', 'clause_id', 'start', 'end', 'quote')) <= set(value):
                    span_total += 1
                    valid = (value['document_id'] == document['document_id'] and value['version'] == document['version']
                             and value['content_sha256'] == req.document.digest and type(value['start']) is int
                             and 0 <= value['start'] < value['end'] <= len(document['text'])
                             and document['text'][value['start']:value['end']] == value['quote']
                             and any(a['clause_id'] == value['clause_id'] and a['span']['start'] <= value['start']
                                     < value['end'] <= a['span']['end'] for a in actual))
                    span_valid += valid
                    by_language[document['language']]['span_total'] += 1
                    by_language[document['language']]['span_valid'] += valid
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(report)
        for finding in report['findings']:
            if finding['category'] == 'claim_assessment':
                unsupported_total += 1
                unsupported_rejected += finding['evidence_status'] not in ('SUPPORTED_BY_TEXT', 'CONTRADICTED_BY_TEXT')
        rc, rt = len(expected_refs & actual_refs), len(expected_refs | actual_refs)
        ref_correct += rc
        ref_total += rt
        by_language[document['language']]['ref_correct'] += rc
        by_language[document['language']]['ref_total'] += rt
        if report['signature_approval'] != 'not_provided' or report['human_review_status'] != 'pending':
            raise AssertionError('Automatic legal approval detected')
        rows.append({'document_id': document['document_id'], 'language': document['language'], 'scenario': document['scenario'],
                     'errors': errors, 'elapsed_ms': duration})
    measured = {group: {metric: scores(count) for metric, count in metrics.items()} for group, metrics in aggregate.items()}
    for group in measured:
        stats = by_language[group] if group != 'all' else {'class_exact': exact_classes, 'class_total': total_classes,
                    'span_valid': span_valid, 'span_total': span_total, 'ref_correct': ref_correct, 'ref_total': ref_total,
                    'class_tn': class_tn, 'class_fp': class_fp}
        measured[group]['classification_exact_accuracy'] = stats['class_exact']/stats['class_total']
        measured[group]['exact_evidence_span_validity'] = stats['span_valid']/stats['span_total']
        measured[group]['cross_reference_resolution_accuracy'] = stats['ref_correct']/stats['ref_total'] if stats['ref_total'] else None
        measured[group]['classification_false_positive_rate'] = stats['class_fp']/(stats['class_fp']+stats['class_tn'])
    artifact = {'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'documents': len(rows),
                'annotated_provisions': sum(len(d['clauses'])-1 for d in fixture['documents']),
                'annotated_segments_including_titles': total_classes,
                'adversarial_or_incomplete_documents': sum(d['adversarial_or_incomplete'] for d in fixture['documents']),
                'mode': 'offline_deterministic_no_live_model', 'metrics': measured,
                'unsupported_claim_rejection': {'rejected': unsupported_rejected, 'total': unsupported_total,
                                                'rate': unsupported_rejected/unsupported_total},
                'evidence_span_checks': {'valid': span_valid, 'total': span_total},
                'latency_ms': {'mean': sum(elapsed)/len(elapsed), 'max': max(elapsed),
                               'p95': sorted(elapsed)[int(.95*(len(elapsed)-1))]}, 'per_document': rows,
                'limitations': ['Engineering-authored diagnostic fixture, not lawyer-adjudicated or statistically representative.',
                               'Extraction sets score clause-level obligation kind, not full semantic role accuracy.',
                               'References use exact clause/status/ordinal matches; accuracy is intersection/union.',
                               'No held-out corpus, model training, NLI validation or legal-quality claim.']}
    if span_valid != span_total or unsupported_rejected != unsupported_total:
        raise AssertionError('Strict evidence integrity or unsupported-claim acceptance failed')
    return artifact


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = evaluate()
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('per_document', 'metrics')}, indent=2))
    print(json.dumps(result['metrics'], indent=2))
