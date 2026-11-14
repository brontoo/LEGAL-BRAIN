"""Actual local FastAPI HTTP, external dependencies faked. Never a live provider test."""
import concurrent.futures
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from scripts.smoke_clause_intelligence import main,TestClient
from scripts.smoke_phase2c import run as old_smoke


def execute():
    for precision in (False,True):
        os.environ['ENABLE_CLAUSE_PRECISION_V3']=str(precision).lower()
        for role in (False,True):
            os.environ['ENABLE_CLAUSE_ROLE_V2']=str(role).lower()
            old_smoke() # eight existing subsystem combinations in each of four modes
    client=TestClient(main.app)
    headers={'Authorization':'Bearer phase2b-http-fixture-only'}
    payload={'document_text':'1 Buyer shall pay Seller.\n2 يلتزم الموكل برد المصروفات.'}
    for token in ('wrong','expired-fixture-token'):
        assert client.post('/analyze/clauses',headers={'Authorization':'Bearer '+token},json=payload).status_code==401
    # Shared service tokens have no built-in expiry; this only checks invalid values.
    times=[]
    for _ in range(100):
        start=time.perf_counter();response=client.post('/analyze/clauses',headers=headers,json=payload)
        assert response.status_code==200
        times.append((time.perf_counter()-start)*1000)
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        statuses=list(pool.map(lambda _:client.post('/analyze/clauses',headers=headers,json=payload).status_code,range(40)))
    elapsed=time.perf_counter()-start
    assert set(statuses)<={200,429} and 200 in statuses
    timeout_start=time.perf_counter()
    try:
        subprocess.run([sys.executable,'-c','import time; time.sleep(3)'],timeout=.05,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        raise AssertionError('Local timeout surrogate was not terminated')
    except subprocess.TimeoutExpired:pass
    return {'scope':'actual local FastAPI HTTP with fictional source and external-service fakes',
            'feature_cases':32,'sequential_samples':100,'http_p50_ms':statistics.median(times),'http_p95_ms':sorted(times)[94],
            'http_p99_ms':sorted(times)[98],'bounded_four_thread_requests':40,'statuses':{str(code):statuses.count(code) for code in set(statuses)},
            'local_http_requests_per_second':40/elapsed,'local_slow_child_terminated_seconds':time.perf_counter()-timeout_start,
            'real_provider_timeout_test':'BLOCKED','actual_model_or_database_calls':0}


if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser();cli.add_argument('--output',required=True)
    result=execute()
    with Path(cli.parse_args().output).open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print('PASSED_PHASE2D_LOCAL_HTTP; live providers not executed')
