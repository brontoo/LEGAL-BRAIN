"""Real FastAPI HTTP transport; external-service fakes, never a live model validation."""
import itertools
import json
import os
import sys
os.environ['API_TOKEN'] = 'phase2b-http-fixture-only'
from tests import fake_deps
fake_deps.install()
for name in list(sys.modules):
    if name == 'fastapi' or name.startswith('fastapi.') or name == 'pydantic' or name.startswith('pydantic.'):
        del sys.modules[name]
from fastapi.testclient import TestClient
import main
from tests.retrieval.helpers import row
from citations import CITATIONS_BEGIN, CITATIONS_END


def run():
    client = TestClient(main.app)
    headers = {'Authorization': 'Bearer phase2b-http-fixture-only'}
    payload = {'document_text': 'FICTIONAL\n\n1 Supplier shall pay AED 500 within 15 days after invoice receipt.',
               'document_id': 'http-fictional', 'document_version': 'v1'}
    assert client.post('/analyze/clauses', json=payload).status_code == 401
    assert client.post('/analyze/clauses', headers={'Authorization': 'Bearer wrong'}, json=payload).status_code == 401
    for skills, hybrid, clause in itertools.product((False, True), repeat=3):
        os.environ['ENABLE_LEGAL_SKILLS'] = str(skills).lower()
        os.environ['ENABLE_HYBRID_LEGAL_RETRIEVAL'] = str(hybrid).lower()
        os.environ['ENABLE_CLAUSE_INTELLIGENCE'] = str(clause).lower()
        fake_deps.reset()
        response = client.post('/analyze/clauses', headers=headers, json=payload)
        assert response.status_code == (200 if clause else 404), response.status_code
        assert not fake_deps.FAKE_SUPABASE.calls
        if clause:
            report = response.json()
            assert report['human_review_status'] == 'pending'
            assert report['obligations'][0]['trigger'] == 'after invoice receipt'
            assert report['dates'][0]['resolved_date'] is None
        source = row(family='contracts', text='يلتزم المورد بتقديم تقرير شهري عن الخدمات المتفق عليها.')
        for rpc in ('match_legal_contracts', 'hybrid_semantic_v1', 'hybrid_lexical_v1'):
            fake_deps.FAKE_SUPABASE.set_rows(rpc, [source])
        fake_deps.AGENT_SCRIPT = [{'tool': 'search_contract_clauses', 'args': {'query': 'review agreement'}},
             {'content': source['chunk_content']+f'\n{CITATIONS_BEGIN}\nC1 :: تقديم تقرير شهري عن الخدمات المتفق عليها\n{CITATIONS_END}'}]
        response = client.post('/generate', headers=headers, json={'prompt': 'Review agreement', 'doc_type': 'agreement'})
        assert response.status_code == 200
        frames = {f['type']: f for f in [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]}
        assert frames['citations']['report']['verified']
        assert skills == ('skill_diagnostics' in frames['done'])
        assert hybrid == any(name == 'hybrid_semantic_v1' for name, _ in fake_deps.FAKE_SUPABASE.calls)
    os.environ['ENABLE_CLAUSE_INTELLIGENCE'] = 'true'
    for bad in ({'document_text': 'X'*100001}, {'document_text': 'PRIVATE', 'path': '/etc/passwd'},
                {'document_text': 'PRIVATE', 'jurisdiction': {'governing_law': 'UK'}}):
        response = client.post('/analyze/clauses', headers=headers, json=bad)
        assert response.status_code == 400 and 'PRIVATE' not in response.text
    response = client.post('/analyze/clauses', headers=headers, content='x'*650001)
    assert response.status_code == 413
    response = client.post('/analyze/clauses', headers=headers, content='['*3000)
    assert response.status_code == 400
    assert client.get('/analyze/debug', headers=headers).status_code == 404
    token = main.API_TOKEN
    main.API_TOKEN = ''
    try:
        assert client.post('/analyze/clauses', json=payload).status_code == 503
    finally:
        main.API_TOKEN = token
    print('PASSED: actual HTTP authentication, eight flags, unchanged generation citations/SSE, bounded confidential input and no debug route; external services faked.')


if __name__ == '__main__':
    run()
