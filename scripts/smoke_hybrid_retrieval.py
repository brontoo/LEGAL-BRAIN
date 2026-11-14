"""Real HTTP transport smoke with offline external-service fakes; never a live model test."""
import json
import os
import sys
os.environ['API_TOKEN']='hybrid-http-fixture-only'
from tests import fake_deps
fake_deps.install()
for name in list(sys.modules):
    if name=='fastapi' or name.startswith('fastapi.') or name=='pydantic' or name.startswith('pydantic.'):
        del sys.modules[name]
from fastapi.testclient import TestClient
from tests.retrieval.helpers import row
from citations import CITATIONS_BEGIN,CITATIONS_END
import main
client=TestClient(main.app)
headers={'Authorization':'Bearer hybrid-http-fixture-only'}
assert client.post('/generate',json={'prompt':'test'}).status_code==401
for skills in (False,True):
    for hybrid in (False,True):
        os.environ['ENABLE_LEGAL_SKILLS']=str(skills).lower()
        os.environ['ENABLE_HYBRID_LEGAL_RETRIEVAL']=str(hybrid).lower()
        fake_deps.reset()
        source=row(family='contracts',text='يلتزم المورد بتقديم تقرير شهري عن الخدمات المتفق عليها.')
        for rpc in ('match_legal_contracts','hybrid_semantic_v1','hybrid_lexical_v1'):
            fake_deps.FAKE_SUPABASE.set_rows(rpc,[source])
        fake_deps.AGENT_SCRIPT=[{'tool':'search_contract_clauses','args':{'query':'review agreement'}},
            {'content':source['chunk_content']+f'\n{CITATIONS_BEGIN}\nC1 :: تقديم تقرير شهري عن الخدمات المتفق عليها\n{CITATIONS_END}'}]
        response=client.post('/generate',headers=headers,json={'prompt':'Review agreement','doc_type':'agreement',
            'retrieval_context':{'jurisdiction':{'governing_law':'uae_federal'},'as_of':'2026-01-15'}})
        assert response.status_code==200,response.status_code
        frames=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        by_type={frame['type']:frame for frame in frames}
        assert by_type['citations']['report']['verified']
        assert skills==('skill_diagnostics' in by_type['done'])
        assert hybrid==any(name=='hybrid_semantic_v1' for name,_ in fake_deps.FAKE_SUPABASE.calls)
os.environ['ENABLE_LEGAL_SKILLS']='false'
os.environ['ENABLE_HYBRID_LEGAL_RETRIEVAL']='true'
assert client.post('/generate',headers=headers,json={'prompt':'test','retrieval_context':{'jurisdiction':{'governing_law':'UK'}}}).status_code==400
assert client.post('/generate',headers=headers,json={'prompt':'test','retrieval_context':{'as_of':'2026-02-30'}}).status_code==400
assert client.get('/retrieval/debug',headers=headers).status_code==404
print('PASSED: real HTTP auth, all four flags, hybrid evidence/citations, invalid contexts and no debug endpoint; external services mocked')
