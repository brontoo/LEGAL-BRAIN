"""Local coordinator commands. No public API/portal or outbound communication."""
import argparse
import json
from . import private,secure_review,datasets


def main():
    cli=argparse.ArgumentParser();cli.add_argument('operation',choices=('prepare','assign','submit','status','confirm-origin','adjudicate','unblind'))
    cli.add_argument('--reviewer-dir');cli.add_argument('--coordinator-dir',required=True)
    cli.add_argument('--sources');cli.add_argument('--record');cli.add_argument('--reviewer-1');cli.add_argument('--reviewer-2')
    cli.add_argument('--engineering-test-only',action='store_true');cli.add_argument('--confirm-finalized',action='store_true')
    cli.add_argument('--confirm-approved-sanitized',action='store_true')
    a=cli.parse_args()
    if a.operation=='prepare':
        if a.engineering_test_only:
            raw=private.read(private.REPO/'benchmarks/roles/corpus.json')['documents']
            docs=[{k:d[k] for k in ('document_id','version','text','language')} for d in raw]
        else:
            if not a.confirm_approved_sanitized:cli.error('Explicit approved/sanitized source confirmation is required')
            if not a.sources:cli.error('Approved external source package required')
            value=datasets.validate(private.read(a.sources))
            if datasets.overlap(value)['exact_provision_matches']:cli.error('Known development material is unsuitable for a fresh blinded study')
            docs=[{**d,'provenance':{'approved_for_review':True}} for d in value['documents']]
        result=secure_review.prepare(docs,reviewer_dir=a.reviewer_dir,coordinator_dir=a.coordinator_dir,test_only=a.engineering_test_only)
    elif a.operation=='assign':result=secure_review.assign(a.coordinator_dir,[a.reviewer_1,a.reviewer_2])
    elif a.operation=='submit':result=secure_review.submit(a.coordinator_dir,private.read(a.record))
    elif a.operation=='confirm-origin':result=secure_review.confirm_origin(a.coordinator_dir,private.read(a.record))
    elif a.operation=='adjudicate':result=secure_review.adjudicate(a.coordinator_dir,private.read(a.record))
    elif a.operation=='unblind':
        secure_review.unblind(a.coordinator_dir,finalized_confirmation=a.confirm_finalized)
        result={'state':'CONTROLLED_UNBLINDING_RECORDED','assignment_key_output':'private destination only'}
    else:result=secure_review.status(a.coordinator_dir)
    print(json.dumps({k:v for k,v in result.items() if k in ('state','cases','test_only','human_review','legal_approval')}))


if __name__=='__main__':
    try:main()
    except (ValueError,TypeError,KeyError,OSError):raise SystemExit('INVALID_REVIEW — no private details logged') from None
