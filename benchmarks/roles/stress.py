"""Disposable local child-process tests, CPU/address-space/time bounded. No network."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import tracemalloc
from unittest.mock import patch
from clause_intelligence import AnalysisRequest, ClauseError, analyze

CASES = ('near_limit', 'nested', 'mixed_unicode', 'duplicates', 'repeated_definitions',
         'repeated_references', 'unpunctuated_allowed', 'oversized_paragraph', 'oversized_document', 'dense_modals')


def fixture(name):
    if name == 'near_limit':
        rows = []
        for i in range(1, 501):
            prefix = f'{i} Supplier shall deliver parcel {i} after written approval. '
            rows.append(prefix+'x'*(198-len(prefix)))
        return '\n'.join(rows)
    if name == 'nested':
        return '\n'.join('.'.join(['1']*i)+' Detail e\u0301 📄 مَادَّة.' for i in range(1, 151))
    if name == 'mixed_unicode':
        return '\n'.join(f'{i} يَلْتَزِم المشتري بالسداد. Buyer may retain سجل e\u0301 🦉.' for i in range(1, 301))
    if name == 'duplicates':
        return '\n'.join('1 Buyer shall pay subject to Clause 1.' for _ in range(300))
    if name == 'repeated_definitions':
        return '\n'.join(f'{i} "Services" means scope-{i}.' for i in range(1, 501))
    if name == 'repeated_references':
        return '\n'.join(f'{i} Subject to Clause 1 and Clause 2 and Clause 3, Buyer may retain records.' for i in range(1, 301))
    if name == 'unpunctuated_allowed':
        return '1 '+'paragraph '*1900
    if name == 'oversized_paragraph':
        return '1 '+'x'*20001
    if name == 'oversized_document':
        return 'x'*100001
    if name == 'dense_modals':
        return '1 '+'Buyer shall pay '*180
    raise ValueError('Unknown stress case')


def run_case(name, mode):
    # Child only; never alter limits of the application, tools or parent process.
    resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    text = fixture(name)
    start = time.perf_counter()
    tracemalloc.start()
    status = 'accepted'
    with patch.dict(os.environ, {'ENABLE_CLAUSE_ROLE_V2': str(mode == 'role_v2').lower(),
                                'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false', 'ENABLE_LEGAL_SKILLS': 'false',
                                'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'false'}):
        try:
            report = analyze(AnalysisRequest.from_payload({'document_text': text, 'document_id': 'stress-fictional'}))
            counts = {'clauses': len(report['clauses']), 'obligations': len(report['obligations'])}
        except ClauseError:
            status, counts = 'rejected_safely', {}
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    expected_rejection = name in ('oversized_paragraph', 'oversized_document') or name == 'dense_modals' and mode == 'role_v2'
    return {'case': name, 'mode': mode, 'characters': len(text), 'status': status, 'counts': counts,
            'expected': 'rejected_safely' if expected_rejection else 'accepted',
            'elapsed_ms_with_tracemalloc': (time.perf_counter()-start)*1000,
            'peak_python_bytes': peak, 'process_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def evaluate():
    results = []
    for mode in ('legacy', 'role_v2'):
        for name in CASES:
            try:
                run = subprocess.run([sys.executable, '-m', 'benchmarks.roles.stress', '--case', name, '--mode', mode],
                                     capture_output=True, text=True, timeout=30)
                result = json.loads(run.stdout) if run.returncode == 0 else {'case': name, 'mode': mode, 'status': 'resource_or_process_failure', 'exit_code': run.returncode}
            except subprocess.TimeoutExpired:
                result = {'case': name, 'mode': mode, 'status': 'timeout'}
            results.append(result)
            print(json.dumps({k: result[k] for k in ('case', 'mode', 'status')}), flush=True)
    return {'scope': 'local disposable Python processes, fictional input, not production stress testing',
            'limits': {'address_space_bytes': 512*1024*1024, 'cpu_seconds': 20, 'wall_seconds_per_case': 30},
            'results': results, 'all_expected': all(r.get('status') == r.get('expected') for r in results)}


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--case', choices=CASES)
    cli.add_argument('--mode', choices=('legacy', 'role_v2'))
    cli.add_argument('--output')
    args = cli.parse_args()
    if args.case:
        print(json.dumps(run_case(args.case, args.mode)))
    else:
        if not args.output:
            cli.error('--output is required')
        result = evaluate()
        with Path(args.output).open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        if not result['all_expected']:
            raise SystemExit(1)
