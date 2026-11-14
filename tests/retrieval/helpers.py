from types import SimpleNamespace
from retrieval.schemas import RetrievalContext,RetrievalRequest
from skills.schemas import JurisdictionContext

VECTOR=[1.0]+[0.0]*1023


def row(identity=1, *, family='legislation',jurisdiction='uae_federal',source=None,verified=True,text=None,**updates):
    data={'source_class':source or ('official_legislation' if family=='legislation' else 'drafting_precedent' if family=='drafts' else 'contractual_evidence'),
          'classification_verified':True,'identity_verified':verified,'jurisdiction_verified':verified,
          'official_url':'https://official.example.invalid/fictional','verified_at':'2026-01-01',
          'effective_from':'2020-01-01','temporal_verified_through':'2026-12-31',
          'jurisdiction':{'governing_law':jurisdiction},'instrument_id':'law:12',
          'article_reference':'15','source_document_id':f'fictional-{identity}'}
    data.update(updates)
    return {'id':identity,'family':family,'document_name':'FICTIONAL Law No. 12 — not real law',
            'chunk_content':text or 'Article 15: fictional payment obligations. المادة ١٥: التزامات دفع افتراضية.',
            'metadata':{'retrieval_v1':data},'similarity':.9}


def request(query='Article 15 of Law No. 12',family='legislation',jurisdiction='uae_federal',as_of=None):
    from datetime import date
    return RetrievalRequest(query,family,RetrievalContext(JurisdictionContext(governing_law=jurisdiction),as_of or date(2026,1,15)))


class Client:
    def __init__(self,semantic=(),lexical=(),failures=None):
        self.results={'hybrid_semantic_v1':list(semantic),'hybrid_lexical_v1':list(lexical)}
        self.calls=[];self.failures=failures or {}
    def rpc(self,name,params):
        self.calls.append((name,params))
        def execute():
            if name in self.failures: raise self.failures[name]
            return SimpleNamespace(data=self.results.get(name,[]))
        return SimpleNamespace(execute=execute)
