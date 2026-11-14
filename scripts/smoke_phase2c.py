"""Real local HTTP/proxy-compatible transport, external dependencies mocked."""
import concurrent.futures
import os
import threading
from unittest.mock import patch
from scripts.smoke_clause_intelligence import run, main, TestClient


if __name__ == '__main__':
    for improved in (False, True):
        os.environ['ENABLE_CLAUSE_ROLE_V2'] = str(improved).lower()
        run()  # All eight existing feature combinations through real HTTP/SSE.
        client = TestClient(main.app)
        headers = {'Authorization': 'Bearer phase2b-http-fixture-only'}
        response = client.post('/analyze/clauses', headers=headers, json={'document_text': '1 Neither party may disclose private records.'})
        assert response.status_code == 200
        report = response.json()
        assert report['schema_version'] == 'phase2b.v1'
        assert improved == ('role_analysis' in report)
        assert report['obligations'][0]['kind'] == ('prohibited' if improved else 'discretionary_right')
    started, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    active = 0
    def occupied(*args, **kwargs):
        global active
        with lock:
            active += 1
            if active == 2:
                started.set()
        release.wait(5)
        return {'status': 'local_transport_capacity_fixture'}
    with patch.object(main, 'analyze_document_clauses', side_effect=occupied), concurrent.futures.ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(client.post, '/analyze/clauses', headers=headers, json={'document_text': 'Fictional local load fixture.'}) for _ in range(2)]
        try:
            assert started.wait(3)
            busy = client.post('/analyze/clauses', headers=headers, json={'document_text': 'Fictional third request.'})
            assert busy.status_code == 429 and busy.headers['retry-after'] == '2'
        finally:
            release.set()
        assert all(job.result().status_code == 200 for job in jobs)
    print('PASSED: real HTTP sixteen flag combinations, both clause modes, unchanged generation citations/SSE/auth and local two-slot capacity/429. External services mocked; no live reasoning claim.')
