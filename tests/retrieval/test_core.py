import copy
from dataclasses import replace
from datetime import date
import math
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from retrieval.config import RetrievalConfig,enabled
from retrieval.context import RetrievalSession,from_payload,retrieval_session,current_session
from retrieval.normalization import normalize
from retrieval.query_analysis import references,exact_match
from retrieval.schemas import RetrievalError,SourceClass,RetrievalContext,RetrievalRequest
from retrieval.provenance import parse
from retrieval.eligibility import evaluate
from retrieval.fusion import fuse,diversify
from retrieval.engine import HybridRetrievalEngine
from skills.schemas import JurisdictionContext
from tests.retrieval.helpers import row,request,Client,VECTOR


class NormalizationTests(unittest.TestCase):
    def test_arabic_diacritics_tatweel_alef(self):
        self.assertEqual('المادة 15 اثبات',normalize('المَادَّة ١٥ إِثـبَات'))
    def test_western_arabic_and_persian_digits(self):
        self.assertEqual('15 15 15',normalize('15 ١٥ ۱۵'))
    def test_nfkc_and_mixed_case(self):
        self.assertEqual('article 15 دبي',normalize('ＡＲＴＩＣＬＥ １５ دبي'))
    def test_preserve_legally_distinct_subsections(self):
        self.assertNotEqual(normalize('7.3'),normalize('7/3'))
    def test_no_ta_marbuta_or_ya_merging(self):
        self.assertNotEqual(normalize('هدى'),normalize('هدي'))
        self.assertNotEqual(normalize('هبة'),normalize('هبه'))
    def test_query_validation(self):
        for q in (None,{},'x'*20001,'x\x00'):
            with self.assertRaises(RetrievalError): normalize(q)
    def test_article_and_instrument_pair(self):
        expected=references('Article 15 of Law No. 12')
        self.assertEqual(expected,references('المادة ١٥ من القانون رقم ١٢'))
        self.assertEqual({('article','15'),('law','12')},{(r.kind,r.value) for r in expected})
    def test_subsection_identifiers_stay_distinct(self):
        self.assertNotEqual(references('Clause 7.3'),references('البند 7/3'))
    def test_decree_law_is_not_generic_law(self):
        refs=references('Decree-law No. 12 Article 15')
        self.assertIn('decree_law',[r.kind for r in refs])
        self.assertNotIn('law',[r.kind for r in refs])
    def test_exact_requires_whole_reference_pair(self):
        c=parse(row(instrument_id='law:99',article_reference='15',text='Article 15 of Law No. 99'),'legislation')
        c=replace(c,title='Law No. 99')
        self.assertFalse(exact_match(references('Article 15 of Law No. 12'),c))
    def test_partial_numbers_are_not_exact(self):
        c=parse(row(instrument_id=None,article_reference=None,text='The invoice number is 15 and fee is 12.'),'legislation')
        c=replace(c,title='Unrelated material')
        self.assertFalse(exact_match(references('Article 15 of Law No. 12'),c))
    def test_exact_structured_fields(self):
        self.assertEqual(('article:structured','law:structured'),exact_match(references('Article 15 of Law No. 12'),parse(row(),'legislation')))
    def test_exact_source_text_not_legal_verification(self):
        c=parse(row(article_reference=None,instrument_id=None),'legislation')
        self.assertEqual(('article:source_text','law:source_text'),exact_match(references('Article 15 of Law No. 12'),c))


class AdapterTests(unittest.TestCase):
    def test_rpc_parameters_and_limits(self):
        client=Client([row()],[row()]);calls=[]
        result=HybridRetrievalEngine(client,lambda q:calls.append(q) or VECTOR,RetrievalConfig(candidate_pool=17)).search(request())
        self.assertTrue(result.candidates)
        self.assertEqual(1,len(calls))
        self.assertEqual({'hybrid_semantic_v1','hybrid_lexical_v1'},{name for name,_ in client.calls})
        for name,params in client.calls: self.assertEqual(17,params['p_limit'])
    def test_family_and_exact_parameters_are_values_not_sql(self):
        client=Client();q="Article 15'; DROP TABLE legal_documents; --"
        HybridRetrievalEngine(client,lambda _:VECTOR).search(request(q))
        _,params=client.calls[-1]
        self.assertIn('drop table',params['p_query'])
        self.assertEqual('legislation',params['p_family'])
    def test_embedding_reused_within_request_across_families(self):
        client=Client();calls=[];session=RetrievalSession()
        engine=HybridRetrievalEngine(client,lambda q:calls.append(q) or VECTOR)
        engine.search(request(),session);engine.search(request(family='contracts'),session)
        self.assertEqual(1,len(calls))
    def test_embedding_not_reused_between_sessions(self):
        calls=[];engine=HybridRetrievalEngine(Client(),lambda q:calls.append(q) or VECTOR)
        engine.search(request());engine.search(request())
        self.assertEqual(2,len(calls))
    def test_concurrent_embedding_single_compute(self):
        session=RetrievalSession();calls=[]
        def encode(q): calls.append(q);return VECTOR
        with ThreadPoolExecutor(8) as pool: list(pool.map(lambda _:session.embedding('same',encode),range(20)))
        self.assertEqual(1,len(calls))
    def test_invalid_vector_uses_explicit_degraded_lexical_path(self):
        for vector in ([1.0]*3,[0.0]*1024,[float('nan')]*1024,[True]*1024):
            client=Client(lexical=[row()])
            result=HybridRetrievalEngine(client,lambda _:vector).search(request())
            self.assertEqual('degraded',result.status)
            self.assertIn('embedding_unavailable',result.diagnostics['failure_categories'])
            self.assertFalse(any(name=='hybrid_semantic_v1' for name,_ in client.calls))
    def test_migration_absent_is_not_false_success_or_legacy_fallback(self):
        error=RuntimeError('PRIVATE SQL DETAIL');error.code='PGRST202'
        client=Client(failures={'hybrid_semantic_v1':error,'hybrid_lexical_v1':error})
        result=HybridRetrievalEngine(client,lambda _:VECTOR).search(request())
        self.assertEqual('unavailable',result.status)
        self.assertEqual(['migration_absent'],result.diagnostics['failure_categories'])
        self.assertNotIn('PRIVATE',str(result.diagnostics))
        self.assertFalse(any(name.startswith('match_') for name,_ in client.calls))
    def test_lexical_failure_not_reported_as_full_hybrid_success(self):
        client=Client([row()],failures={'hybrid_lexical_v1':TimeoutError('private query')})
        result=HybridRetrievalEngine(client,lambda _:VECTOR).search(request())
        self.assertEqual('degraded',result.status)
        self.assertIn('timeout',result.diagnostics['failure_categories'])
    def test_no_eligible_sources_never_restores_wrong_regime(self):
        client=Client([row(jurisdiction='difc')],[row(jurisdiction='difc')])
        result=HybridRetrievalEngine(client,lambda _:VECTOR).search(request())
        self.assertEqual('no_eligible_sources',result.status)
        self.assertFalse(result.candidates)
    def test_empty_query_has_no_external_calls(self):
        client=Client();result=HybridRetrievalEngine(client,lambda _:VECTOR).search(request(' '))
        self.assertEqual('empty_query',result.status);self.assertFalse(client.calls)
    def test_invalid_family_and_context(self):
        with self.assertRaises(RetrievalError):request(family='legal_documents;drop')
        for value in ({'jurisdiction':{'governing_law':'UK'}},{'as_of':'20260101'},{'as_of':'2026-02-30'},{'path':'/etc/passwd'}):
            with self.assertRaises(RetrievalError):from_payload(value)
    def test_strict_unknown_policy_excludes_without_promotion(self):
        old={'id':1,'document_name':'old law','chunk_content':'Article 15','metadata':{}}
        result=HybridRetrievalEngine(Client([old],[old]),lambda _:VECTOR,RetrievalConfig(unknown_policy='exclude')).search(request())
        self.assertFalse(result.candidates)
    def test_unknown_leads_are_explicit(self):
        old={'id':1,'document_name':'old law','chunk_content':'Article 15','metadata':{}}
        result=HybridRetrievalEngine(Client([old],[old]),lambda _:VECTOR).search(request())
        self.assertEqual('unknown',result.candidates[0].eligibility.decision)
        self.assertEqual(SourceClass.UNKNOWN,result.candidates[0].provenance.source_class)
    def test_caps_enforced_even_if_rpc_ignores_limits(self):
        rows=[row(i) for i in range(1,140)]
        result=HybridRetrievalEngine(Client(rows,rows),lambda _:VECTOR,RetrievalConfig(candidate_pool=10)).search(request())
        self.assertEqual(3,len(result.candidates))
    def test_invalid_runtime_settings_fail(self):
        for kwargs in ({'candidate_pool':0},{'candidate_pool':101},{'rrf_k':True},{'max_per_document':0},{'unknown_policy':'accept'}):
            with self.assertRaises(RetrievalError):RetrievalConfig(**kwargs)
    def test_default_flag_independent_of_skills(self):
        with patch.dict(os.environ,{'ENABLE_LEGAL_SKILLS':'true','ENABLE_HYBRID_LEGAL_RETRIEVAL':'false'}):self.assertFalse(enabled())
    def test_session_lifecycle_cleanup(self):
        self.assertIsNone(current_session())
        with self.assertRaises(RuntimeError):
            with retrieval_session() as session:
                self.assertIs(current_session(),session);raise RuntimeError()
        self.assertIsNone(current_session())


class FusionTests(unittest.TestCase):
    def test_standard_rrf(self):
        a,b=parse(row(1),'legislation'),parse(row(2),'legislation')
        result,_=fuse([a,b],[b,a],k=60,exact_priority=False)
        self.assertAlmostEqual(1/61+1/62,result[0].fusion_score)
        self.assertEqual('1',result[0].chunk_id)
        self.assertEqual(1,result[0].semantic_rank)
        self.assertEqual(2,result[0].lexical_rank)
    def test_single_source(self):
        a=parse(row(),'legislation');result,_=fuse([a],[])
        self.assertEqual(1/61,result[0].fusion_score)
        self.assertIsNone(result[0].lexical_rank)
    def test_duplicate_within_branch_cannot_inflate_score(self):
        a=parse(row(),'legislation');result,_=fuse([a,a],[a,a])
        self.assertEqual(1,len(result));self.assertEqual(2/61,result[0].fusion_score)
    def test_conflicting_same_id_text_is_excluded(self):
        a=parse(row(),'legislation');b=replace(a,text='different')
        result,conflicts=fuse([a],[b])
        self.assertFalse(result);self.assertEqual(1,conflicts)
    def test_missing_ids_rejected_not_title_merged(self):
        for value in (None,'',True,'1.0'):
            bad=row();bad['id']=value
            with self.assertRaises(RetrievalError):parse(bad,'legislation')
    def test_titles_alone_do_not_deduplicate(self):
        a,b=parse(row(1),'legislation'),parse(row(2),'legislation')
        self.assertEqual(2,len(fuse([a,b],[])[0]))
    def test_document_diversity_and_distinct_articles(self):
        rows=[parse(row(i,source_document_id='same',article_reference=str(i)),'legislation') for i in range(1,6)]
        selected,count=diversify(rows,3,2)
        self.assertEqual(2,len(selected));self.assertEqual(3,count)
        self.assertEqual(3,len(diversify(rows,3,3)[0]))
    def test_exact_priority_separately_configurable(self):
        a=parse(row(1),'legislation');b=replace(parse(row(2),'legislation'),exact_basis=('article:structured',))
        self.assertEqual('2',fuse([a,b],[],exact_priority=True)[0][0].chunk_id)
        self.assertEqual('1',fuse([a,b],[],exact_priority=False)[0][0].chunk_id)
    def test_family_in_identity(self):
        a=parse(row(),'legislation');b=replace(a,family='contracts')
        self.assertEqual(2,len(fuse([a,b],[])[0]))


class EligibilityTests(unittest.TestCase):
    def test_all_seven_jurisdictions_and_unknown(self):
        for jurisdiction in ('uae_federal','abu_dhabi','dubai','sharjah','other_uae_emirates','adgm','difc'):
            self.assertEqual('compatible',evaluate(parse(row(jurisdiction=jurisdiction),'legislation'),request(jurisdiction=jurisdiction)).decision)
        self.assertEqual('unknown',evaluate(parse(row(jurisdiction='unknown'),'legislation'),request()).decision)
    def test_special_regime_conflicts(self):
        for jurisdiction in ('adgm','difc','dubai'):
            self.assertEqual('incompatible',evaluate(parse(row(jurisdiction=jurisdiction),'legislation'),request()).decision)
    def test_court_does_not_infer_governing_law(self):
        c=from_payload(case=SimpleNamespace(forum='DIFC',country='UAE'))
        self.assertEqual('difc',c.jurisdiction.court_jurisdiction)
        self.assertEqual('unknown',c.jurisdiction.governing_law)
    def test_conflicting_intake_rejected(self):
        with self.assertRaises(RetrievalError):from_payload({'jurisdiction':{'court_jurisdiction':'adgm'}},case=SimpleNamespace(forum='DIFC',country='UAE'))
    def test_source_classes_not_authority_by_family(self):
        for source in ('contractual_evidence','drafting_precedent','internal_policy','external_commentary'):
            self.assertEqual('incompatible',evaluate(parse(row(source=source),'legislation'),request()).decision)
    def test_judgments_are_not_relabelled_as_legislation(self):
        c=parse(row(source='judicial_decision'),'legislation')
        self.assertEqual(SourceClass.JUDICIAL,c.provenance.source_class)
    def test_unverified_class_not_promoted(self):
        c=parse(row(classification_verified=False),'legislation')
        self.assertEqual(SourceClass.UNKNOWN,c.provenance.source_class)
    def test_generated_material_rejected(self):
        self.assertEqual('incompatible',evaluate(parse(row(ai_generated=True),'legislation'),request()).decision)
    def test_temporal_expired_and_future_excluded(self):
        for update in ({'effective_to':'2025-01-01'},{'effective_from':'2027-01-01'}):
            self.assertEqual('incompatible',evaluate(parse(row(**update),'legislation'),request()).decision)
    def test_empty_expiry_does_not_prove_current_force(self):
        decision=evaluate(parse(row(temporal_verified_through=None),'legislation'),request())
        self.assertEqual('unknown',decision.decision);self.assertEqual('unverified',decision.temporal_status)
    def test_four_verification_claims_independent(self):
        c=parse(row(verified=True,temporal_verified_through=None),'legislation')
        e=evaluate(c,request())
        self.assertEqual('verified',e.identity_status)
        self.assertEqual('metadata_compatible',e.jurisdiction_status)
        self.assertEqual('unverified',e.temporal_status)
    def test_no_original_text_mutation(self):
        source=row(text='المَادَّة ١٥: نص أصليّ.');original=copy.deepcopy(source)
        c=parse(source,'legislation');exact_match(references('المادة 15'),c)
        self.assertEqual(original,source);self.assertEqual(original['chunk_content'],c.text)
    def test_invalid_metadata_fail_closed(self):
        for update in ({'verified_at':'2026-02-30'},{'verified_at':'20260101'},{'classification_verified':'true'},
                       {'source_class':'primary-because-ai-said-so'},{'jurisdiction':{'governing_law':'UK'}},
                       {'official_url':'https://user:secret@host/law'}):
            with self.subTest(update=update),self.assertRaises(RetrievalError):parse(row(**update),'legislation')
    def test_family_mismatch_rejected(self):
        with self.assertRaises(RetrievalError):parse(row(family='drafts'),'legislation')


class IdentifierSafetyTests(unittest.TestCase):
    def test_year_specific_instruments_not_merged(self):
        self.assertNotEqual(references('Law No. 12 of 2020'),references('القانون رقم ١٢ لسنة ٢٠٢١'))
        candidate=parse(row(instrument_id='law:12:2021',text='Article 15 of Law No. 12 of 2021'),'legislation')
        candidate=replace(candidate,title='Law No. 12 of 2021')
        self.assertFalse(exact_match(references('Article 15 of Law No. 12 of 2020'),candidate))
    def test_matching_year_supported(self):
        candidate=parse(row(instrument_id='law:12:2020'),'legislation')
        self.assertTrue(exact_match(references('Article 15 of Law No. 12 of 2020'),candidate))
    def test_non_numeric_suffix_not_silently_dropped(self):
        self.assertFalse(references('Article 15a'))
        self.assertEqual('15',references('Article 15. Next sentence')[0].value)
    def test_invalid_empty_metadata_is_not_treated_as_missing(self):
        for metadata in ([],0,False):
            value=row();value['metadata']=metadata
            with self.assertRaises(RetrievalError):parse(value,'legislation')


class ConservativeMetadataTests(unittest.TestCase):
    def test_unverified_structured_identifier_cannot_receive_exact_boost(self):
        c=parse(row(verified=False,text='No references in this passage'),'legislation')
        c=replace(c,title='Unrelated title')
        self.assertFalse(exact_match(references('Article 15 of Law No. 12'),c))
    def test_unverified_non_authority_declaration_cannot_be_hidden_as_unknown(self):
        c=parse(row(source='internal_policy',classification_verified=False),'legislation')
        self.assertEqual('incompatible',evaluate(c,request()).decision)
    def test_foreign_case_stops_all_rpc_calls(self):
        ctx=from_payload(case=SimpleNamespace(country='UK',forum='London'))
        client=Client([row()],[row()])
        result=HybridRetrievalEngine(client,lambda _:VECTOR).search(replace(request(),context=ctx))
        self.assertEqual('unsupported_jurisdiction',result.status);self.assertFalse(client.calls)


class QueryBoundTests(unittest.TestCase):
    def test_many_references_do_not_silently_match_a_subset(self):
        query=' '.join('Article '+str(i) for i in range(1,20))
        client=Client()
        result=HybridRetrievalEngine(client,lambda _:VECTOR).search(request(query))
        self.assertEqual('invalid_query',result.status);self.assertFalse(client.calls)
    def test_exact_setting_cannot_silently_accept_arbitrary_text(self):
        with patch.dict(os.environ,{'HYBRID_EXACT_PRIORITY':'invalid'}),self.assertRaises(RetrievalError):RetrievalConfig.from_env()


class MetadataPreferenceTests(unittest.TestCase):
    def test_unverified_lead_does_not_crowd_out_equally_exact_compatible_source(self):
        from retrieval.schemas import Eligibility
        unknown=replace(parse(row(1),'legislation'),eligibility=Eligibility('unknown'))
        compatible=replace(parse(row(2),'legislation'),eligibility=Eligibility('compatible'))
        normal=fuse([unknown,compatible],[],prefer_compatible=False)[0]
        preferred=fuse([unknown,compatible],[],prefer_compatible=True)[0]
        self.assertEqual('1',normal[0].chunk_id);self.assertEqual('2',preferred[0].chunk_id)
        self.assertEqual(1/62,preferred[0].fusion_score)
        self.assertEqual('unknown',preferred[1].eligibility.decision)


class SafeAuditAndDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_never_include_query_source_text_names_or_ids(self):
        query='PRIVATE_QUERY_FOR_TEST'
        source=row(text='PRIVATE_DOCUMENT_FOR_TEST')
        result=HybridRetrievalEngine(Client([source],[source]),lambda _:VECTOR).search(request(query))
        import json
        text=json.dumps(result.diagnostics)
        self.assertNotIn(query,text);self.assertNotIn(source['document_name'],text);self.assertNotIn(source['chunk_content'],text)
        self.assertNotIn('chunk_id',text)
    def test_audit_contract_rejects_unexpected_raw_data(self):
        from scripts.audit_retrieval_metadata import audit,KEYS
        good={key:0 for key in KEYS}
        client=SimpleNamespace(rpc=lambda *args:SimpleNamespace(execute=lambda:SimpleNamespace(data=good)))
        self.assertEqual(good,audit(client,'legislation'))
        bad={**good,'document_text':'PRIVATE'}
        client=SimpleNamespace(rpc=lambda *args:SimpleNamespace(execute=lambda:SimpleNamespace(data=bad)))
        with self.assertRaises(ValueError):audit(client,'legislation')


class FailureCategoryTests(unittest.TestCase):
    def test_sdk_timeout_and_permission_failures_are_distinct(self):
        from retrieval.diagnostics import call
        class ReadTimeout(Exception):pass
        error=RuntimeError('PRIVATE');error.code='42501'
        for error,wanted in ((ReadTimeout('PRIVATE'),'timeout'),(error,'permission_denied')):
            def fail():raise error
            self.assertEqual(wanted,call('lexical',fail).status)
    def test_invalid_rows_are_data_failure_not_legal_exclusion(self):
        invalid=row();invalid['id']=None
        result=HybridRetrievalEngine(Client([invalid],[invalid]),lambda _:VECTOR).search(request())
        self.assertEqual('unavailable',result.status)
        self.assertIn('invalid_metadata',result.diagnostics['failure_categories'])


class CrossBranchExclusionTests(unittest.TestCase):
    def test_other_branch_cannot_restore_incompatible_source_under_same_identity(self):
        good=row(1)
        conflicting=row(1,jurisdiction='difc')
        result=HybridRetrievalEngine(Client([good],[conflicting]),lambda _:VECTOR).search(request())
        self.assertFalse(result.candidates)
        self.assertIn('invalid_metadata',result.diagnostics['failure_categories'])


class UniqueRankTests(unittest.TestCase):
    def test_duplicate_rows_do_not_demote_next_unique_source(self):
        a,b=parse(row(1),'legislation'),parse(row(2),'legislation')
        fused,_=fuse([a,a,b],[])
        other=next(c for c in fused if c.chunk_id=='2')
        self.assertEqual(2,other.semantic_rank)
        self.assertEqual(1/62,other.fusion_score)
