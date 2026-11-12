import json
import os
import unittest
from dataclasses import asdict
from unittest.mock import Mock, patch
from clause_intelligence import AnalysisRequest, ClauseError, analyze
from clause_intelligence.evidence import validate_span
from clause_intelligence.schemas import EvidenceSpan
from benchmarks.roles.runner import walk_spans


def run(text, **fields):
    with patch.dict(os.environ, {'ENABLE_CLAUSE_ROLE_V2': 'true', 'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false'}):
        return analyze(AnalysisRequest.from_payload({'document_text': text, **fields}))


def role(text):
    return run('1 '+text)['obligations'][0]['semantic_role']


class SemanticRoles(unittest.TestCase):
    def test_buyer_action_beneficiary_and_amount(self):
        r = run('1 The Buyer shall pay the Seller AED 50,000.')
        f = r['obligations'][0]['semantic_role']
        self.assertEqual('The Buyer', f['actor']['value'])
        self.assertEqual('pay', f['action']['value'])
        self.assertEqual('the Seller', f['beneficiary']['value'])
        self.assertEqual('AED 50,000', f['object']['value'])
        self.assertEqual(['M-0001'], f['financial_ids'])

    def test_multiple_actors_remain_separate(self):
        r = run('1 Buyer shall pay Seller and Seller shall deliver the cartons.')
        self.assertEqual(['Buyer', 'Seller'], [o['obligated_party'] for o in r['obligations']])
        self.assertEqual(['pay', 'deliver'], [o['semantic_role']['action']['value'] for o in r['obligations']])

    def test_multiple_coordinated_actions_keep_same_evidenced_actor(self):
        r = run('1 Supplier must inspect and repair the crates.')
        self.assertEqual(2, len(r['obligations']))
        self.assertEqual(['Supplier', 'Supplier'], [o['obligated_party'] for o in r['obligations']])
        self.assertIsNone(r['obligations'][0]['semantic_role']['object']['value'])

    def test_noun_following_action_is_not_second_action(self):
        r = run('1 Seller shall complete the transfer.')
        self.assertEqual(1, len(r['obligations']))
        self.assertEqual('the transfer', r['obligations'][0]['subject'])

    def test_unknown_actor_not_invented_from_generic_prefix(self):
        f = role('The outstanding balance shall be payable after handover.')
        self.assertIsNone(f['actor']['value'])
        self.assertEqual('unknown', f['actor']['status'])

    def test_explicit_actor_and_defined_alias_distinct(self):
        self.assertEqual('explicit', role('Buyer must pay Seller.')['actor']['status'])
        r = run('1 Hush Mountain Ltd (the Buyer).\n2 Buyer must pay Seller.')
        f = r['obligations'][0]['semantic_role']
        self.assertEqual('from_definition', f['actor']['status'])
        self.assertEqual('Hush Mountain Ltd', f['actor']['value'])
        self.assertEqual(2, len(f['actor']['evidence']))

    def test_ambiguous_alias_returns_unknown_identity_with_evidence(self):
        r = run('1 Quiet Hill Ltd (the Buyer).\n2 Bright Peak Ltd (the Buyer).\n3 Buyer shall pay Seller.')
        f = r['obligations'][0]['semantic_role']
        self.assertIsNone(f['actor']['value'])
        self.assertEqual('ambiguous', f['actor']['status'])
        self.assertIn('actor_ambiguous', f['uncertainty'])

    def test_english_obligation_with_explicit_arabic_name(self):
        r = run('1 Buyer: شركة الأفق التجريبي\n2 شركة الأفق التجريبي shall pay Seller.')
        self.assertEqual('شركة الأفق التجريبي', r['obligations'][0]['obligated_party'])

    def test_arabic_negative_right_with_attached_preposition(self):
        f = role('لا يحق للمستأجر التنازل عن العقد دون موافقة خطية.')
        self.assertEqual('للمستأجر', f['actor']['value'])
        self.assertEqual(('prohibited', 'negative'), (f['modality'], f['polarity']))
        self.assertTrue(f['conditional'])

    def test_arabic_multiple_actors(self):
        r = run('1 يلتزم المشتري بالسداد ويلتزم المورد بتسليم القطع.')
        self.assertEqual(['المشتري', 'المورد'], [o['obligated_party'] for o in r['obligations']])

    def test_unrecognized_action_remains_unknown(self):
        f = role('Buyer shall quantum-annotate the register.')
        self.assertIsNone(f['action']['value'])
        self.assertIn('action_unknown', f['uncertainty'])

    def test_unclear_beneficiary_remains_unknown(self):
        f = role('Buyer shall pay whoever is designated later.')
        self.assertIsNone(f['beneficiary']['value'])

    def test_two_amounts_do_not_cross_actor_boundary(self):
        r = run('1 Buyer shall pay Seller AED 350 and Agent shall pay Client AED 900.')
        self.assertEqual([['M-0001'], ['M-0002']], [o['semantic_role']['financial_ids'] for o in r['obligations']])

    def test_deadline_is_not_grammatical_object(self):
        f = role('Supplier shall deliver the report within 9 business days after approval.')
        self.assertEqual('the report', f['object']['value'])
        self.assertTrue(f['deadline_ids'])

    def test_consequence_is_candidate_not_liability(self):
        f = role('Buyer shall pay promptly, failing which the agreed remedy applies.')
        self.assertEqual('candidate_consequence', f['consequence']['status'])
        self.assertEqual('not_established', f['liability_status'])


class NegationAndConditions(unittest.TestCase):
    def test_neither_party_is_prohibited_not_permission(self):
        f = role('Neither party may disclose confidential information.')
        self.assertEqual(('prohibited', 'negative'), (f['modality'], f['polarity']))

    def test_shall_not_is_not_positive_shall(self):
        self.assertEqual('negative', role('The Buyer shall not assign this Agreement.')['polarity'])

    def test_may_and_may_not_are_distinct(self):
        self.assertEqual('permitted', role('The Agent may terminate the agreement.')['modality'])
        self.assertEqual('prohibited', role('The Agent may not terminate the agreement.')['modality'])

    def test_not_required_until_is_negative_conditional_not_current_duty(self):
        f = role('The Seller is not required to complete the transfer until payment is received.')
        self.assertEqual('negative_entitlement', f['obligation_type'])
        self.assertTrue(f['conditional'])
        self.assertEqual('unknown', f['condition_fulfilment'])

    def test_no_commission_unless_is_condition_precedent(self):
        r = run('1 No commission shall be payable unless completion occurs.')
        self.assertEqual('condition_precedent', r['conditions'][0]['condition_role'])
        self.assertEqual('negative_entitlement', r['obligations'][0]['semantic_role']['modality'])
        self.assertIsNone(r['obligations'][0]['obligated_party'])

    def test_provided_that_and_unless_both_preserve_qualifiers(self):
        for text in ('The Company shall pay the fee, provided that the transaction completes.',
                     'The Company shall pay the fee unless the transaction is cancelled.'):
            f = role(text)
            self.assertTrue(f['conditional'])
            self.assertEqual('unknown', f['condition_fulfilment'])

    def test_arabic_all_mandated_negation_constructions(self):
        for text in ('لا يجوز لأي من الطرفين الإفصاح عن المعلومات السرية.',
                     'لا يستحق الوسيط العمولة إلا بعد إتمام الصفقة.',
                     'لا يلتزم البائع بنقل الملكية قبل استلام كامل الثمن.',
                     'لا يحق للمستأجر التنازل عن العقد دون موافقة خطية.',
                     'لا تعتبر المبالغ مستحقة ما لم يتم التسليم.'):
            with self.subTest(text=text):
                f = role(text)
                self.assertEqual('negative', f['polarity'])
                self.assertNotEqual('permitted', f['modality'])

    def test_arabic_positive_right_obligation_and_lapse(self):
        self.assertEqual('mandatory', role('يلتزم المشتري بسداد الثمن.')['modality'])
        self.assertEqual('permitted', role('يحق للمؤجر إنهاء العقد وفقاً للشروط المحددة.')['modality'])
        f = role('يسقط الحق في المطالبة عند تحقق الشرط المنصوص عليه.')
        self.assertEqual('lapse', f['action']['value'])
        self.assertTrue(f['conditional'])

    def test_unclear_not_only_and_double_negation_abstain(self):
        for text in ('Buyer may not only inspect the goods.', 'Buyer shall not fail to pay Seller.'):
            with self.subTest(text=text):
                self.assertEqual('ambiguous', role(text)['polarity'])

    def test_exception_preserves_nested_trigger_scope(self):
        r = run('1 Client may reject goods unless damage occurred after handover.')
        f = r['obligations'][0]['semantic_role']
        self.assertFalse(f['trigger_ids'])
        self.assertEqual('unless damage occurred after handover', r['conditions'][0]['referenced_condition'])
        self.assertEqual(r['conditions'][0]['relationship_id'], r['conditions'][1]['parent_relationship'])

    def test_two_actors_do_not_inherit_each_others_postposed_trigger(self):
        r = run('1 Buyer shall pay after invoice receipt and Seller shall deliver after clearance.')
        self.assertEqual(['after invoice receipt', 'after clearance'], [o['trigger'] for o in r['obligations']])

    def test_first_actor_exception_not_attached_to_second(self):
        r = run('1 Buyer shall pay unless disputed and Seller shall deliver the report.')
        self.assertTrue(r['obligations'][0]['semantic_role']['exception_ids'])
        self.assertFalse(r['obligations'][1]['semantic_role']['exception_ids'])
        self.assertFalse(r['obligations'][1]['semantic_role']['conditional'])

    def test_permission_inside_exception_is_not_independent_right(self):
        r = run('1 Buyer shall pay unless Seller may cancel under the agreed terms.')
        self.assertEqual(1, len(r['obligations']))
        self.assertEqual('Buyer', r['obligations'][0]['obligated_party'])

    def test_reservation_of_rights_is_not_new_condition(self):
        r = run('1 Agent shall preserve records without prejudice to existing rights.')
        self.assertFalse(r['obligations'][0]['semantic_role']['conditional'])
        self.assertEqual('reservation_of_rights', r['conditions'][0]['condition_role'])

    def test_carve_out_does_not_turn_prohibition_into_permission(self):
        r = run('1 Company shall not disclose records except its professional advisers.')
        f = r['obligations'][0]['semantic_role']
        self.assertEqual('prohibited', f['modality'])
        self.assertTrue(f['exception_ids'])

    def test_condition_subsequent_never_assumed_occurred(self):
        r = run('1 The right lapses upon revocation.')
        self.assertEqual('condition_subsequent', r['conditions'][0]['condition_role'])
        self.assertEqual('unknown', r['conditions'][0]['condition_status'])

    def test_extended_word_deadline_no_calculation(self):
        r = run('1 Tenant shall pay within twenty business days after invoice receipt.')
        self.assertEqual(20, r['dates'][0]['amount'])
        self.assertEqual('working', r['dates'][0]['day_basis'])
        self.assertIsNone(r['dates'][0]['resolved_date'])


class GroundingAndAlignment(unittest.TestCase):
    def test_unicode_diacritics_combining_and_non_bmp_spans(self):
        req = AnalysisRequest.from_payload({'document_text': '1 📄 يَلْتَزِم المشتري بسداد الثمن.\n2 Buyer shall pay e\u0301 fees.'})
        with patch.dict(os.environ, {'ENABLE_CLAUSE_ROLE_V2': 'true'}):
            r = analyze(req)
        from clause_intelligence.parser import parse
        self.assertTrue(all(validate_span(req.document, parse(req.document), s) for s in walk_spans(r)))

    def test_structural_predicate_only_supports_fixed_narrow_presence(self):
        text = '1 Buyer shall pay Seller.'
        r = run(text)
        span = r['obligations'][0]['semantic_role']['action']['evidence'][0]
        claim = {'claim_text': 'Source contains action: pay', 'claim_type': 'structural_observation',
                 'predicate': {'field': 'action', 'value': 'pay'}, 'evidence': [span]}
        result = run(text, claims=[claim])
        f = result['findings'][-1]
        self.assertEqual('SUPPORTED_BY_TEXT', f['evidence_status'])
        self.assertEqual('structural_support', f['support_level'])
        self.assertEqual('not_assessed', f['legal_applicability'])

    def test_structural_field_cannot_verify_arbitrary_claim(self):
        text = '1 Buyer shall pay Seller.'
        span = run(text)['obligations'][0]['semantic_role']['action']['evidence'][0]
        f = run(text, claims=[{'claim_text': 'The debt is overdue.', 'claim_type': 'structural_observation',
                 'predicate': {'field': 'action', 'value': 'pay'}, 'evidence': [span]}])['findings'][-1]
        self.assertNotEqual('SUPPORTED_BY_TEXT', f['evidence_status'])

    def test_contrary_evidence_never_ignored(self):
        text = '1 Buyer shall pay Seller.'
        span = run(text)['obligations'][0]['semantic_role']['action']['evidence'][0]
        f = run(text, claims=[{'claim_text': 'Source contains action: pay', 'claim_type': 'structural_observation',
                 'predicate': {'field': 'action', 'value': 'pay'}, 'evidence': [span], 'contradictory_evidence': [span]}])['findings'][-1]
        self.assertEqual('AMBIGUOUS', f['evidence_status'])

    def test_wrong_version_and_hash_do_not_support_structural_predicate(self):
        text = '1 Buyer shall pay Seller.'
        span = run(text)['obligations'][0]['semantic_role']['action']['evidence'][0]
        for changes in ({'version': 'other'}, {'content_sha256': '0'*64}, {'document_id': 'another'}, {'quote': 'paid'}):
            f = run(text, claims=[{'claim_text': 'Source contains action: pay', 'claim_type': 'structural_observation',
                     'predicate': {'field': 'action', 'value': 'pay'}, 'evidence': [{**span, **changes}]}])['findings'][-1]
            self.assertEqual('INSUFFICIENT_EVIDENCE', f['evidence_status'])

    def test_no_legal_enforceability_approval(self):
        r = run('1 Penalty AED 44,000.', claims=[{'claim_text': 'This penalty is enforceable.', 'claim_type': 'legal_conclusion'}])
        self.assertEqual('REQUIRES_LEGAL_VERIFICATION', r['findings'][-1]['evidence_status'])
        self.assertEqual('pending', r['human_review_status'])

    def test_explicit_parallel_markers_allow_divergence_candidate(self):
        r = run('1 AR version Clause 8: لا يجوز للشركة الإفصاح.\n2 EN version Clause 8: Company may disclose.', language='bilingual')
        alignment = r['role_analysis']['language_alignments'][0]
        self.assertEqual('divergence_candidate', alignment['status'])
        self.assertIn('polarity', alignment['dimensions'])
        self.assertEqual(2, len(alignment['evidence']))

    def test_no_markers_no_fabricated_alignment(self):
        r = run('1 Buyer shall pay AED 800.\n2 يلتزم المشتري بسداد ٩٠٠ درهم.', language='bilingual')
        self.assertFalse(r['role_analysis']['language_alignments'])

    def test_missing_or_repeated_marker_is_uncertain(self):
        r = run('1 AR version Clause 8: النص.\n2 EN version Clause 9: Other wording.', language='bilingual')
        self.assertTrue(all(a['status'] == 'alignment_uncertain' for a in r['role_analysis']['language_alignments']))

    def test_amount_and_deadline_divergence_not_precedence(self):
        r = run('1 AR version Clause 3: وديعة ٨٠٠ درهم خلال ٩ أيام.\n2 EN version Clause 3: Deposit AED 900 within 19 days.', language='bilingual')
        a = r['role_analysis']['language_alignments'][0]
        self.assertIn('amount', a['dimensions'])
        self.assertIn('deadline', a['dimensions'])
        self.assertNotIn('prevailing_language', a)

    def test_same_obligation_different_period_is_potential_conflict(self):
        r = run('1 Buyer shall pay the fee within 7 days after invoice receipt.\n2 Buyer shall pay the fee within 17 days after invoice receipt.')
        conflicts = [f for f in r['findings'] if f['category'] == 'potential_conflict']
        self.assertEqual(1, len(conflicts))
        self.assertEqual('AMBIGUOUS', conflicts[0]['evidence_status'])

    def test_different_parties_triggers_scopes_currency_or_exception_abstain(self):
        first = '1 Buyer shall pay the fee within 7 days after invoice receipt.\n2 '
        for second in ('Seller shall pay the fee within 17 days after invoice receipt.',
                       'Buyer shall pay the fee within 17 days after completion.',
                       'Buyer shall pay the fee within 17 days after invoice receipt unless disputed.'):
            self.assertFalse(any(f['category'] == 'potential_conflict' for f in run(first+second)['findings']))
        r = run('1 Liability cap USD 800.\n2 Liability cap AED 900.')
        self.assertFalse(any(f['category'] == 'potential_conflict' for f in r['findings']))

    def test_amendment_qualifier_requires_precedence_review(self):
        r = run('1 Amendment replaces earlier period.\n2 Buyer shall pay within 7 days.\n3 Buyer shall pay within 17 days.')
        self.assertTrue(r['role_analysis']['comparison_diagnostics']['amendment_or_precedence_review_required'])
        self.assertFalse(any(f['category'] == 'potential_conflict' for f in r['findings']))

    def test_missing_schedule_is_gap_not_invented_content(self):
        r = run('1 Buyer shall pay subject to Schedule W.')
        self.assertEqual('unavailable_schedule', r['cross_references'][0]['status'])
        self.assertTrue(any(f['category'] == 'evidence_gap' for f in r['findings']))

    def test_legacy_mode_preserves_known_behavior_and_response_shape(self):
        with patch.dict(os.environ, {'ENABLE_CLAUSE_ROLE_V2': 'false'}):
            r = analyze(AnalysisRequest.from_payload({'document_text': '1 Neither party may disclose records.'}))
        self.assertEqual('discretionary_right', r['obligations'][0]['kind'])
        self.assertNotIn('semantic_role', r['obligations'][0])
        self.assertNotIn('role_analysis', r)
        self.assertEqual('phase2b.v1', r['schema_version'])
