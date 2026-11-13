"""Unchanged Phase 2C gold; retain strict scores AND explicit new identity policy."""
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch
from clause_intelligence import AnalysisRequest,Document,analyze
from clause_intelligence.parser import parse
from clause_intelligence.roles_v2 import parties
from clause_intelligence.identity import resolve,equivalent
from clause_intelligence.evidence import validate_span
from benchmarks.roles.runner import projection,expected,walk_spans
from benchmarks.roles.metrics import empty_counts,add,finalize,normalize
from . import private

POLICY='phase2d.source_definition_equivalence.v1'


def identity_match(gold,predicted,document,clauses,entities):
    if gold is None or predicted is None:return gold is None and predicted is None
    a,b=resolve(gold,document,clauses,entities),resolve(predicted,document,clauses,entities)
    if a.ambiguity_status=='ambiguous' or b.ambiguity_status=='ambiguous':return None
    if normalize(gold,'beneficiary')==normalize(predicted,'beneficiary'):return True
    return equivalent(gold,predicted,document,clauses,entities)


def evaluate():
    path=private.REPO/'benchmarks/roles/corpus.json';raw=path.read_bytes()
    manifest=private.read(path.with_name('manifest.json'))
    if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:raise ValueError('Frozen gold changed')
    result={'fixture_sha256':manifest['sha256'],'identity_policy':POLICY,'gold_changed':False,'modes':{},
            'identity_policy_sha256':hashlib.sha256((private.REPO/'clause_intelligence/identity.py').read_bytes()).hexdigest(),
            'independent_held_out':'NOT_RUN','lawyer_assessment':'NOT_RUN','per_document':[]}
    for mode in ('role_v2','precision_v3'):
        totals=defaultdict(empty_counts);canonical=defaultdict(empty_counts)
        surface=defaultdict(lambda:{'correct':0,'present':0})
        identities=defaultdict(lambda:{'correct':0,'assessed':0,'unresolved':0})
        evidence_valid=evidence_total=attacks=attack_rejected=0;errors=[]
        object_correct=object_total=ambiguous_action_correct=ambiguous_action_total=0
        for source in json.loads(raw)['documents']:
            doc=Document(source['document_id'],source['text'],source['version']);cs=parse(doc);es=parties(cs)
            claims=[{'claim_text':'The penalty is enforceable.','claim_type':'legal_conclusion'},
                    {'claim_text':'Payment is already overdue.','claim_type':'inference'}]
            with patch.dict(os.environ,{'ENABLE_CLAUSE_ROLE_V2':'true','ENABLE_CLAUSE_PRECISION_V3':str(mode=='precision_v3').lower(),
                        'ENABLE_CLAUSE_MODEL_ASSISTANCE':'false','ENABLE_LEGAL_SKILLS':'false','ENABLE_HYBRID_LEGAL_RETRIEVAL':'false'}):
                report=analyze(AnalysisRequest(doc,language=source['language'],claims=tuple(claims)))
            spans=list(walk_spans(report));evidence_total+=len(spans);evidence_valid+=sum(validate_span(doc,cs,s) for s in spans)
            assessed=[f for f in report['findings'] if f['category']=='claim_assessment']
            attacks+=len(assessed);attack_rejected+=sum(f['evidence_status'] not in ('SUPPORTED_BY_TEXT','CONTRADICTED_BY_TEXT') for f in assessed)
            predictions=defaultdict(list)
            for o in report['obligations']:
                c=next(c for c in cs if c.clause_id==o['source_clause']);predictions[(c.span.start,c.span.end)].append(o)
            for provision in source['provisions']:
                rows=predictions.pop((provision['start'],provision['end']),[]);gold=provision['roles']
                for slot in range(max(len(rows),len(gold))):
                    g=expected(gold[slot]) if slot<len(gold) else None
                    obligation=rows[slot] if slot<len(rows) else None
                    p=projection(report,obligation,True) if obligation else None
                    groups=['all',source['language'],'category:'+source['category'],
                            'complex' if provision['tags'] else 'simple']
                    adjustment=dict(p) if p else None
                    fields=[]
                    for group in groups:fields=add(totals[group],g,p)
                    if g and p:
                        for field in ('actor','beneficiary'):
                            verdict=identity_match(g[field],p[field],doc,cs,es)
                            a,b=resolve(g[field],doc,cs,es),resolve(p[field],doc,cs,es)
                            canonical_verdict=(a.canonical_entity_id==b.canonical_entity_id
                                               if a.canonical_entity_id and b.canonical_entity_id else None)
                            for group in groups:
                                if g[field] is not None:
                                    entry=identities[group+':'+field]
                                    entry['unresolved']+=canonical_verdict is None
                                    entry['assessed']+=canonical_verdict is not None
                                    entry['correct']+=canonical_verdict is True
                                    raw_gold=gold[slot].get(field)
                                    field_role=obligation['semantic_role'][field]
                                    mention=field_role['evidence'][0]['quote'] if field_role['evidence'] else None
                                    s=surface[group+':'+field];s['present']+=1
                                    s['correct']+=normalize(raw_gold,field)==normalize(mention,field)
                            if verdict is True:adjustment[field]=g[field]
                        obj=g.get('object')
                        if obj is not None:
                            object_total+=1
                            target=gold[slot]['spans']['object'];observed=obligation['semantic_role']['object']['evidence']
                            object_correct+=bool(observed and all(target[k]==observed[0][k] for k in ('start','end','quote')))
                        if gold[slot]['action_surface']=='رد':
                            ambiguous_action_total+=1;ambiguous_action_correct+=g['action']==p['action']
                    for group in groups:add(canonical[group],g,adjustment)
                    if fields:errors.append({'document_id':source['document_id'],'provision_start':provision['start'],'slot':slot,'strict_fields':fields})
            for remaining in predictions.values():
                for o in remaining:
                    p=projection(report,o,True)
                    for group in ('all',source['language']):add(totals[group],None,p);add(canonical[group],None,p)
        if evidence_valid!=evidence_total or attacks!=attack_rejected:raise AssertionError('Critical evidence/support gate failed')
        result['modes'][mode]={'strict_historical_value_metrics':{k:finalize(v) for k,v in totals.items()},
            'equivalence_aware_metrics':{k:finalize(v) for k,v in canonical.items()},
            'strict_surface_accuracy':{k:{**v,'accuracy':v['correct']/v['present'] if v['present'] else None} for k,v in surface.items()},
            'documentary_identity_accuracy':{k:{**v,'accuracy':v['correct']/v['assessed'] if v['assessed'] else None} for k,v in identities.items()},
            'object_accuracy':{'correct':object_correct,'total':object_total,'accuracy':object_correct/object_total if object_total else None},
            'arabic_rd_action_accuracy':{'correct':ambiguous_action_correct,'total':ambiguous_action_total,'accuracy':ambiguous_action_correct/ambiguous_action_total if ambiguous_action_total else None},
            'evidence':{'valid':evidence_valid,'total':evidence_total},'unsupported_claims':{'rejected':attack_rejected,'total':attacks},
            'strict_errors':errors,'critical_documentary_error_slots':sum(bool(set(e['strict_fields'])&{'actor','polarity','conditional'}) for e in errors),
            'reviewer_disagreement_rate':None}
    return result


if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser();cli.add_argument('--output',required=True)
    value=evaluate()
    with Path(cli.parse_args().output).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print('EXECUTED_ENGINEERING_COMPARISON; independent held-out and lawyer evaluation NOT_RUN')
