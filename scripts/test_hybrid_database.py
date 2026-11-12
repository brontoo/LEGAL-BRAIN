"""Disposable PostgreSQL/pgvector integration checks and measured synthetic benchmark.

Optional dependency: psycopg[binary]. Never accepts production/remote DSNs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

from benchmarks.hybrid.postgres import DisposableClient,TABLES
from benchmarks.hybrid.runner import load_fixture,run,FIXTURE,vector
from retrieval.config import RetrievalConfig
from retrieval.engine import HybridRetrievalEngine
from tests.retrieval.helpers import row,request,VECTOR
from psycopg.types.json import Jsonb
from psycopg import sql

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn',default='host=127.0.0.1 port=15432 dbname=legal_brain_test user=postgres')
    parser.add_argument('--acknowledge-disposable',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a new output filename')
    client=DisposableClient(args.dsn,acknowledge_disposable=args.acknowledge_disposable)
    con=client.connection
    migration=(ROOT/'migrations/phase2a_hybrid_retrieval.sql').read_text()
    baseline={r['proname']:r['body'] for r in con.execute("select proname,pg_get_functiondef(oid) body from pg_proc where proname=any(%s)",(['match_'+t for t in TABLES.values()],))}
    if len(baseline)!=5:raise RuntimeError('Apply the existing schema.sql to the disposable database first')
    con.execute(migration)
    con.execute(migration)
    fixture=json.loads(FIXTURE.read_text());load_fixture(client,fixture)

    class DatabaseChecks(unittest.TestCase):
        def test_01_all_legacy_rpc_contracts_unchanged(self):
            after={r['proname']:r['body'] for r in con.execute("select proname,pg_get_functiondef(oid) body from pg_proc where proname=any(%s)",(['match_'+t for t in TABLES.values()],))}
            self.assertEqual(baseline,after)
        def test_02_indexes_retained_and_added(self):
            indexes={r['indexname'] for r in con.execute("select indexname from pg_indexes where schemaname='public'")}
            for table in TABLES.values():
                self.assertIn(table+'_embedding_idx',indexes);self.assertIn(table+'_lexical_v1_idx',indexes)
        def test_03_rpcs_all_families_and_metadata(self):
            for family in TABLES:
                q=next(q for q in fixture['queries'] if q['family']==family)
                result=HybridRetrievalEngine(client,lambda _:vector(q['synthetic_features'])).search(request(q['query'],family,q['jurisdiction']))
                self.assertEqual('ok',result.status)
                self.assertTrue(result.candidates)
                self.assertTrue(all(c.family==family for c in result.candidates))
        def test_04_filters_apply_before_limit(self):
            result=HybridRetrievalEngine(client,lambda _:vector(['family:legislation','topic:payment']),RetrievalConfig(candidate_pool=1,unknown_policy='exclude')).search(request('payment obligations',jurisdiction='uae_federal'))
            self.assertTrue(result.candidates)
            self.assertEqual('compatible',result.candidates[0].eligibility.decision)
        def test_05_normalization_parity(self):
            from retrieval.normalization import normalize
            for value in ('المَادَّة ١٥ إِثـبَات','Clause ۷/۳','ＡＲＴＩＣＬＥ １５'):
                self.assertEqual(normalize(value),con.execute('select public.retrieval_normalize_v1(%s) v',(value,)).fetchone()['v'])
        def test_06_exact_matching_is_conjunctive(self):
            refs=Jsonb([{'kind':'article','value':'15'},{'kind':'law','value':'12'}])
            for title,body,wanted in (('Law No. 12','Article 15',True),('Law No. 99','Article 15',False),('Unrelated 15','Invoice 12',False)):
                result=con.execute('select public.retrieval_exact_v1(%s,%s,%s,%s) v',(title,body,Jsonb({}),refs)).fetchone()['v']
                self.assertEqual(wanted,result)
        def test_07_decree_law_not_generic_law(self):
            result=con.execute('select public.retrieval_exact_v1(%s,%s,%s,%s) v',('Decree-law No. 12','Article 15',Jsonb({}),Jsonb([{'kind':'law','value':'12'}]))).fetchone()['v']
            self.assertFalse(result)
        def test_08_strict_unknown_policy_excludes_old_metadata(self):
            self.assertFalse(con.execute('select public.retrieval_eligible_v1(%s,%s,%s) v',(Jsonb({}),'legislation',Jsonb({'unknown_policy':'exclude'}))).fetchone()['v'])
        def test_09_role_and_view_are_invoker(self):
            self.assertTrue(all(not r['prosecdef'] for r in con.execute("select prosecdef from pg_proc where proname in ('hybrid_semantic_v1','hybrid_lexical_v1','hybrid_metadata_audit_v1')")))
            self.assertIn('security_invoker=true',con.execute("select reloptions from pg_class where oid='public.retrieval_chunks_v1'::regclass").fetchone()['reloptions'])
        def test_10_no_public_function_or_view_access(self):
            self.assertFalse(con.execute("select has_function_privilege('anon','public.hybrid_lexical_v1(text,text,jsonb,integer,jsonb)','execute') ok").fetchone()['ok'])
            self.assertFalse(con.execute("select has_table_privilege('anon','public.retrieval_chunks_v1','select') ok").fetchone()['ok'])
        def test_11_invoker_does_not_bypass_base_privileges_or_rls(self):
            from psycopg.errors import InsufficientPrivilege
            for table in TABLES.values():con.execute(sql.SQL('revoke select on public.{} from service_role').format(sql.Identifier(table)))
            con.execute('set role service_role')
            try:
                with self.assertRaises(InsufficientPrivilege):con.execute("select * from public.hybrid_lexical_v1('legislation','payment')").fetchall()
            finally:con.execute('reset role')
            for table in TABLES.values():con.execute(sql.SQL('grant select on public.{} to service_role').format(sql.Identifier(table)))
            con.execute('alter table public.legal_documents enable row level security')
            con.execute('set role service_role')
            try:self.assertEqual([],con.execute("select * from public.hybrid_lexical_v1('legislation','payment')").fetchall())
            finally:con.execute('reset role');con.execute('alter table public.legal_documents disable row level security')
        def test_12_audit_returns_only_aggregates(self):
            payload=client.rpc('hybrid_metadata_audit_v1',{'p_family':'legislation'}).execute().data[0]['audit']
            self.assertEqual(60,payload['records'])
            self.assertTrue(all(type(value) is int for value in payload.values()))
            self.assertEqual(payload['records'],payload['known_jurisdiction']+payload['unknown_jurisdiction'])
            with con.transaction(force_rollback=True):
                con.execute('insert into public.legal_documents (id,document_name,chunk_content,metadata) overriding system value values (%s,%s,%s,%s)',
                    (9999999,'FICTIONAL audit probe','Not legal material',Jsonb({'retrieval_v1':{'jurisdiction':{'governing_law':'invalid'}}})))
                observed=client.rpc('hybrid_metadata_audit_v1',{'p_family':'legislation'}).execute().data[0]['audit']
                self.assertEqual(61,observed['records']);self.assertEqual(11,observed['unknown_jurisdiction'])

        def test_13_malformed_sql_inputs_rejected(self):
            from psycopg.errors import InvalidParameterValue
            with self.assertRaises(InvalidParameterValue):client.rpc('hybrid_lexical_v1',{'p_family':'legislation;drop table legal_documents','p_query':'x','p_references':[],'p_limit':10,'p_filters':{}}).execute()
        def test_14_index_expression_supports_gin_plan(self):
            con.execute('set enable_seqscan=off')
            try:
                plan=con.execute("explain select id from legal_documents where to_tsvector('simple',retrieval_normalize_v1(document_name||' '||chunk_content))@@plainto_tsquery('simple','payment')").fetchall()
                self.assertIn('legal_documents_lexical_v1_idx',str(plan))
            finally:con.execute('reset enable_seqscan')
        def test_15_original_passage_preserved(self):
            item=fixture['corpus'][0]
            table=TABLES[item['family']]
            actual=con.execute(sql.SQL('select chunk_content from public.{} where id=%s').format(sql.Identifier(table)),(item['id'],)).fetchone()['chunk_content']
            self.assertEqual(item['chunk_content'],actual)
        def test_16_year_specific_reference_and_sentence_boundary(self):
            for title,refs,wanted in (
                ('Law No. 12 of 2020.',[{'kind':'law','value':'12:2020'}],True),
                ('Law No. 12 of 2021.',[{'kind':'law','value':'12:2020'}],False),
                ('Article 15.',[{'kind':'article','value':'15'}],True),
                ('Article 15a',[{'kind':'article','value':'15'}],False)):
                result=con.execute('select public.retrieval_exact_v1(%s,%s,%s,%s) v',(title,'',Jsonb({}),Jsonb(refs))).fetchone()['v']
                self.assertEqual(wanted,result)
        def test_17_unverified_metadata_is_not_an_exact_match(self):
            metadata={'retrieval_v1':{'article_reference':'15','identity_verified':False}}
            self.assertFalse(con.execute('select public.retrieval_exact_v1(%s,%s,%s,%s) v',('No reference','Nothing',Jsonb(metadata),Jsonb([{'kind':'article','value':'15'}]))).fetchone()['v'])
        def test_18_sql_python_eligibility_parity(self):
            from retrieval.provenance import parse
            from retrieval.eligibility import evaluate
            from retrieval.semantic import filters
            from retrieval.schemas import RetrievalError
            cases=[row(jurisdiction=value) for value in ('uae_federal','abu_dhabi','dubai','sharjah','other_uae_emirates','adgm','difc','unknown')]
            cases+=[row(**change) for change in ({'classification_verified':False},{'identity_verified':False},
                {'verified_at':None},{'temporal_verified_through':None},{'effective_to':'2025-01-01'},
                {'source':'internal_policy','classification_verified':False},{'ai_generated':True},
                {'source':'judicial_decision'},{'effective_from':'2027-01-01'},{'official_url':None},{'jurisdiction':None})]
            null_namespace=row();null_namespace['metadata']['retrieval_v1']['jurisdiction']=None
            null_metadata=row();null_metadata['metadata']=None
            cases += [null_namespace,null_metadata]
            for policy in ('research_lead','exclude'):
                cfg=RetrievalConfig(unknown_policy=policy)
                for item in cases:
                    try:
                        eligibility=evaluate(parse(item,'legislation'),request())
                        expected=eligibility.decision!='incompatible' and (policy=='research_lead' or eligibility.decision=='compatible')
                    except RetrievalError:
                        expected=False
                    actual=con.execute('select public.retrieval_eligible_v1(%s,%s,%s) v',(Jsonb(item['metadata']),'legislation',Jsonb(filters(request(),cfg)))).fetchone()['v']
                    self.assertEqual(expected,actual,(policy,item['metadata']))
        def test_19_unknown_metadata_not_upgraded_in_storage(self):
            count=con.execute("select count(*) n from public.legal_documents where metadata->'retrieval_v1'='{}'::jsonb").fetchone()['n']
            self.assertEqual(10,count)
        def test_20_rollback_and_reapplication_preserve_rows_and_legacy_rpcs(self):
            con.execute((ROOT/'migrations/phase2a_hybrid_retrieval_rollback.sql').read_text())
            self.assertEqual(60,con.execute('select count(*) n from public.legal_documents').fetchone()['n'])
            self.assertEqual(5,con.execute("select count(*) n from pg_proc where proname=any(%s)",(['match_'+t for t in TABLES.values()],)).fetchone()['n'])
            con.execute(migration)
    outcome=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DatabaseChecks))
    if not outcome.wasSuccessful():raise SystemExit(1)
    result=run(client)
    result['database_checks']={'status':'PASSED','tests':outcome.testsRun,'postgres':con.execute('show server_version').fetchone()['server_version'],
       'pgvector':con.execute("select extversion from pg_extension where extname='vector'").fetchone()['extversion'],
       'migration_executed_twice':True,'production_database_touched':False}
    a=result['aggregate']
    critical=all(a[mode][key]==1 for mode in ('hybrid','hybrid_strict') for key in
                 ('jurisdiction_exclusion_accuracy','legal_exclusion_accuracy','provenance_status_accuracy','citation_evidence_integrity'))
    quality=all(a['hybrid'][key]>=a['semantic_only'][key] for key in ('recall_at_k','ndcg_at_k'))
    result['acceptance']={'status':'PASSED' if critical and quality else 'FAILED',
        'critical_safety_all_pass':critical,'synthetic_quality_nonregression':quality,
        'threshold_basis':'Inspected measured baseline before choosing nonregression thresholds; fixture labels unchanged'}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['aggregate'],indent=2))
    print('Saved measured synthetic SQL benchmark; no claim about e5 or current-law quality.')
    client.close()
    if not critical or not quality:raise SystemExit(1)


if __name__=='__main__':main()
