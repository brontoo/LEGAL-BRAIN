import hashlib
import json
from pathlib import Path
import unittest
from benchmarks.clauses.build_fixture import build
from benchmarks.clauses.metrics import counts, scores
from benchmarks.clauses.runner import evaluate

FIXTURE = Path('benchmarks/clauses/fixture.json')
DIGEST = 'dbdeb162e1fe5ff2c97f81b0d76496c093af5ad0d0512ce398c35f9ac3fb0e13'


class Benchmark(unittest.TestCase):
    def test_frozen_annotations_have_not_changed_to_match_predictions(self):
        self.assertEqual(DIGEST, hashlib.sha256(FIXTURE.read_bytes()).hexdigest())
        self.assertEqual(json.loads(json.dumps(build())), json.loads(FIXTURE.read_text()))

    def test_minimum_document_clause_language_and_adversarial_coverage(self):
        fixture = json.loads(FIXTURE.read_text())
        self.assertEqual(20, len(fixture['documents']))
        self.assertEqual(120, sum(len(d['clauses'])-1 for d in fixture['documents']))
        self.assertGreaterEqual(sum(d['adversarial_or_incomplete'] for d in fixture['documents']), 10)
        self.assertEqual({'ar', 'en', 'bilingual'}, {d['language'] for d in fixture['documents']})

    def test_gold_offsets_and_unclassified_negative_examples(self):
        for doc in json.loads(FIXTURE.read_text())['documents']:
            for clause in doc['clauses']:
                self.assertEqual(clause['text'], doc['text'][clause['start']:clause['end']])
            self.assertTrue(doc['unsupported_conclusions'])
            self.assertTrue(doc['ambiguous_findings'])

    def test_metric_math_counts_false_positives_and_false_negatives(self):
        actual = scores(counts({'a', 'b'}, {'a', 'c', 'd'}))
        self.assertEqual(1/3, actual['precision'])
        self.assertEqual(.5, actual['recall'])
        self.assertEqual(.4, actual['f1'])
        self.assertIsNone(scores(counts(set(), set()))['precision'])

    def test_real_engine_fixture_metrics_and_strict_integrity(self):
        result = evaluate()
        self.assertEqual(DIGEST, result['fixture_sha256'])
        self.assertEqual(1, result['metrics']['all']['exact_evidence_span_validity'])
        self.assertEqual(140, result['unsupported_claim_rejection']['total'])
        self.assertEqual(1, result['unsupported_claim_rejection']['rate'])
        # Scores are diagnostic: retain actual errors instead of requiring fictional perfection.
        self.assertGreater(result['metrics']['all']['classification']['fp'], 0)
        self.assertGreater(result['metrics']['all']['classification']['fn'], 0)
        self.assertEqual(20, len(result['per_document']))

    def test_every_taxonomy_label_is_declared_without_using_engine_predictions(self):
        from clause_intelligence.classification import TAXONOMY
        labels = {category for d in json.loads(FIXTURE.read_text())['documents'] for c in d['clauses'] for category in c['categories']}
        self.assertEqual(set(TAXONOMY), labels)
