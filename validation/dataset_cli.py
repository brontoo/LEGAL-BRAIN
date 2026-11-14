"""Explicit offline ingestion/evaluation. Defaults to honest independent-data NOT RUN."""
import argparse
from . import datasets,private


def main():
    cli=argparse.ArgumentParser();cli.add_argument('operation',choices=('freeze','evaluate'));cli.add_argument('--source');cli.add_argument('--destination');cli.add_argument('--frozen');cli.add_argument('--output')
    a=cli.parse_args()
    if a.operation=='freeze':
        if not a.source or not a.destination:cli.error('--source and --destination required')
        result=datasets.freeze(a.source,a.destination)
    else:
        if not a.output:cli.error('Explicit private --output required')
        result=datasets.evaluate(a.frozen);private.write(a.output,result)
    print(result.get('status','FROZEN_OFFLINE_LABELS'))


if __name__=='__main__':
    try:main()
    except (ValueError,TypeError,KeyError,OSError):raise SystemExit('FAILED_EVALUATION_INPUT — no private details logged') from None
