import asyncio
from dataclasses import replace
import itertools
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests import fake_deps
fake_deps.install()
import main
import legal_agent
from citations import CITATIONS_BEGIN, CITATIONS_END
from clause_intelligence import AnalysisRequest, analyze
from clause_intelligence import research
from clause_intelligence.playbook_adapter import SUPPORTED
from tests.retrieval.helpers import Client, row, VECTOR
from retrieval.engine import HybridRetrievalEngine


class FakeRequest:
    def __init__(self, payload=None, raw=None):
        self.body = raw if raw is not None else json.dumps(payload).encode()

    async def stream(self):
        for i in range(0, len(self.body), 1200):
            yield self.body[i:i+1200]


def request(**options):
    return AnalysisRequest.from_payload({'document_text': '1 Supplier shall pay AED 500 after completion.', **options})


class Integration(unittest.TestCase):
    def setUp(self):
        fake_deps.reset()
        legal_agent._model = None
        legal_agent._supabase = None

    def test_all_eight_flag_combinations_generation_and_clause_endpoint(self):
        for skills, hybrid, clause in itertools.product((False, True), repeat=3):
            with self.subTest(skills=skills, hybrid=hybrid, clause=clause):
                fake_deps.reset()
                source = row(family='contracts', text='يلتزم المورد بتقديم تقرير شهري عن الخدمات المتفق عليها.')
                for rpc in ('match_legal_contracts', 'hybrid_semantic_v1', 'hybrid_lexical_v1'):
                    fake_deps.FAKE_SUPABASE.set_rows(rpc, [source])
                fake_deps.AGENT_SCRIPT = [{'tool': 'search_contract_clauses', 'args': {'query': 'review agreement'}},
                     {'content': source['chunk_content']+f'\n{CITATIONS_BEGIN}\nC1 :: تقديم تقرير شهري عن الخدمات المتفق عليها\n{CITATIONS_END}'}]
                env = {'ENABLE_LEGAL_SKILLS': str(skills).lower(), 'ENABLE_HYBRID_LEGAL_RETRIEVAL': str(hybrid).lower(),
                       'ENABLE_CLAUSE_INTELLIGENCE': str(clause).lower(), 'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false'}
                async def run():
                    response = await main.generate(main.GenerateRequest(prompt='Review this agreement', doc_type='agreement'))
                    events = [json.loads(c.removeprefix('data: ').strip()) async for c in response.content]
                    return response, {event['type']: event for event in events}
                with patch.dict(os.environ, env), patch.object(main, 'API_TOKEN', 'fixture-token'):
                    response, frames = asyncio.run(run())
                    self.assertTrue(frames['citations']['report']['verified'])
                    self.assertEqual(skills, 'skill_diagnostics' in frames['done'])
                    for kind in ('review', 'revision', 'authority', 'facts', 'done'):
                        self.assertIn(kind, frames)
                    calls = [name for name, _ in fake_deps.FAKE_SUPABASE.calls]
                    self.assertEqual(hybrid, 'hybrid_semantic_v1' in calls)
                    count = len(calls)
                    if clause:
                        report = asyncio.run(main.analyze_clauses_endpoint(FakeRequest({'document_text': '1 Supplier shall pay.'})))
                        self.assertEqual('pending', report['human_review_status'])
                        self.assertEqual(count, len(fake_deps.FAKE_SUPABASE.calls))
                    else:
                        with self.assertRaises(main.HTTPException) as error:
                            asyncio.run(main.analyze_clauses_endpoint(FakeRequest({'document_text': '1 Supplier shall pay.'})))
                        self.assertEqual(404, error.exception.status_code)

    def test_existing_token_dependency_attached(self):
        registered = [options for _, path, _, options in main.app.routes if path == '/analyze/clauses']
        self.assertEqual([[main.require_token]], [r['dependencies'] for r in registered])

    def test_new_endpoint_requires_configured_token_even_in_development(self):
        with patch.dict(os.environ, {'ENABLE_CLAUSE_INTELLIGENCE': 'true'}), patch.object(main, 'API_TOKEN', ''):
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.analyze_clauses_endpoint(FakeRequest({'document_text': 'Text'})))
        self.assertEqual(503, error.exception.status_code)

    def test_malformed_json_never_echoes_document(self):
        with patch.dict(os.environ, {'ENABLE_CLAUSE_INTELLIGENCE': 'true'}), patch.object(main, 'API_TOKEN', 'fixture'):
            for raw in (b'PRIVATE_SECRET', b'{"document_text": false}', b'{"path":"/etc/passwd"}', b'[]'):
                with self.assertRaises(main.HTTPException) as error:
                    asyncio.run(main.analyze_clauses_endpoint(FakeRequest(raw=raw)))
                self.assertEqual(400, error.exception.status_code)
                self.assertNotIn('PRIVATE_SECRET', error.exception.detail)

    def test_streamed_request_size_bounded(self):
        with patch.dict(os.environ, {'ENABLE_CLAUSE_INTELLIGENCE': 'true'}), patch.object(main, 'API_TOKEN', 'fixture'):
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.analyze_clauses_endpoint(FakeRequest(raw=b'x'*650001)))
        self.assertEqual(413, error.exception.status_code)

    def test_core_never_contacts_model_or_retrieval_without_explicit_requests(self):
        model, search = Mock(), Mock()
        with patch.dict(os.environ, {'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'true', 'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'true'}):
            analyze(request(), model_invoke=model, external_search=search)
        model.assert_not_called()
        search.assert_not_called()

    def test_model_endpoint_blocks_prompt_tracing_before_provider_call(self):
        env = {'ENABLE_CLAUSE_INTELLIGENCE': 'true', 'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'true',
               'LANGSMITH_TRACING': '1'}
        with patch.dict(os.environ, env), patch.object(main, 'API_TOKEN', 'fixture'), patch.object(main, 'llm') as model:
            r = asyncio.run(main.analyze_clauses_endpoint(FakeRequest({'document_text': '1 Supplier shall pay.',
                                                                     'analysis_mode': 'model_assisted'})))
        self.assertEqual('rejected_or_unavailable', r['model_assistance']['status'])
        model.bind.assert_not_called()

    def test_hybrid_not_enabled_by_clause_analysis(self):
        search = Mock()
        with patch.dict(os.environ, {'ENABLE_CLAUSE_INTELLIGENCE': 'true', 'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'false'}):
            report = analyze(request(research_query='fictional applicable legal requirements'), external_search=search)
        self.assertEqual('hybrid_disabled', report['external_research']['status'])
        search.assert_not_called()

    def test_research_uses_existing_engine_filters_and_only_explicit_query(self):
        client = Client([row(1), row(2, jurisdiction='difc')], [row(1), row(2, jurisdiction='difc')])
        calls = []
        def search(req):
            calls.append(req)
            return HybridRetrievalEngine(client, lambda _: VECTOR).search(req)
        req = request(research_query='Article 15 of fictional Law 12', jurisdiction={'governing_law': 'uae_federal'}, as_of='2026-01-15')
        with patch.dict(os.environ, {'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'true'}):
            report = analyze(req, external_search=search)
        self.assertEqual(req.research_query, calls[0].query)
        self.assertNotEqual(req.document.text, calls[0].query)
        self.assertEqual(['1'], [s['identity'] for s in report['external_research']['sources']])
        self.assertTrue(report['external_research']['legal_research_gap'])

    def test_missing_migration_cannot_break_offline_analysis(self):
        def unavailable(_):
            raise RuntimeError('PRIVATE SUPABASE ERROR')
        with patch.dict(os.environ, {'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'true'}):
            r = analyze(request(research_query='official law'), external_search=unavailable)
        self.assertTrue(r['clauses'])
        self.assertEqual('unavailable', r['external_research']['status'])
        self.assertNotIn('PRIVATE', json.dumps(r))

    def test_precedent_cannot_establish_applicable_law(self):
        client = Client([row(source='drafting_precedent')], [row(source='drafting_precedent')])
        with patch.dict(os.environ, {'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'true'}):
            result = analyze(request(research_query='law'), external_search=HybridRetrievalEngine(client, lambda _: VECTOR).search)
        self.assertFalse(result['external_research']['sources'])

    def test_research_reuses_all_existing_authority_source_enums(self):
        from retrieval.schemas import AUTHORITY_CLASSES
        for source in AUTHORITY_CLASSES:
            with self.subTest(source=source):
                client = Client([row(source=source.value)], [row(source=source.value)])
                with patch.dict(os.environ, {'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'true'}):
                    r = analyze(request(research_query='official law'), external_search=HybridRetrievalEngine(client, lambda _: VECTOR).search)
                self.assertEqual([source.value], [s['source_class'] for s in r['external_research']['sources']])

    def test_all_seven_jurisdictions_remain_separate_and_uninferred(self):
        for law in ('uae_federal', 'abu_dhabi', 'dubai', 'sharjah', 'other_uae_emirates', 'adgm', 'difc'):
            r = analyze(request(jurisdiction={'governing_law': law}, document_text='1 Dubai courts have jurisdiction.'))
            self.assertEqual(law, r['document']['jurisdiction_context']['governing_law'])
            self.assertEqual('unknown', r['document']['jurisdiction_context']['court_jurisdiction'])

    def test_condition_dependency_links_resolved_reference_without_fulfilment(self):
        r = analyze(request(document_text='1 Supplier shall pay subject to Clause 2.\n2 Completion requires written confirmation.'))
        self.assertEqual(['C-0002'], r['conditions'][0]['target_clauses'])
        self.assertEqual('unknown', r['conditions'][0]['condition_status'])

    def test_multiple_definitions_are_potential_conflicts_not_resolved(self):
        r = analyze(request(document_text='1 "Services" means screening.\n2 "Services" means drafting.'))
        conflicts = [f for f in r['findings'] if f['category'] == 'potential_conflict']
        self.assertEqual(1, len(conflicts))
        self.assertEqual('AMBIGUOUS', conflicts[0]['evidence_status'])
        self.assertEqual(2, len(conflicts[0]['evidence']))

    def test_arabic_report_explanations_and_quotations(self):
        text = '1 مع مراعاة المادة السابعة، يلتزم المورد بالسداد.'
        r = analyze(request(document_text=text, language='ar'))
        gap = next(f for f in r['findings'] if f['category'] == 'evidence_gap')
        self.assertIn('المحتوى', gap['claim_text'])
        self.assertEqual(text[gap['evidence'][0]['start']:gap['evidence'][0]['end']], gap['evidence'][0]['quote'])

    def test_all_five_playbooks_receive_evidenced_structured_inputs(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            for skill in SUPPORTED:
                with self.subTest(skill=skill):
                    r = analyze(request(document_text='1 Supplier shall not disclose confidential information.\n2 Subject to Schedule A, payment applies.\n3 Board approval is required.',
                                        playbook=skill, jurisdiction={'governing_law': 'uae_federal'}))
                    self.assertEqual('selected', r['playbook']['status'])
                    self.assertEqual(skill, r['playbook']['skill_id'])
                    self.assertFalse(r['playbook']['methodology_is_legal_authority'])
                    self.assertTrue(r['playbook']['clause_ids'])
                    if skill == 'uae-legal-risk':
                        self.assertEqual('unknown', r['playbook']['risk_assessment']['status'])
                    if skill == 'uae-contract-negotiation':
                        self.assertEqual('unagreed_illustrative_draft', r['playbook']['proposed_amendments'][0]['status'])

    def test_playbooks_independently_disabled(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'false'}):
            r = analyze(request(playbook='uae-contract-review'))
        self.assertEqual('disabled', r['playbook']['status'])

    def test_invalid_playbook_rejected_without_filesystem_access(self):
        from clause_intelligence import ClauseError
        with self.assertRaises(ClauseError):
            analyze(request(playbook='unregistered'))

    def test_explicit_definition_evidence_retains_original_language(self):
        r = analyze(request(document_text='1 "Deliverable" means the monthly report.\n2 «المعلومات» يقصد به بيانات العميل.', language='bilingual'))
        self.assertEqual(['Deliverable', 'المعلومات'], [t['term'] for t in r['defined_terms']])

    def test_date_context_does_not_convert_notice_to_limitation_period(self):
        r = analyze(request(document_text='1 Notice: 30 calendar days.'))
        self.assertEqual('notice', r['dates'][0]['contractual_context'])
        self.assertIsNone(r['dates'][0]['resolved_date'])

    def test_existing_next_proxy_forwards_nested_analysis_path_and_hides_token(self):
        proxy = Path('frontend/app/api/[...path]/route.ts').read_text()
        self.assertIn('path.join("/")', proxy)
        self.assertIn('request.nextUrl.search', proxy)
        self.assertIn('headers.set("authorization", `Bearer ${API_TOKEN}`)', proxy)
        self.assertNotIn('NEXT_PUBLIC_API_TOKEN', proxy)
