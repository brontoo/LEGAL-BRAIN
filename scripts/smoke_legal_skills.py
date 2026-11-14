"""Optional isolated HTTP smoke test; requires FastAPI/Pydantic/httpx, no live services.

Run from repository root: PYTHONPATH=. python scripts/smoke_legal_skills.py
"""
import os
import sys
os.environ['ENABLE_LEGAL_SKILLS'] = 'true'
os.environ['API_TOKEN'] = 'local-test-only'
from tests import fake_deps
fake_deps.install()
# Keep LLM/storage/model fakes; use real HTTP routing and Pydantic validation.
for name in list(sys.modules):
    if name == 'fastapi' or name.startswith('fastapi.') or name == 'pydantic' or name.startswith('pydantic.'):
        del sys.modules[name]
from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
headers = {'Authorization': 'Bearer local-test-only'}
assert client.get('/skills').status_code == 401
assert client.post('/skills/resolve', json={'prompt': 'nda'}).status_code == 401
response = client.get('/skills', headers=headers)
assert response.status_code == 200 and len(response.json()['skills']) == 5
assert 'instructions' not in response.text and '/workspace' not in response.text
response = client.post('/skills/resolve', headers=headers, json={'prompt': 'Assess this confidentiality agreement'})
assert response.status_code == 200 and response.json()['selected_skill'] == 'uae-nda-review'
assert client.post('/skills/resolve', headers=headers, json={'prompt': ''}).status_code == 422
assert client.post('/skills/resolve', headers=headers, json={'prompt': 'nda', 'skill_id': '../etc/passwd'}).status_code == 400
assert client.post('/skills/resolve', headers=headers, json={'prompt': 'nda', 'jurisdiction': {'governing_law': 'UK'}}).status_code == 400
fake_deps.AGENT_SCRIPT = [{'content': 'وثيقة اختبار دون أسانيد.'}]
response = client.post('/generate', headers=headers, json={'prompt': 'Review agreement', 'skill_id': 'uae-contract-review'})
assert response.status_code == 200, response.text
assert response.headers['content-type'].startswith('text/event-stream')
assert response.headers['x-legal-skill'] == 'uae-contract-review'
assert '"type": "citations"' in response.text
assert '"type": "facts"' in response.text
os.environ['ENABLE_LEGAL_SKILLS'] = 'false'
assert client.get('/skills', headers=headers).json() == {'enabled': False, 'skills': []}
assert client.post('/skills/resolve', headers=headers, json={'prompt': 'nda'}).status_code == 404
response = client.post('/generate', headers=headers, json={'prompt': 'Draft agreement'})
assert response.status_code == 200
assert 'x-legal-skill' not in response.headers
print('PASS: real FastAPI/Pydantic HTTP authentication, discovery, routing, invalid inputs, enabled/disabled generation and SSE verification frames')
