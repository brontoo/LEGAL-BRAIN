import os
import unittest
from unittest.mock import patch
from clause_intelligence import AnalysisRequest,analyze
from clause_intelligence.identity import equivalent
from clause_intelligence.roles_v2 import parties
from clause_intelligence.parser import parse


def report(text,precision=True):
    with patch.dict(os.environ,{'ENABLE_CLAUSE_ROLE_V2':'true','ENABLE_CLAUSE_PRECISION_V3':str(precision).lower()}):
        return analyze(AnalysisRequest.from_payload({'document_text':text}))


class Precision(unittest.TestCase):
    def test_definition_backed_beneficiary_has_separate_surface_and_identity(self):
        r=report('1 Orion Fictional LLC (the Seller).\n2 Buyer shall pay the Seller AED 1700.')
        identity=r['obligations'][0]['semantic_role']['beneficiary_identity']
        self.assertEqual('the Seller',identity['surface_mention'])
        self.assertEqual('Orion Fictional LLC',identity['canonical_name'])
        self.assertEqual('explicit_same_document_definition',identity['resolution_basis'])
        self.assertTrue(identity['definition_references'])

    def test_wrong_party_never_equivalent_based_on_shared_name_words(self):
        req=AnalysisRequest.from_payload({'document_text':'1 Orion Fictional East LLC (the Seller).\n2 Orion Fictional West LLC (the Buyer).'})
        cs=parse(req.document)
        self.assertFalse(equivalent('Seller','Buyer',req.document,cs,parties(cs)))

    def test_conflicting_aliases_remain_ambiguous(self):
        r=report('1 Orion Alpha Ltd (the Seller).\n2 Orion Beta Ltd (the Seller).\n3 Buyer shall pay Seller.')
        identity=r['obligations'][0]['semantic_role']['beneficiary_identity']
        self.assertEqual('ambiguous',identity['ambiguity_status'])
        self.assertIsNone(identity['canonical_entity_id'])

    def test_schedule_scope_not_automatically_collapsed(self):
        r=report('1 Orion Fictional LLC (the Seller).\nSchedule B: Separate instrument\n2 Buyer shall pay Seller.')
        self.assertEqual('ambiguous',r['obligations'][0]['semantic_role']['beneficiary_identity']['ambiguity_status'])
        self.assertIsNone(r['obligations'][0]['beneficiary'])

    def test_identical_names_across_documents_do_not_share_canonical_id(self):
        def run(identity):
            with patch.dict(os.environ,{'ENABLE_CLAUSE_ROLE_V2':'true','ENABLE_CLAUSE_PRECISION_V3':'true'}):
                r=analyze(AnalysisRequest.from_payload({'document_id':identity,'document_text':'1 Orion Fictional LLC (the Seller).\n2 Buyer shall pay Seller.'}))
            return r['obligations'][0]['semantic_role']['beneficiary_identity']['canonical_entity_id']
        self.assertNotEqual(run('doc-one'),run('doc-two'))

    def test_unseen_expense_and_request_object_classes(self):
        for text,expected in (('يلتزم الموكل برد التكاليف الإدارية.','reimburse'),
                              ('يلتزم الوكيل برد العروض المتأخرة.','reject'),
                              ('يلتزم المورد برد الوثائق الأصلية.','return')):
            with self.subTest(text=text):
                f=report('1 '+text)['obligations'][0]['semantic_role']
                self.assertEqual(expected,f['action']['value'])
                self.assertEqual('not_established',f['liability_status'])

    def test_response_preposition_and_diacritics_preserved(self):
        f=report('1 يلتزم الوكيل بِرَدّ على الإنذار.')['obligations'][0]['semantic_role']
        self.assertEqual('respond',f['action']['value'])
        self.assertIn('رَدّ',f['action']['evidence'][0]['quote'])

    def test_nominal_arabic_reply_recovers_original_source_span(self):
        f=report('1 يلتزم الوكيل بالرد على الإخطار.')['obligations'][0]['semantic_role']
        self.assertEqual('respond',f['action']['value'])

    def test_unresolved_amount_and_conflicting_objects_abstain(self):
        for text in ('يلتزم الوكيل برد المبلغ.','يلتزم الوكيل برد الطلب والمصروفات.'):
            f=report('1 '+text)['obligations'][0]['semantic_role']
            self.assertIsNone(f['action']['value'])
            self.assertEqual('ambiguous',f['action']['status'])

    def test_direct_object_recipient_and_scope_distinct(self):
        f=report('1 Company shall not disclose confidential records to any outsider for audit.')['obligations'][0]['semantic_role']
        self.assertEqual('confidential records',f['object']['value'])
        self.assertEqual('any outsider',f['recipient']['value'])
        self.assertEqual('for audit',f['scope_qualifier']['value'].strip())
        self.assertIsNone(f['beneficiary']['value'])

    def test_arabic_object_recipient_boundary(self):
        f=report('1 لا يجوز للشركة الإفصاح عن السجلات إلى جهات خارجية.')['obligations'][0]['semantic_role']
        self.assertEqual('السجلات',f['object']['value'])
        self.assertEqual('جهات خارجية',f['recipient']['value'].rstrip('.'))

    def test_destination_not_person_beneficiary(self):
        f=report('1 Supplier shall deliver records to the archive.')['obligations'][0]['semantic_role']
        self.assertIsNone(f['beneficiary']['value'])
        self.assertEqual('the archive',f['destination']['value'])

    def test_multiple_to_phrases_are_ambiguous(self):
        f=report('1 Company shall disclose records to any outsider to retain copies.')['obligations'][0]['semantic_role']
        self.assertEqual('ambiguous_prepositional_attachment',f['boundary_status'])

    def test_precision_flag_off_preserves_original_reading(self):
        f=report('1 يلتزم الموكل برد المصروفات.',precision=False)['obligations'][0]['semantic_role']
        self.assertEqual('return',f['action']['value'])
        self.assertNotIn('recipient',f)

    def test_new_flag_does_not_enable_role_v2(self):
        with patch.dict(os.environ,{'ENABLE_CLAUSE_ROLE_V2':'false','ENABLE_CLAUSE_PRECISION_V3':'true'}):
            r=analyze(AnalysisRequest.from_payload({'document_text':'1 Buyer shall pay Seller.'}))
        self.assertNotIn('role_analysis',r)

    def test_unchanged_gold_both_metrics_retained(self):
        from validation.benchmark import evaluate
        r=evaluate();old=r['modes']['role_v2'];new=r['modes']['precision_v3']
        self.assertEqual(118,old['strict_historical_value_metrics']['all']['full_correct'])
        self.assertEqual(121,new['strict_historical_value_metrics']['all']['full_correct'])
        self.assertEqual(131,new['equivalence_aware_metrics']['all']['full_correct'])
        self.assertAlmostEqual(.7222222222,new['strict_historical_value_metrics']['all']['beneficiary']['f1'])
        self.assertEqual(1,new['documentary_identity_accuracy']['all:beneficiary']['accuracy'])
        self.assertEqual(26,new['documentary_identity_accuracy']['all:beneficiary']['unresolved'])
