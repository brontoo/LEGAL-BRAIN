"""Exact identifiers are conjunctions, not unrelated matching numbers."""
import re
from .normalization import normalize
from .schemas import LegalReference,RetrievalError

PATTERNS = (
    ('article', r'(?:\barticle\s+|المادة\s*)([0-9]+(?:[./][0-9]+)*)'),
    ('clause', r'(?:\bclause\s+|البند\s*)([0-9]+(?:[./][0-9]+)*)'),
    ('decree_law', r'(?:\bdecree[- ]law\s+(?:no\.?\s*)?|مرسوم\s+بقانون\s+(?:رقم\s*)?)([0-9]+)'),
    ('law', r'(?:\blaw\s+no\.?\s*|القانون\s+رقم\s*|قانون\s+رقم\s*)([0-9]+)'),
    ('regulation', r'(?:\bregulation\s+no\.?\s*|لائحة\s+رقم\s*)([0-9]+)'),
)


def references(query: str) -> tuple[LegalReference,...]:
    text=normalize(query)
    found=[]
    for kind,pattern in PATTERNS:
        for match in re.finditer(pattern,text):
            # A slash and a decimal point remain distinct; no subsection inference.
            value=match.group(1)
            if re.match(r'(?:\w|[./][0-9])',text[match.end():]):
                continue
            if kind in ('law','decree_law','regulation'):
                year=re.match(r'\s+(?:of|لسنة)\s+([0-9]{4})(?!\w)',text[match.end():])
                if year: value+=':'+year.group(1)
            ref=LegalReference(kind,value)
            if ref not in found:
                found.append(ref)
    # "decree law no" must not also be assigned a generic law identity.
    if any(ref.kind=='decree_law' for ref in found):
        found=[ref for ref in found if ref.kind!='law']
    if len(found)>16: raise RetrievalError('Too many exact references')
    return tuple(found)


def exact_match(query_refs, candidate) -> tuple[str,...]:
    if not query_refs:
        return ()
    p=candidate.provenance
    source_refs=references(candidate.title+'\n'+candidate.text[:20000-len(candidate.title)-1])
    basis=[]
    trusted_fields=p.identity_verified and p.verified_at is not None
    for ref in query_refs:
        structured = trusted_fields and ((ref.kind=='article' and p.article_reference is not None and normalize(p.article_reference)==ref.value)
                      or (ref.kind=='clause' and p.clause_reference is not None and normalize(p.clause_reference)==ref.value)
                      or (ref.kind in ('law','decree_law','regulation') and p.instrument_id is not None
                          and normalize(p.instrument_id)==ref.kind+':'+ref.value))
        if structured:
            basis.append(ref.kind+':structured')
        elif ref in source_refs:
            basis.append(ref.kind+':source_text')
        else:
            return ()
    return tuple(basis)
