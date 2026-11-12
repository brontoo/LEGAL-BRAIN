"""Read optional human-reviewed metadata without upgrading legacy records."""
from datetime import date
import math
import re
from urllib.parse import urlparse
from skills.schemas import JurisdictionContext, SkillError
from .schemas import Candidate, Provenance, SourceClass, RetrievalError


def _date(value):
    if value in (None,''): return None
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):
        raise RetrievalError('Invalid provenance date')
    try: return date.fromisoformat(value)
    except (TypeError,ValueError) as exc: raise RetrievalError('Invalid provenance date') from exc


def _text(value,limit=500):
    if value is None: return None
    if not isinstance(value,str) or len(value)>limit or '\x00' in value:
        raise RetrievalError('Invalid provenance text')
    return value or None


def parse(row: dict, family: str) -> Candidate:
    if not isinstance(row,dict): raise RetrievalError('Invalid retrieval row')
    if row.get('family',family)!=family: raise RetrievalError('Source family mismatch')
    identity=str(row.get('id',''))
    if not re.fullmatch(r'[1-9][0-9]{0,18}',identity):
        raise RetrievalError('Missing or invalid stable chunk identity')
    text=row.get('chunk_content')
    title=row.get('document_name')
    if not isinstance(text,str) or not text.strip() or not isinstance(title,str) or len(title)>500:
        raise RetrievalError('Invalid evidence content')
    raw=row.get('metadata')
    if raw is None: raw={}
    if not isinstance(raw,dict): raise RetrievalError('Invalid metadata')
    data=raw.get('retrieval_v1',{})
    if not isinstance(data,dict): raise RetrievalError('Invalid provenance namespace')
    for key in ('classification_verified','identity_verified','jurisdiction_verified','ai_generated'):
        if key in data and type(data[key]) is not bool: raise RetrievalError('Invalid provenance status')
    try:
        source=SourceClass(data.get('source_class','unknown'))
        context=JurisdictionContext.from_mapping(data.get('jurisdiction'))
    except (ValueError,TypeError,SkillError) as exc: raise RetrievalError('Invalid provenance classification') from exc
    declared_source=source
    if not data.get('classification_verified',False): source=SourceClass.UNKNOWN
    url=_text(data.get('official_url'),2000)
    if url:
        parsed=urlparse(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            raise RetrievalError('Invalid official source URL')
    kwargs={key:_text(data.get(key)) for key in ('instrument_id','issuing_authority','original_title',
              'article_reference','clause_reference','language','amendment_version','source_document_id','content_checksum')}
    dates={key:_date(data.get(key)) for key in ('publication_date','effective_from','effective_to','verified_at','temporal_verified_through')}
    if dates['effective_from'] and dates['effective_to'] and dates['effective_from']>dates['effective_to']:
        raise RetrievalError('Conflicting temporal range')
    provenance=Provenance(source_class=source,declared_source_class=declared_source,official_url=url,jurisdiction=context,
        jurisdiction_verified=data.get('jurisdiction_verified',False),
        identity_verified=data.get('identity_verified',False),ai_generated=data.get('ai_generated',False),**kwargs,**dates)
    similarity=row.get('similarity')
    if similarity is not None and (type(similarity) not in (float,int) or not math.isfinite(similarity) or not -1<=similarity<=1):
        raise RetrievalError('Invalid semantic similarity')
    return Candidate(family,identity,title,text,provenance,similarity)
