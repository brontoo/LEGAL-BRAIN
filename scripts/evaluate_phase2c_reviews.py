"""Explicit local comparison of supplied human reviews; no outbound communication."""
import argparse
import hashlib
import json
from pathlib import Path
from clause_intelligence import Document
from clause_intelligence.parser import parse
from benchmarks.roles.lawyer_review import evaluate_reviews


def evaluate(first_path=None, second_path=None):
    raw = Path('benchmarks/roles/corpus.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    cases = {}
    for item in json.loads(raw)['documents']:
        case_id = 'REVIEW-'+hashlib.sha256((digest+item['document_id']).encode()).hexdigest()[:10]
        document = Document(item['document_id'], item['text'], item['version'])
        cases[case_id] = (document, parse(document))
    first = json.loads(Path(first_path).read_text()) if first_path else None
    second = json.loads(Path(second_path).read_text()) if second_path else None
    return evaluate_reviews(first, second, corpus_sha256=digest, cases=cases)


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--first')
    cli.add_argument('--second')
    cli.add_argument('--output', required=True)
    args = cli.parse_args()
    result = evaluate(args.first, args.second)
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(result['status'])
