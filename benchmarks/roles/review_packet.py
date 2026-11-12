"""Create an explicit local blinded A/B packet with EMPTY lawyer forms."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
from unittest.mock import patch
from clause_intelligence import AnalysisRequest, analyze
from .runner import projection
from .lawyer_review import evaluate_reviews, REVIEW_FIELDS


def prepare(output):
    root = Path(output)
    root.mkdir(parents=False, exist_ok=False)
    raw = Path(__file__).with_name('corpus.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    documents = json.loads(raw)['documents']
    packet, private = [], []
    rng = random.Random(20261112)
    for index, doc in enumerate(documents):
        case_id = 'REVIEW-'+hashlib.sha256((digest+doc['document_id']).encode()).hexdigest()[:10]
        models = ['legacy', 'role_v2']
        rng.shuffle(models)
        case = {'case_id': case_id, 'language': doc['language'], 'source_document': doc['text'],
                'source_document_id': doc['document_id'], 'source_version': doc['version'],
                'source_sha256': hashlib.sha256(doc['text'].encode()).hexdigest(), 'candidates': {},
                'provisions': [{'unit_prefix': f'P-{i+1:04d}', 'start': p['start'], 'end': p['end'], 'text': p['text']}
                               for i, p in enumerate(doc['provisions'])]}
        for letter, mode in zip(('A', 'B'), models):
            with patch.dict(os.environ, {'ENABLE_CLAUSE_ROLE_V2': str(mode == 'role_v2').lower(),
                                        'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false', 'ENABLE_LEGAL_SKILLS': 'false',
                                        'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'false'}):
                report = analyze(AnalysisRequest.from_payload({'document_id': doc['document_id'], 'document_version': doc['version'],
                                'document_text': doc['text'], 'language': doc['language']}))
            units, candidates = {}, []
            for obligation in report['obligations']:
                clause = next(c for c in report['clauses'] if c['clause_id'] == obligation['source_clause'])
                provision = next(p for p in case['provisions'] if p['start'] == clause['span']['start'] and p['end'] == clause['span']['end'])
                prefix = provision['unit_prefix']
                units[prefix] = units.get(prefix, 0)+1
                candidates.append({'unit_id': prefix+':'+str(units[prefix]),
                                   'roles': projection(report, obligation, mode == 'role_v2'),
                                   'evidence': obligation['evidence'], 'legal_approval': 'not_provided'})
            case['candidates'][letter] = candidates
        packet.append(case)
        private.append({'case_id': case_id, 'source_id': doc['document_id'], 'A': models[0], 'B': models[1]})
    def write(name, value):
        with (root/name).open('x') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    write('packet.json', {'corpus_sha256': digest, 'status': 'PREPARED_NOT_REVIEWED', 'cases': packet})
    (root/'coordinator-only').mkdir()
    write('coordinator-only/blinding-map.json', private)
    template = {'corpus_sha256': digest, 'reviewer_id': None, 'origin': None,
                'qualification_attested': False, 'independence_attested': False,
                'annotation_fields': REVIEW_FIELDS, 'annotations': [], 'status': 'NOT_RUN'}
    write('reviewer-1-empty.json', template)
    write('reviewer-2-empty.json', template)
    write('review-status.json', evaluate_reviews(corpus_sha256=digest))
    return {'status': 'PREPARED_NOT_REVIEWED', 'cases': len(packet), 'lawyer_evaluation': 'NOT_RUN'}


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--output-dir', required=True)
    print(json.dumps(prepare(cli.parse_args().output_dir)))
