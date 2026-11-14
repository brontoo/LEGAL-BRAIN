"""Hybrid orchestration. Operational failure never restores legally excluded rows."""
from dataclasses import replace
import time
from . import semantic, lexical
from .config import RetrievalConfig, FINAL_COUNTS
from .context import RetrievalSession
from .eligibility import evaluate
from .fusion import fuse,diversify
from .normalization import normalize
from .provenance import parse
from .query_analysis import references,exact_match
from .schemas import RetrievalResult,RetrievalError


class HybridRetrievalEngine:
    def __init__(self,client,encode,config=None):
        self.client=client;self.encode=encode;self.config=config or RetrievalConfig.from_env()

    def search(self, request, session=None):
        started=time.perf_counter(); config=self.config
        session=session or RetrievalSession(request.context)
        if not normalize(request.query) or request.context.unsupported:
            return RetrievalResult((),'unsupported_jurisdiction' if request.context.unsupported else 'empty_query',
                                   {'mode':'hybrid','selected':0,'candidate_count':0,'failure_categories':[]})
        try:
            refs=references(request.query)
        except RetrievalError:
            return RetrievalResult((),'invalid_query',{'mode':'hybrid','selected':0,'candidate_count':0,'failure_categories':['invalid_query']})
        branches=(semantic.retrieve(self.client,self.encode,session,request,config),
                  lexical.retrieve(self.client,request,config))
        accepted=[];filtered=invalid=unknown=0
        observed={};blocked=set();contradictions=set()
        for branch in branches:
            current=[]
            for row in branch.rows[:config.candidate_pool]:
                try:
                    c=parse(row,request.family)
                    previous=observed.get(c.identity)
                    if previous and (previous.text!=c.text or previous.title!=c.title or previous.provenance!=c.provenance):
                        contradictions.add(c.identity)
                    observed[c.identity]=c
                    decision=evaluate(c,request)
                    if decision.decision=='incompatible':blocked.add(c.identity)
                    if decision.decision=='incompatible' or decision.decision=='unknown' and config.unknown_policy=='exclude':
                        filtered+=1;continue
                    if decision.decision=='unknown': unknown+=1
                    current.append(replace(c,eligibility=decision,exact_basis=exact_match(refs,c)))
                except RetrievalError:
                    invalid+=1
            accepted.append(current)
        # One branch must never reintroduce a source excluded by the other.
        blocked.update(contradictions)
        accepted=[[c for c in branch if c.identity not in blocked] for branch in accepted]
        invalid+=len(contradictions)
        fusion_started=time.perf_counter()
        fused,conflicts=fuse(*accepted,k=config.rrf_k,exact_priority=config.exact_priority,prefer_compatible=config.prefer_compatible)
        selected,diversity=diversify(fused,FINAL_COUNTS[request.family],config.max_per_document)
        failures=[b.status for b in branches if b.status!='ok']
        if invalid+conflicts:failures.append('invalid_metadata')
        status=('degraded' if selected else 'unavailable') if failures else ('ok' if selected else 'no_eligible_sources')
        diagnostic={'mode':'hybrid' if not failures else 'degraded',
            'branches':{b.name:{'status':b.status,'count':len(b.rows),'elapsed_ms':round(b.elapsed_ms,3)} for b in branches},
            'candidate_count':sum(len(b.rows) for b in branches),'selected':len(selected),
            'filtered':filtered,'invalid_metadata':invalid+conflicts,'unknown_metadata':unknown,
            'diversity_excluded':diversity,'exact_matches':sum(bool(c.exact_basis) for c in selected),
            'selected_families':[request.family] if selected else [],'failure_categories':sorted(set(failures)),
            'fusion_ms':round((time.perf_counter()-fusion_started)*1000,3),
            'selected_passage_chars':sum(len(c.text) for c in selected),
            'total_ms':round((time.perf_counter()-started)*1000,3)}
        session.record(diagnostic)
        return RetrievalResult(selected,status,diagnostic)
