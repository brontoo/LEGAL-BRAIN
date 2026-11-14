"""Private, randomized study packets and append-only supplied-review workflow.

No reviewer identity/qualification/independence is invented or independently
verified by software. Tests are explicitly marked and cannot grant human approval.
"""
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import secrets
from unittest.mock import patch
from clause_intelligence import AnalysisRequest, Document, analyze
from clause_intelligence.parser import parse
from clause_intelligence.evidence import from_payload
from benchmarks.roles.runner import projection
from benchmarks.roles.lawyer_review import REVIEW_FIELDS, agreement_math
from . import private

FIELDS = (*REVIEW_FIELDS, 'missing_evidence', 'explanation')
EMPTY = ('unknown', 'not_present', 'ambiguous', 'unsupported')
DOCUMENTARY = ('actor', 'action', 'object', 'beneficiary', 'conditions', 'exceptions', 'trigger', 'deadline', 'interpretation_support')


def retired(case_id):
    manifest = private.read(private.REPO/'benchmarks/roles/review-packet/RETIREMENT.json')
    return case_id in manifest['retired_case_ids'] or case_id.startswith('REVIEW-')


def prepare(documents, *, reviewer_dir=None, coordinator_dir=None, test_only=False, testing_rng=None):
    if testing_rng is not None and not test_only:
        raise ValueError('Deterministic randomness is available only for explicit tests')
    if not documents or len(documents) > 100:
        raise ValueError('Provide bounded approved source documents')
    if sum(len(d.get('text','')) for d in documents)>500000:
        raise ValueError('Review study exceeds total source-text bound')
    if not test_only and any(d.get('provenance', {}).get('approved_for_review') is not True for d in documents):
        raise ValueError('Explicit approved-source provenance is required')
    rand = testing_rng
    token = lambda: f'{rand.getrandbits(128):032x}' if rand else secrets.token_hex(16)
    choose = lambda: rand.randrange(2) if rand else secrets.randbelow(2)
    base = Path.home()/'.local/share/legal-brain-private'
    reviewer_dir = private.outside_repository(reviewer_dir or base/('review-packets-private-'+token()))
    coordinator_dir = private.outside_repository(coordinator_dir or base/('legal-review-private-'+token()))
    if reviewer_dir.is_relative_to(coordinator_dir) or coordinator_dir.is_relative_to(reviewer_dir):
        raise ValueError('Coordinator and reviewer destinations must be disjoint')
    if reviewer_dir.exists() or coordinator_dir.exists():
        raise FileExistsError('Refusing to overwrite a study destination')
    public, key = [], []
    used = set()
    for source in documents:
        case_id = 'CASE-'+token()
        if case_id in used or retired(case_id):
            raise ValueError('Case identifiers must be fresh and unique')
        used.add(case_id)
        doc = Document(case_id, source['text'], source.get('version', 'v1'))
        models = ('legacy', 'role_v2') if choose() else ('role_v2', 'legacy')
        case = {'case_id': case_id, 'source': {'document_id': case_id, 'version': doc.version,
                'content_sha256': doc.digest, 'text': doc.text}, 'provisions': [], 'candidates': {}}
        clauses = parse(doc)
        for clause in clauses:
            if clause.structure != 'title':
                case['provisions'].append({'unit_id': clause.clause_id, 'evidence': asdict(clause.span)})
        for label, mode in zip(('A', 'B'), models):
            with patch.dict(os.environ, {'ENABLE_CLAUSE_ROLE_V2': str(mode == 'role_v2').lower(),
                        'ENABLE_CLAUSE_MODEL_ASSISTANCE': 'false', 'ENABLE_LEGAL_SKILLS': 'false',
                        'ENABLE_HYBRID_LEGAL_RETRIEVAL': 'false'}):
                report = analyze(AnalysisRequest(doc, language=source.get('language', 'en')))
            case['candidates'][label] = [{'unit_id': o['source_clause'], 'candidate_id': o['obligation_id'],
                                         'roles': projection(report, o, mode == 'role_v2'), 'evidence': o['evidence']}
                                        for o in report['obligations']]
        public.append(case)
        if sum(len(str(c)) for c in public)>16*1024*1024:
            raise ValueError('Review study exceeds artifact bound')
        key.append({'case_id': case_id, 'source_id': source.get('document_id'), 'A': models[0], 'B': models[1]})
    study_id = 'STUDY-'+token()
    packet = {'study_id': study_id, 'state': 'PREPARED', 'test_only': test_only, 'cases': public,
              'human_review': 'NOT_RUN', 'legal_approval': 'not_provided'}
    commitment = private.digest(packet)
    private.directory(reviewer_dir)
    private.directory(coordinator_dir)
    private.write(coordinator_dir/'blinding-map.json', {'study_id': study_id, 'packet_sha256': commitment, 'assignments': key})
    private.write(coordinator_dir/'study.json', {'packet': packet, 'assignments': [], 'submissions': [], 'adjudications': []})
    for number in (1, 2):
        destination = reviewer_dir/f'reviewer-{number}'
        destination.mkdir(mode=0o700)
        # Source-first material is distributed BEFORE candidates by the coordinator.
        sources = [{k: v for k, v in case.items() if k != 'candidates'} for case in public]
        private.write(destination/'source-first.json', {'study_id': study_id, 'cases': sources})
        private.write(destination/'candidates.json', packet)
        private.write(destination/'empty-submission.json', {'study_id': study_id, 'packet_sha256': commitment,
                      'reviewer_id': None, 'origin': None, 'qualification_attested': False,
                      'independence_attested': False, 'source_first_attested': False, 'finalized': False,
                      'annotations': [], 'human_review': 'NOT_RUN'})
    return {'state': 'PREPARED', 'cases': len(public), 'study_id': study_id, 'packet_sha256': commitment,
            'test_only': test_only, 'human_review': 'NOT_RUN', 'legal_approval': 'not_provided'}


def assign(coordinator, reviewer_ids):
    root = private.outside_repository(coordinator)
    study = private.read(root/'study.json')
    if len(reviewer_ids) != 2 or len(set(reviewer_ids)) != 2 or any(not isinstance(v, str) or not 1 <= len(v) <= 80 for v in reviewer_ids):
        raise ValueError('Two distinct externally supplied reviewer identifiers are required')
    record = {'reviewer_ids': list(reviewer_ids), 'state': 'ASSIGNED', 'qualification_check': 'external_responsibility'}
    private.write(root/'assignment.json', record)
    return record


def validate_submission(packet, record, assigned):
    if record.get('study_id') != packet['study_id'] or record.get('packet_sha256') != private.digest(packet):
        raise ValueError('Retired or mismatched study/packet')
    if record.get('reviewer_id') not in assigned:
        raise ValueError('Unassigned reviewer')
    if any(record.get(key) is not True for key in ('qualification_attested', 'independence_attested', 'source_first_attested')):
        raise ValueError('Supplied independent source-first qualification attestations required')
    expected_origin = 'fictional_unit_test' if packet['test_only'] else 'human_supplied'
    if record.get('origin') != expected_origin:
        raise ValueError('Synthetic records cannot advance real human-review state')
    cases = {c['case_id']: c for c in packet['cases']}
    annotations = record.get('annotations')
    if not isinstance(annotations, list) or not annotations or len(annotations) > 100000:
        raise ValueError('Bounded supplied annotations required')
    units = {}
    for item in annotations:
        if not isinstance(item, dict) or set(item)-{'case_id','unit_id','field','label','evidence','notes','status'}:
            raise ValueError('Invalid annotation fields')
        case_id, unit, field = item.get('case_id'), item.get('unit_id'), item.get('field')
        if not isinstance(case_id,str) or retired(case_id) or case_id not in cases or field not in FIELDS:
            raise ValueError('Unknown or retired case/field')
        case = cases[case_id]
        if unit not in [p['unit_id'] for p in case['provisions']]:
            raise ValueError('Unknown source provision')
        label = item.get('label')
        if not isinstance(label, str) or not 1 <= len(label) <= 1200:
            raise ValueError('Bounded reviewer label required')
        key = (case_id, unit, field)
        if key in units:
            raise ValueError('Duplicate annotation')
        source = case['source']
        document = Document(source['document_id'], source['text'], source['version'])
        evidence = item.get('evidence', [])
        if not isinstance(evidence, list) or len(evidence) > 6:
            raise ValueError('Invalid evidence list')
        for span in evidence:
            checked = from_payload(document, parse(document), span)
            if checked.clause_id != unit:
                raise ValueError('Evidence must belong to the reviewed provision')
        if field in DOCUMENTARY and label not in EMPTY and not evidence:
            raise ValueError('Supported documentary labels require exact evidence')
        if field == 'approval' and label not in ('analysis_accepted','analysis_rejected','needs_review'):
            raise ValueError('Approval applies to extraction analysis only')
        units[key] = item
    required = {(c['case_id'], p['unit_id'], field) for c in packet['cases'] for p in c['provisions'] for field in FIELDS}
    complete=required <= units.keys()
    if record.get('finalized') is True and not complete:raise ValueError('Incomplete reviews cannot be finalized')
    return units, complete


def submit(coordinator, record):
    root = private.outside_repository(coordinator)
    study = private.read(root/'study.json')
    assigned = private.read(root/'assignment.json')['reviewer_ids']
    units, complete = validate_submission(study['packet'], record, assigned)
    slot = assigned.index(record['reviewer_id'])+1
    previous=sorted(root.glob(f'reviewer-{slot}-submission-*.json'))
    if previous and private.read(previous[-1]).get('finalized') is True:
        raise ValueError('Finalized independent submissions are immutable')
    if (root/'adjudication.json').exists() or (root/'unblinding-audit.json').exists():
        raise ValueError('Reviews are locked after adjudication or unblinding')
    # Exclusive immutable original; a partial submission cannot silently become final.
    revision=len(list(root.glob(f'reviewer-{slot}-submission-*.json')))+1
    private.write(root/f'reviewer-{slot}-submission-{revision:04d}.json', record)
    return {**status(root), 'accepted_fields':len(units), 'complete':complete}


def status(coordinator):
    root = private.outside_repository(coordinator)
    packet = private.read(root/'study.json')['packet']
    result = {'state':'PREPARED','human_review':'NOT_RUN','legal_approval':'not_provided', 'agreement_by_field':{}, 'disagreements':[]}
    if not (root/'assignment.json').exists():
        return result
    ids = private.read(root/'assignment.json')['reviewer_ids']
    result['state'] = 'ASSIGNED'
    reviews = []
    try:
        for slot in (1,2):
            paths=sorted(root.glob(f'reviewer-{slot}-submission-*.json'))
            if paths:
                path=paths[-1]
                record = private.read(path)
                units, complete = validate_submission(packet,record,ids)
                if record['reviewer_id'] != ids[slot-1]:
                    raise ValueError('Reviewer slot mismatch')
                verified=packet['test_only']
                proof=root/f'origin-confirmation-{private.digest(record)}.json'
                if proof.exists():
                    confirmation=private.read(proof)
                    verified=bool(confirmation.get('actual_independent_submission_confirmed') is True
                                  and confirmation.get('submission_sha256')==private.digest(record)
                                  and confirmation.get('reviewer_id')==record['reviewer_id'])
                reviews.append((units,complete and record.get('finalized') is True and verified))
    except (ValueError,TypeError,KeyError):
        result['state']='INVALID_REVIEW'
        return result
    if reviews:
        result['state']='PARTIALLY_REVIEWED'
    if len(reviews)!=2 or not all(complete for _,complete in reviews):
        return result
    result['state']='INDEPENDENT_REVIEWS_COMPLETE'
    a,b=reviews[0][0],reviews[1][0]
    common=sorted(a.keys() & b.keys())
    result['coverage']={'common_fields':len(common),'union_fields':len(a.keys() | b.keys())}
    for field in FIELDS:
        keys=[k for k in common if k[2]==field]
        if keys and not packet['test_only']:
            result['agreement_by_field'][field]=agreement_math([a[k]['label'] for k in keys],[b[k]['label'] for k in keys])
    disagreements=[{'case_id':k[0],'unit_id':k[1],'field':k[2],'first':a[k]['label'],'second':b[k]['label']} for k in common if a[k]['label']!=b[k]['label']]
    result['disagreements']=disagreements
    if disagreements:
        result['state']='ADJUDICATION_PENDING'
        if (root/'adjudication.json').exists():
            decisions=private.read(root/'adjudication.json')
            try:
                validate_adjudication(packet,ids,disagreements,decisions)
                result['state']='ADJUDICATED'
            except (ValueError,KeyError,TypeError):result['state']='INVALID_REVIEW'
    result['human_review']='NOT_RUN' if packet['test_only'] else 'coordinator_confirmed_supplied_records_not_legal_approval'
    return result


def confirm_origin(coordinator,record):
    root=private.outside_repository(coordinator)
    if not isinstance(record,dict) or set(record)!={'reviewer_id','submission_sha256','verified_by','external_reference','actual_independent_submission_confirmed'}:
        raise ValueError('Explicit external coordinator verification record required')
    if record['actual_independent_submission_confirmed'] is not True or any(not isinstance(record[k],str) or not 1<=len(record[k])<=300 for k in ('verified_by','external_reference')):
        raise ValueError('External origin confirmation cannot be inferred from JSON annotations')
    submissions=[private.read(p) for p in root.glob('reviewer-*-submission-*.json')]
    if not any(private.digest(s)==record['submission_sha256'] and s['reviewer_id']==record['reviewer_id'] for s in submissions):
        raise ValueError('Origin confirmation does not match an immutable supplied submission')
    private.write(root/f"origin-confirmation-{record['submission_sha256']}.json",record)
    return status(root)


def validate_adjudication(packet, reviewer_ids, disagreements, record):
    if record.get('adjudicator_id') in reviewer_ids or not isinstance(record.get('adjudicator_id'),str) or not record['adjudicator_id'].strip():
        raise ValueError('Distinct supplied adjudicator required')
    if record.get('origin') != ('fictional_unit_test' if packet['test_only'] else 'human_supplied'):
        raise ValueError('Adjudicator origin mismatch')
    expected={(d['case_id'],d['unit_id'],d['field']) for d in disagreements}
    decisions=record.get('decisions',[])
    if not isinstance(decisions,list) or len(decisions)!=len(expected):
        raise ValueError('Each disagreement requires one reasoned decision')
    seen=set()
    for d in decisions:
        key=(d.get('case_id'),d.get('unit_id'),d.get('field'))
        if key not in expected or key in seen or not isinstance(d.get('reason'),str) or not 20<=len(d['reason'])<=2000:
            raise ValueError('Incomplete, duplicate or unreasoned adjudication')
        case=next(c for c in packet['cases'] if c['case_id']==key[0]); source=case['source']
        doc=Document(source['document_id'],source['text'],source['version'])
        if not isinstance(d.get('label'),str) or not 1<=len(d['label'])<=1200 or not d.get('evidence'):
            raise ValueError('Adjudication label and evidence required')
        for span in d['evidence']:
            if from_payload(doc,parse(doc),span).clause_id!=key[1]:
                raise ValueError('Wrong adjudication provision')
        seen.add(key)


def adjudicate(coordinator, record):
    root=private.outside_repository(coordinator)
    current=status(root)
    if current['state']!='ADJUDICATION_PENDING':
        raise ValueError('Finalize independent reviews before adjudication')
    packet=private.read(root/'study.json')['packet']; ids=private.read(root/'assignment.json')['reviewer_ids']
    validate_adjudication(packet,ids,current['disagreements'],record)
    private.write(root/'adjudication.json',record)
    return status(root)


def unblind(coordinator, *, finalized_confirmation=False):
    root=private.outside_repository(coordinator)
    current=status(root)
    if not finalized_confirmation or current['state'] not in ('INDEPENDENT_REVIEWS_COMPLETE','ADJUDICATED'):
        raise ValueError('Controlled unblinding requires complete reviews and explicit coordinator confirmation')
    key=private.read(root/'blinding-map.json')
    if key['packet_sha256']!=private.digest(private.read(root/'study.json')['packet']):
        raise ValueError('Assignment key and packet commitment mismatch')
    private.write(root/'unblinding-audit.json',{'packet_sha256':key['packet_sha256'],'review_state':current['state'],
                  'submission_hashes':[private.digest(private.read(sorted(root.glob(f'reviewer-{i}-submission-*.json'))[-1])) for i in (1,2)]})
    return key
