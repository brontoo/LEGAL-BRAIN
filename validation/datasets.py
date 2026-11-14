"""Offline external source/label provenance, immutable freeze and overlap reporting."""
from dataclasses import asdict
import hashlib
from pathlib import Path
import json
import os
from unittest.mock import patch
from clause_intelligence import Document,AnalysisRequest,analyze
from clause_intelligence.evidence import from_payload
from . import private

NOT_RUN='NOT_RUN — INDEPENDENT HELD-OUT DATASET NOT PROVIDED'


def validate(value):
    if not isinstance(value,dict) or set(value)!={'version','source_provenance','annotation_provenance','documents'}:
        raise ValueError('External corpus format requires separate source and annotation provenance')
    for key in ('source_provenance','annotation_provenance'):
        p=value[key]
        if not isinstance(p,dict) or set(p)!={'origin','reference','independent_attested'} or not all(isinstance(p[k],str) and 1<=len(p[k])<=300 for k in ('origin','reference')) or type(p['independent_attested']) is not bool:
            raise ValueError('Invalid separate provenance')
    if not isinstance(value['version'],str) or not 1<=len(value['version'])<=80:
        raise ValueError('Corpus version required')
    docs=value['documents']
    if not isinstance(docs,list) or not 1<=len(docs)<=100:raise ValueError('Bounded corpus required')
    ids=set()
    from clause_intelligence.parser import parse
    for item in docs:
        if not isinstance(item,dict) or set(item)!={'document_id','version','text','sha256','language','provisions'}:raise ValueError('Invalid corpus document fields')
        doc=Document(item['document_id'],item['text'],item['version'])
        if doc.document_id in ids or doc.digest!=item['sha256'] or item['language'] not in ('ar','en','bilingual'):
            raise ValueError('Document identity/hash/language mismatch')
        ids.add(doc.document_id)
        if not isinstance(item['provisions'],list) or len(item['provisions'])>600:raise ValueError('Bounded annotations required')
        for provision in item['provisions']:
            if not isinstance(provision,dict) or set(provision)!={'start','end','quote','roles'}:raise ValueError('Invalid gold provision')
            s,e=provision['start'],provision['end']
            if type(s) is not int or type(e) is not int or not 0<=s<e<=len(doc.text) or doc.text[s:e]!=provision['quote']:
                raise ValueError('Gold source span mismatch')
            if not isinstance(provision['roles'],list) or len(provision['roles'])>128:raise ValueError('Bounded gold roles required')
            from benchmarks.roles.metrics import FIELDS
            for role in provision['roles']:
                if not isinstance(role,dict) or set(role)!=set(FIELDS):raise ValueError('Gold role fields must be explicit, including nulls')
                if type(role['conditional']) is not bool or any(v is not None and (not isinstance(v,str) or len(v)>1200) for k,v in role.items() if k!='conditional'):
                    raise ValueError('Invalid gold role values')
    return value


def overlap(value):
    known=set()
    for path,key in ((private.REPO/'benchmarks/roles/corpus.json','provisions'),(private.REPO/'benchmarks/clauses/fixture.json','clauses')):
        for doc in private.read(path)['documents']:
            for p in doc[key]:known.add(hashlib.sha256(p['text'].strip().encode()).hexdigest())
    count=sum(hashlib.sha256(p['quote'].strip().encode()).hexdigest() in known for d in value['documents'] for p in d['provisions'])
    return {'exact_provision_matches':count,'method':'exact trimmed UTF-8 hash; paraphrase/semantic leakage not detected'}


def freeze(source,destination):
    value=validate(private.read(source))
    root=private.directory(destination)
    fingerprint=private.write(root/'corpus.json',value)
    manifest={'schema_version':'phase2d.external.v1','version':value['version'],'sha256':fingerprint,
              'source_provenance':value['source_provenance'],'annotation_provenance':value['annotation_provenance'],
              'overlap':overlap(value),'configuration':{'matching':'exact_source_boundary_then_role_ordinal','gold_mutation':False}}
    private.write(root/'manifest.json',manifest)
    (root/'corpus.json').chmod(0o400)
    (root/'manifest.json').chmod(0o400)
    return manifest


def evaluate(frozen=None):
    if frozen is None:return {'status':NOT_RUN,'metrics':None,'expert_legal_validation':'NOT_RUN'}
    root=private.outside_repository(frozen)
    manifest=private.read(root/'manifest.json'); path=root/'corpus.json'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Frozen corpus changed')
    value=validate(private.read(path))
    if manifest['source_provenance']!=value['source_provenance'] or manifest['annotation_provenance']!=value['annotation_provenance']:
        raise ValueError('Frozen provenance mismatch')
    from benchmarks.roles.metrics import empty_counts,add,finalize
    from benchmarks.roles.runner import projection
    totals={mode:empty_counts() for mode in ('legacy','role_v2','precision_v3')}
    for item in value['documents']:
        for mode in totals:
            with patch.dict(os.environ,{'ENABLE_CLAUSE_ROLE_V2':str(mode!='legacy').lower(),'ENABLE_CLAUSE_PRECISION_V3':str(mode=='precision_v3').lower(),
                                       'ENABLE_CLAUSE_MODEL_ASSISTANCE':'false','ENABLE_LEGAL_SKILLS':'false','ENABLE_HYBRID_LEGAL_RETRIEVAL':'false'}):
                r=analyze(AnalysisRequest.from_payload({'document_id':item['document_id'],'document_version':item['version'],'document_text':item['text'],'language':item['language']}))
            predictions={}
            for o in r['obligations']:
                c=next(c for c in r['clauses'] if c['clause_id']==o['source_clause'])
                predictions.setdefault((c['span']['start'],c['span']['end']),[]).append(projection(r,o,mode!='legacy'))
            for provision in item['provisions']:
                predicted=predictions.pop((provision['start'],provision['end']),[]); gold=provision['roles']
                for i in range(max(len(predicted),len(gold))):add(totals[mode],gold[i] if i<len(gold) else None,predicted[i] if i<len(predicted) else None)
            for leftovers in predictions.values():
                for p in leftovers:add(totals[mode],None,p)
    independent=all(value[k]['independent_attested'] for k in ('source_provenance','annotation_provenance'))
    return {'status':'EVALUATED_SUPPLIED_CORPUS','manifest_sha256':private.digest(manifest),'metrics':{m:finalize(v) for m,v in totals.items()},
            'independence':'supplier_attestation_not_expert_verification' if independent else 'NOT_INDEPENDENTLY_ATTESTED',
            'overlap':manifest['overlap'],'expert_legal_validation':'NOT_RUN'}
