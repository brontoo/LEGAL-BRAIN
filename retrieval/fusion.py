"""Standard rank-only RRF. Exact priority is a separate deterministic option."""
from dataclasses import replace
from .schemas import RetrievalError


def fuse(semantic, lexical, *, k=60, exact_priority=True, prefer_compatible=False):
    if type(k) is not int or k<1: raise RetrievalError('Invalid RRF constant')
    merged={}
    conflicts=set()
    for name,rows in (('semantic',semantic),('lexical',lexical)):
        seen=set();rank=0
        for c in rows:
            key=c.identity
            previous=merged.get(key)
            if key in seen:
                if previous and (previous.text!=c.text or previous.title!=c.title or previous.provenance!=c.provenance):
                    conflicts.add(key)
                continue
            seen.add(key);rank+=1
            if previous and (previous.text!=c.text or previous.title!=c.title or previous.provenance!=c.provenance):
                conflicts.add(key)
                continue
            current=previous or c
            score=current.fusion_score+1/(k+rank)
            current=replace(current,fusion_score=score,**{name+'_rank':rank})
            merged[key]=current
    ordered=[c for key,c in merged.items() if key not in conflicts]
    ordered.sort(key=lambda c:(-int(exact_priority and bool(c.exact_basis)),-int(prefer_compatible and c.eligibility is not None and c.eligibility.decision=='compatible'),-c.fusion_score,c.family,int(c.chunk_id)))
    return tuple(ordered),len(conflicts)


def diversify(candidates, limit, per_document):
    selected=[]; counts={}; excluded=0
    for c in candidates:
        # Never treat a title alone as a document identity.
        key=(c.family,c.provenance.source_document_id) if c.provenance.source_document_id else c.identity
        if counts.get(key,0)>=per_document:
            excluded+=1
            continue
        if len(selected)<limit:
            selected.append(c);counts[key]=counts.get(key,0)+1
    return tuple(selected),excluded
