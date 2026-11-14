"""Paired acceptance report. Default: offline plumbing, never legal-quality claims.

Run: PYTHONPATH=. python scripts/compare_legal_skills.py --output /tmp/comparison.json
Live mode is opt-in, loopback-only, and requires a confirmed nonproduction dataset.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = ('workflow_selection','issue_identification','analysis_completeness','factual_consistency',
          'citation_integrity','jurisdiction_treatment','missing_information','proposed_clause_quality',
          'human_review_requirements','output_consistency')


def private_write(path: Path, value):
    # Refuse accidental overwrite of a previous run or user artifact.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd,'w') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.write('\n')


def local_base(value):
    parsed=urlparse(value)
    if (parsed.scheme not in ('http','https') or parsed.hostname not in ('localhost','127.0.0.1','::1')
        or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/')):
        raise ValueError('Live acceptance URLs must be loopback origins without credentials or paths')
    return value.rstrip('/')


def fetch(base,path,body=None):
    token=os.environ.get('API_TOKEN','').strip()
    if not token:
        raise ValueError('Configure API_TOKEN securely; no token is accepted on the command line')
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
    req=Request(base+path,data=None if body is None else json.dumps(body,ensure_ascii=False).encode(),headers=headers)
    # Do not follow redirects with the bearer token to another origin.
    from urllib.request import HTTPRedirectHandler, build_opener
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs): return None
    with build_opener(NoRedirect()).open(req,timeout=300) as response:
        return response.headers, response.read().decode()


def run_live(args):
    if os.environ.get('LEGAL_ACCEPTANCE_NONPRODUCTION') != 'true':
        raise ValueError('Confirm a fictional, nonproduction, read-only knowledge base using LEGAL_ACCEPTANCE_NONPRODUCTION=true')
    original, skilled=local_base(args.original_url),local_base(args.skilled_url)
    if original==skilled:
        raise ValueError('Use separately configured flag-off and flag-on servers')
    for base,wanted in ((original,False),(skilled,True)):
        _,text=fetch(base,'/skills')
        if json.loads(text)['enabled'] != wanted:
            raise ValueError('Server feature flags do not match comparison modes')
    scenarios=json.loads((ROOT/'tests/acceptance/scenarios.json').read_text())
    scenario=next(item for item in scenarios if item['id']==args.scenario)
    variant=scenario['variants'][args.language]
    body={'prompt':variant['prompt']+'\n\n'+variant['document'],
          'doc_type':scenario['document_type'],'skill_jurisdiction':scenario['jurisdiction']}
    if scenario.get('risk_inputs'): body['skill_risk']=scenario['risk_inputs'][0]
    outcomes={}
    for mode,base in (('original',original),('skilled',skilled)):
        headers,text=fetch(base,'/generate',body)
        frames=[json.loads(line[6:]) for line in text.splitlines() if line.startswith('data: ')]
        by_type={frame['type']:frame for frame in frames}
        if 'error' in by_type or 'done' not in by_type:
            raise RuntimeError('Generation failed; no comparison-quality claim can be made')
        citations=by_type.get('citations',{}).get('report',{})
        outcomes[mode]={'selected_skill':headers.get('X-Legal-Skill'),
                        'output':by_type['done']['document'],
                        'diagnostics':by_type['done'].get('skill_diagnostics'),
                        'verification_frames':{key:by_type.get(key) for key in ('citations','authority','review','revision','facts')},
                        'deterministic_counts':{key:len(citations.get(key,[])) for key in ('verified','rejected','unbacked_articles')}}
    return {'mode':'live_paired','scenario':scenario['id'],'language':args.language,
            'current_law_verified':False, 'results':outcomes,
            'lawyer_scorecard':{dimension:{'original_score':None,'skilled_score':None,'evidence':None,'status':'NOT RUN'} for dimension in RUBRIC},
            'human_approval':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--original-url',default='http://127.0.0.1:18001')
    parser.add_argument('--skilled-url',default='http://127.0.0.1:18002')
    parser.add_argument('--scenario',choices=[f'{n:02}' for n in range(1,11)],default='01')
    parser.add_argument('--language',choices=['ar','en'],default='en')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Output already exists; choose a new run filename')
    if args.live:
        result=run_live(args)
    else:
        from tests.acceptance.harness import offline_comparison
        result=offline_comparison()
    private_write(args.output,result)
    print('Saved acceptance report; subjective legal quality requires lawyer review.')


if __name__=='__main__': main()
