"""Bounded local deterministic time/memory measurements, no network or real clients."""
import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from clause_intelligence import AnalysisRequest,analyze


def run(samples=100):
    if type(samples) is not int or not 20<=samples<=200:raise ValueError('Use 20..200 bounded samples')
    results={}
    request=AnalysisRequest.from_payload({'document_id':'performance-fictional','document_text':'1 Buyer shall pay Seller AED 1700 after invoice receipt.\n2 لا يحق للمستأجر التنازل دون موافقة خطية.'})
    for improved in (False,True):
        values=[];cpu=time.process_time()
        with patch.dict(os.environ,{'ENABLE_CLAUSE_ROLE_V2':'true','ENABLE_CLAUSE_PRECISION_V3':str(improved).lower(),'ENABLE_CLAUSE_MODEL_ASSISTANCE':'false',
                                   'ENABLE_HYBRID_LEGAL_RETRIEVAL':'false','ENABLE_LEGAL_SKILLS':'false'}):
            analyze(request)
            for _ in range(samples):
                start=time.perf_counter();analyze(request);values.append((time.perf_counter()-start)*1000)
            tracemalloc.start()
            for _ in range(10):analyze(request)
            before=tracemalloc.get_traced_memory()[0]
            for _ in range(30):analyze(request)
            after,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            start=time.perf_counter()
            with ThreadPoolExecutor(2) as pool:list(pool.map(lambda _:analyze(request),range(20)))
            concurrent_seconds=time.perf_counter()-start
        ordered=sorted(values)
        results['precision_v3' if improved else 'role_v2']={'samples':samples,'p50_ms':statistics.median(values),
            'p95_ms':ordered[int(.95*(samples-1))],'p99_ms':ordered[int(.99*(samples-1))] if samples>=100 else None,
            'mean_ms':statistics.mean(values),'cpu_seconds':time.process_time()-cpu,'peak_python_bytes':peak,
            'retained_python_growth_bytes_over_30_requests':after-before,'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'two_thread_core_requests_per_second':20/concurrent_seconds,'memory_scope':'Python trace excludes pre-existing allocations; RSS is process lifetime high-water mark'}
    return {'scope':'small fictional deterministic core; HTTP admission/provider/stress reported separately','results':results}


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--output',required=True);cli.add_argument('--samples',type=int,default=100)
    a=cli.parse_args();value=run(a.samples)
    with Path(a.output).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
