"""Opt-in bounded subprocess harness. Defaults to no access and honest BLOCKED."""
import argparse
from decimal import Decimal,InvalidOperation
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from .preflight import inspect,READY
from . import private


def guarded_child(kind,*,timeout=20,max_calls=1,max_cost_usd=None,execute=False,confirm_nonproduction=False):
    if kind not in ('gemini','supabase'):raise ValueError('Unknown integration')
    if type(max_calls) is not int or not 1<=max_calls<=(3 if kind=='gemini' else 5) or not 1<=timeout<=60:raise ValueError('Bounded calls/timeouts required')
    ready=inspect(confirm_nonproduction=confirm_nonproduction,operator_opt_in=execute)
    label='BLOCKED — LIVE GEMINI VALIDATION NOT EXECUTED' if kind=='gemini' else 'BLOCKED — LIVE SUPABASE / REAL E5 VALIDATION NOT EXECUTED'
    blocked={'status':label,'preflight':ready,'provider_requests':0,'result_kind':'prerequisite_check_only'}
    if not execute or not confirm_nonproduction or ready[kind]!=READY:return blocked
    if kind=='supabase' and not ready['packages']['sentence_transformers']:return blocked
    if any(os.environ.get(k,'').lower() in ('1','true','yes','on') for k in ('LANGCHAIN_TRACING','LANGCHAIN_TRACING_V2','LANGSMITH_TRACING')):
        return {**blocked,'reason':'prompt_tracing_enabled'}
    if kind=='gemini':
        try:
            budget=Decimal(str(max_cost_usd))
            rates=[Decimal(os.environ[k]) for k in ('GEMINI_INPUT_USD_PER_MTOK','GEMINI_OUTPUT_USD_PER_MTOK')]
            if not budget.is_finite() or not Decimal('0')<budget<=Decimal('5') or any(not v.is_finite() or v<0 for v in rates):raise ValueError
        except (KeyError,InvalidOperation,ValueError):return {**blocked,'reason':'explicit_bounded_cost_budget_and_operator_rates_required'}
    # No raw SDK stdout/stderr reaches logs or artifacts. Only the sanitized worker
    # report is read; process death enforces a wall limit even if an SDK ignores one.
    with tempfile.TemporaryDirectory(prefix='legal-brain-live-private-') as work:
        os.chmod(work,0o700)
        output=Path(work)/'sanitized.json'
        command=[sys.executable,'-m','validation.live_worker','--kind',kind,'--output',str(output),
                 '--timeout',str(timeout),'--max-calls',str(max_calls)]
        if kind=='gemini':command+=['--budget',str(max_cost_usd)]
        start=time.perf_counter()
        try:
            environment={**os.environ,'LEGAL_BRAIN_LIVE_WORKER_CONFIRMED':'yes'}
            result=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout+2,check=False,env=environment)
            if result.returncode or not output.exists():return {'status':'FAILED_LIVE_WORKER','provider_requests':None,'elapsed_ms':(time.perf_counter()-start)*1000}
            report=private.read(output)
            report['elapsed_ms']=(time.perf_counter()-start)*1000
            return report
        except subprocess.TimeoutExpired:
            return {'status':'FAILED_PROVIDER_TIMEOUT','provider_requests':None,'elapsed_ms':(time.perf_counter()-start)*1000,
                    'note':'Worker killed; exact provider-side billing/requests may be unknown.'}


if __name__=='__main__':
    cli=argparse.ArgumentParser()
    cli.add_argument('--kind',choices=('gemini','supabase'),required=True)
    cli.add_argument('--execute',action='store_true');cli.add_argument('--confirm-nonproduction',action='store_true')
    cli.add_argument('--timeout',type=int,default=20);cli.add_argument('--max-calls',type=int,default=1)
    cli.add_argument('--max-cost-usd');cli.add_argument('--output',required=True)
    args=cli.parse_args()
    result=guarded_child(args.kind,timeout=args.timeout,max_calls=args.max_calls,max_cost_usd=args.max_cost_usd,
                          execute=args.execute,confirm_nonproduction=args.confirm_nonproduction)
    private.write(args.output,result)
    print(result['status'])
