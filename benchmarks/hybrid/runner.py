"""Measured SQL benchmark, with synthetic vector fixtures and immutable labels."""
import hashlib
import json
import math
import threading
from types import SimpleNamespace
from citations import RefAllocator,Citation,verify_citations
from retrieval.evidence import build as build_evidence
from pathlib import Path
from time import perf_counter
from datetime import date
from dataclasses import asdict
from collections import defaultdict
from retrieval.config import RetrievalConfig,FINAL_COUNTS,THRESHOLDS
from retrieval.context import RetrievalSession
from retrieval.engine import HybridRetrievalEngine
from retrieval.schemas import RetrievalRequest,RetrievalContext
from skills.schemas import JurisdictionContext
from .postgres import TABLES
from .metrics import score,aggregate

FIXTURE=Path(__file__).with_name('fixture.json')


def vector(features):
    # Fixed, transparent synthetic semantic space. No per-query scripted rankings.
    out=[0.0]*1024
    for feature in features:
        index=int.from_bytes(hashlib.sha256(feature.encode()).digest()[:4],'big')%1024
        out[index]+=1.0
    length=math.sqrt(sum(x*x for x in out))
    return [x/length for x in out]


def load_fixture(client,fixture):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    con=client.connection
    # Explicit test-only driver already enforces loopback/database acknowledgement.
    for table in TABLES.values():con.execute(sql.SQL('truncate table public.{} restart identity').format(sql.Identifier(table)))
    for item in fixture['corpus']:
        statement=sql.SQL('insert into public.{} (id,document_name,chunk_content,metadata,embedding) overriding system value values (%s,%s,%s,%s,%s::vector)').format(sql.Identifier(TABLES[item['family']]))
        con.execute(statement,(item['id'],item['document_name'],item['chunk_content'],Jsonb(item['metadata']),str(vector(item['synthetic_features']))))
    for table in TABLES.values():con.execute(sql.SQL('analyze public.{}').format(sql.Identifier(table)))


def run(client):
    raw=FIXTURE.read_bytes();fixture=json.loads(raw);results=[]
    corpus_by_id={item['family']+':'+str(item['id']):item for item in fixture['corpus']}
    for query in fixture['queries']:
        embedding=vector(query['synthetic_features']);family=query['family'];k=FINAL_COUNTS[family]
        started=perf_counter()
        rows=client.rpc('match_'+TABLES[family],{'query_embedding':embedding,'match_threshold':THRESHOLDS[family],'match_count':k}).execute().data
        baseline_ms=(perf_counter()-started)*1000
        req=RetrievalRequest(query['query'],family,RetrievalContext(JurisdictionContext(governing_law=query['jurisdiction']),date.fromisoformat(query['as_of'])))
        for mode,config in (('hybrid',RetrievalConfig()),('hybrid_strict',RetrievalConfig(unknown_policy='exclude'))):
            result=HybridRetrievalEngine(client,lambda _:embedding,config).search(req,RetrievalSession(req.context))
            if result.status!='ok':raise RuntimeError('Benchmark RPC branch failed; refusing misleading quality metrics')
            identities=[c.family+':'+c.chunk_id for c in result.candidates]
            eligible_only=[c.family+':'+c.chunk_id for c in result.candidates if c.eligibility.decision=='compatible']
            labels=query['labels'];bad={key for key,value in labels.items() if value['status']=='relevant_ineligible'}
            # Provenance is independent of topical relevance: an irrelevant unknown
            # record must still remain unknown, rather than being scored as a status error.
            provenance_correct=all((c.eligibility.decision=='unknown') == (not corpus_by_id[c.family+':'+c.chunk_id]['metadata']['retrieval_v1']) for c in result.candidates)
            collected=[]
            collector=SimpleNamespace(allocator=RefAllocator(),_hybrid_lock=threading.RLock(),_hybrid_evidence={},add=collected.extend)
            displayed=build_evidence(result,collector,family)
            citation_integrity=all(e.text in displayed and bool(verify_citations([Citation(e.ref,e.text[:100])],collected).verified)
                                   and not verify_citations([Citation(e.ref,'UNRETURNED FICTIONAL TEXT not supplied')],collected).verified
                                   for e in collected)
            jurisdiction_bad={key for key,item in corpus_by_id.items() if item['family']==family
                and item['metadata']['retrieval_v1'].get('jurisdiction_verified')
                and item['metadata']['retrieval_v1']['jurisdiction']['governing_law']!=query['jurisdiction']}
            bad=bad|jurisdiction_bad
            results.append({'query_id':query['id'],'language':query['language'],'family':family,'jurisdiction':query['jurisdiction'],
                'mode':mode,'k':k,'retrieved':identities,'metrics':score(identities,labels,k),
                'incompatible_returned':sorted(set(identities)&bad),'jurisdiction_exclusion_correct':not bool(set(identities)&jurisdiction_bad),
                'legal_exclusion_correct':not bool(set(identities)&bad),
                'authoritative_incompatible_returned':sorted(set(eligible_only)&bad),
                'provenance_status_correct':provenance_correct,'citation_evidence_integrity':citation_integrity,'diagnostics':result.diagnostics})
        identities=[family+':'+str(row['id']) for row in rows]
        jurisdiction_bad={key for key,item in corpus_by_id.items() if item['family']==family and item['metadata']['retrieval_v1'].get('jurisdiction_verified') and item['metadata']['retrieval_v1']['jurisdiction']['governing_law']!=query['jurisdiction']}
        bad={key for key,value in query['labels'].items() if value['status']=='relevant_ineligible'}
        results.append({'query_id':query['id'],'language':query['language'],'family':family,'jurisdiction':query['jurisdiction'],
            'mode':'semantic_only','k':k,'retrieved':identities,'metrics':score(identities,query['labels'],k),
            'incompatible_returned':sorted(set(identities)&bad),'jurisdiction_exclusion_correct':not bool(set(identities)&jurisdiction_bad),
            'legal_exclusion_correct':not bool(set(identities)&bad),
            'provenance_status_correct':None,'diagnostics':{'total_ms':round(baseline_ms,3)}})
    aggregate_report={}
    for mode in ('semantic_only','hybrid','hybrid_strict'):
        subset=[r for r in results if r['mode']==mode]
        aggregate_report[mode]={**aggregate([r['metrics'] for r in subset]),
            'query_count':len(subset),'jurisdiction_exclusion_accuracy':sum(r['jurisdiction_exclusion_correct'] for r in subset)/len(subset),
            'provenance_status_accuracy':sum(r['provenance_status_correct'] is True for r in subset)/len(subset) if mode!='semantic_only' else None,
            'citation_evidence_integrity':sum(r.get('citation_evidence_integrity',False) for r in subset)/len(subset) if mode!='semantic_only' else None,
            'legal_exclusion_accuracy':sum(r['legal_exclusion_correct'] for r in subset)/len(subset),
            'mean_total_ms':sum(r['diagnostics']['total_ms'] for r in subset)/len(subset)}
    breakdown={}
    for dimension in ('language','family','jurisdiction'):
        breakdown[dimension]={}
        for value in sorted({r[dimension] for r in results}):
            breakdown[dimension][value]={mode:aggregate([r['metrics'] for r in results if r[dimension]==value and r['mode']==mode]) for mode in aggregate_report}
    regressions=[r['query_id'] for r in results if r['mode']=='hybrid' and r['metrics']['recall_at_k']<next(b for b in results if b['mode']=='semantic_only' and b['query_id']==r['query_id'])['metrics']['recall_at_k']]
    return {'fixture_sha256':hashlib.sha256(raw).hexdigest(),'source':'fictional PostgreSQL/pgvector retrieval benchmark',
        'query_count':len(fixture['queries']),'corpus_rows':len(fixture['corpus']),
        'configuration':asdict(RetrievalConfig()),'k_by_family':FINAL_COUNTS,
        'embedding_model':'synthetic feature vectors; not e5; no production semantic-quality inference',
        'live_supabase':{'status':'BLOCKED','reason':'authorized nonproduction credentials absent'},'live_gemini':{'status':'BLOCKED','reason':'credentials and integration dependencies absent'},'aggregate':aggregate_report,
        'breakdown':breakdown,'regressions':regressions,'per_query':results}
