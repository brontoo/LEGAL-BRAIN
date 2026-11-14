"""Allocate only final evidence; original candidates remain intact for internal audit."""
from dataclasses import replace,asdict
import json
from citations import Evidence,format_evidence_block
import untrusted


def displayed_text(text: str, limit: int) -> str:
    # Use the host's existing escaping policy and then retain EXACTLY the body the
    # model sees, not unseen suffixes or invented truncation-marker prose.
    fenced=untrusted.fence(text[:limit].strip())
    if not fenced: return ''
    return fenced.split(untrusted.FENCE_OPEN+'\n',1)[1].rsplit('\n'+untrusted.FENCE_CLOSE,1)[0]


def build(result,collector,family,limit=1800):
    allocator=collector.allocator
    evidence=[];blocks=[]
    for candidate in result.candidates:
        text=displayed_text(candidate.text,limit)
        if not text: continue
        key=(family,candidate.chunk_id,candidate.title,text)
        with collector._hybrid_lock:
            item=collector._hybrid_evidence.get(key)
            if item is None:
                item=Evidence(allocator.next_ref(family),candidate.chunk_id,candidate.title,text,
                              candidate.similarity,family)
                collector._hybrid_evidence[key]=item
                collector.add([item])
        evidence.append(item)
        e=candidate.eligibility
        status=('RESEARCH LEAD — UNVERIFIED / مادة بحث غير متحققة' if e.decision=='unknown'
                else 'Metadata compatible only — legal applicability requires authority checks / توافق بيانات فقط')
        # Arbitrary titles stay inside an untrusted fence; the reference header is
        # constructed only from validated family/ID. Collector keeps the real title.
        header=f'Source class: {candidate.provenance.source_class.value}; {status}. '
        header+='Quotation matching is not source, jurisdiction or temporal verification.'
        known={key:value for key,value in asdict(candidate.provenance.jurisdiction).items() if value!='unknown'}
        header+=' Source jurisdiction metadata: '+json.dumps(known,sort_keys=True)+'; '
        header+=f'identity={e.identity_status}; jurisdiction={e.jurisdiction_status}; temporal={e.temporal_status}.'
        blocks.append(header+'\n'+untrusted.fence(candidate.title)+'\n'+
            format_evidence_block([replace(item,document_name=family+'/'+candidate.chunk_id)]))
    result.diagnostics['displayed_chars']=sum(len(item.text) for item in evidence)
    prefix=('استرجاع جزئي؛ لم تكتمل جميع مسارات البحث.\n' if result.status=='degraded' else '')
    content=prefix+'\n\n'.join(blocks)
    result.diagnostics['model_context_chars']=len(content)
    return content
