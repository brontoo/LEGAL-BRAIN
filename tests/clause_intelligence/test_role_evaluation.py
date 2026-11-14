import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from benchmarks.roles.author_corpus import build
from benchmarks.roles.metrics import empty_counts, add, finalize
from benchmarks.roles.runner import evaluate
from benchmarks.roles.lawyer_review import agreement_math, evaluate_reviews, validate_review

HASH = 'cd7f039bda844d7165b66715369e632ca94ebd634895b20647013a4f19cbb682'


class ShadowEvaluation(unittest.TestCase):
    def test_frozen_gold_digest_and_authoring_source(self):
        raw = Path('benchmarks/roles/corpus.json').read_bytes()
        self.assertEqual(HASH, hashlib.sha256(raw).hexdigest())
        self.assertEqual(json.loads(raw), json.loads(json.dumps(build())))

    def test_minimum_new_corpus_composition_and_source_spans(self):
        docs = json.loads(Path('benchmarks/roles/corpus.json').read_text())['documents']
        self.assertEqual(30, len(docs))
        self.assertEqual(210, sum(len(d['provisions']) for d in docs))
        self.assertEqual(10, sum(d['language'] == 'bilingual' for d in docs))
        self.assertGreaterEqual(sum(bool(p['tags']) for d in docs for p in d['provisions']), 20)
        for d in docs:
            for p in d['provisions']:
                self.assertEqual(p['text'], d['text'][p['start']:p['end']])
                for role in p['roles']:
                    for span in role['spans'].values():
                        self.assertEqual(span['quote'], d['text'][span['start']:span['end']])

    def test_new_corpus_does_not_reuse_original_provisions(self):
        old = {c['text'] for d in json.loads(Path('benchmarks/clauses/fixture.json').read_text())['documents'] for c in d['clauses']}
        new = {c['text'] for d in build()['documents'] for c in d['provisions']}
        self.assertFalse(old & new)

    def test_partial_roles_do_not_count_as_full_tuples(self):
        count = empty_counts()
        add(count, {'actor': 'Buyer', 'action': 'pay', 'beneficiary': 'Seller'},
            {'actor': 'Buyer', 'action': 'pay', 'beneficiary': None})
        result = finalize(count)
        self.assertEqual(0, result['full_role_tuple_accuracy'])
        self.assertEqual(1, result['partial'])
        self.assertEqual(1, result['beneficiary']['fn'])
        self.assertEqual(1, result['actor_action_pair_accuracy'])

    def test_wrong_actor_counts_fp_and_fn_not_partial_identity_credit(self):
        count = empty_counts()
        add(count, {'actor': 'Buyer'}, {'actor': 'Seller'})
        result = finalize(count)
        self.assertEqual(1, result['actor']['fp'])
        self.assertEqual(1, result['actor']['fn'])
        self.assertEqual(0, result['actor']['f1'])

    def test_false_positive_record_cannot_disappear_in_set_dedup(self):
        count = empty_counts()
        add(count, None, {'actor': 'Buyer', 'action': 'pay'})
        add(count, None, {'actor': 'Buyer', 'action': 'pay'})
        result = finalize(count)
        self.assertEqual(2, result['actor']['fp'])
        self.assertEqual(2, result['slots'])

    def test_real_comparison_reports_languages_and_strict_safety(self):
        result = evaluate()
        self.assertEqual(HASH, result['fixture_sha256'])
        for mode in ('legacy', 'role_v2'):
            self.assertEqual({'all', 'en', 'ar', 'bilingual'}-result['metrics'][mode].keys(), set())
            self.assertEqual(result['evidence_span_checks'][mode]['valid'], result['evidence_span_checks'][mode]['total'])
            self.assertEqual(1, result['unsupported_interpretation_rejection'][mode]['rate'])
        self.assertGreater(result['metrics']['role_v2']['bilingual']['full_role_tuple_accuracy'],
                           result['metrics']['legacy']['bilingual']['full_role_tuple_accuracy'])
        self.assertGreater(result['metrics']['role_v2']['all']['beneficiary']['fn'], 0)
        self.assertEqual('NOT_RUN', result['lawyer_evaluation'])


class LawyerProtocol(unittest.TestCase):
    def test_no_annotations_no_agreement_or_approval(self):
        result = evaluate_reviews(corpus_sha256=HASH)
        self.assertEqual('NOT_RUN', result['status'])
        self.assertIsNone(result['agreement'])
        self.assertEqual('not_provided', result['legal_approval'])

    def test_empty_templates_never_count_as_expert_annotations(self):
        template = {'annotations': []}
        self.assertEqual('NOT_RUN', evaluate_reviews(template, template, corpus_sha256=HASH)['status'])

    def test_synthetic_and_unattested_records_rejected(self):
        for origin in ('synthetic', None):
            with self.assertRaises(ValueError):
                validate_review({'corpus_sha256': HASH, 'origin': origin, 'annotations': []}, HASH)

    def test_wrong_corpus_never_compared(self):
        with self.assertRaises(ValueError):
            validate_review({'corpus_sha256': 'wrong'}, HASH)

    def test_categorical_agreement_arithmetic_only_not_human_result(self):
        values = agreement_math(['x', 'x', 'y', 'y'], ['x', 'y', 'x', 'y'])
        self.assertEqual(.5, values['observed_agreement'])
        self.assertEqual(0, values['cohen_kappa'])
        self.assertIsNone(agreement_math(['x', 'x'], ['x', 'x'])['cohen_kappa'])

    def test_no_genuine_review_artifacts_or_invented_signatures(self):
        module = Path('benchmarks/roles/review_packet.py').read_text()
        self.assertIn("'reviewer_id': None", module)
        self.assertIn("'qualification_attested': False", module)
        self.assertNotIn('approved_for_signature', module)
