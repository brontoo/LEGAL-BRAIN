import json
import unittest
from pathlib import Path
from benchmarks.hybrid.metrics import score,aggregate
from benchmarks.hybrid.runner import vector,FIXTURE


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.labels={'a':{'grade':3,'status':'relevant_eligible'},'b':{'grade':2,'status':'relevant_eligible'},
                     'wrong':{'grade':3,'status':'relevant_ineligible'},'unknown':{'grade':3,'status':'relevant_unverified'}}
    def test_perfect_eligible_ranking(self):
        result=score(['a','b'],self.labels,2)
        for key in ('recall_at_k','precision_at_k','mrr','ndcg_at_k','hit_rate_at_k'):self.assertEqual(1.0,result[key])
    def test_ineligible_and_unverified_never_count_as_relevant(self):
        result=score(['wrong','unknown'],self.labels,2)
        self.assertEqual(0,result['recall_at_k']);self.assertEqual(0,result['ndcg_at_k'])
    def test_precision_denominator_is_k_even_for_short_lists(self):
        self.assertEqual(.25,score(['a'],self.labels,4)['precision_at_k'])
    def test_reciprocal_rank_and_false_negative(self):
        result=score(['wrong','a'],self.labels,2)
        self.assertEqual(.5,result['mrr']);self.assertEqual(['b'],result['false_negatives'])
    def test_fixture_has_100_independent_bilingual_cases_and_all_families(self):
        fixture=json.loads(FIXTURE.read_text())
        self.assertEqual(100,len(fixture['queries']));self.assertEqual(100,len({q['id'] for q in fixture['queries']}))
        self.assertEqual({'ar','en'},{q['language'] for q in fixture['queries']})
        self.assertEqual(5,len({q['family'] for q in fixture['queries']}))
        for q in fixture['queries']:
            self.assertEqual({'relevant_eligible','relevant_ineligible','relevant_unverified'},{l['status'] for l in q['labels'].values()})
            self.assertEqual('irrelevant',q['default_label']['status'])
    def test_synthetic_vectors_normalized_and_not_model_claim(self):
        v=vector(['family:contracts','topic:payment'])
        self.assertEqual(1024,len(v));self.assertAlmostEqual(1,sum(x*x for x in v))
        self.assertIn('NOT multilingual-e5',json.loads(FIXTURE.read_text())['semantic_model'])
    def test_fixture_builder_cannot_silently_overwrite_labels(self):
        source=Path('benchmarks/hybrid/build_fixture.py').read_text()
        self.assertIn('Refusing to overwrite reviewed benchmark labels',source)
