from pathlib import Path
import copy
import json
import random
import tempfile
import unittest
from validation import private,secure_review as review


class SecureReview(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='legal-review-unit-test-')
        self.base=Path(self.temp.name);self.public=self.base/'public';self.secret=self.base/'private'
        self.docs=[{'document_id':'fictional-test','text':'1 Buyer shall pay Seller.','version':'v1','language':'en'}]

    def tearDown(self):self.temp.cleanup()

    def prepare(self,**kw):
        return review.prepare(self.docs,reviewer_dir=self.public,coordinator_dir=self.secret,test_only=True,**kw)

    def record(self,reviewer,*,full=True,finalized=True,label='unknown'):
        packet=private.read(self.secret/'study.json')['packet'];case=packet['cases'][0];unit=case['provisions'][0]
        fields=review.FIELDS if full else ('actor',)
        annotations=[]
        for field in fields:
            value='needs_review' if field=='approval' else label
            annotations.append({'case_id':case['case_id'],'unit_id':unit['unit_id'],'field':field,'label':value,
                                'evidence':[unit['evidence']] if value not in review.EMPTY and field in review.DOCUMENTARY else []})
        return {'study_id':packet['study_id'],'packet_sha256':private.digest(packet),'reviewer_id':reviewer,
                'origin':'fictional_unit_test','qualification_attested':True,'independence_attested':True,
                'source_first_attested':True,'finalized':finalized,'annotations':annotations}

    def test_retired_packet_old_identifiers_rejected_and_generator_disabled(self):
        retirement=private.read(private.REPO/'benchmarks/roles/review-packet/RETIREMENT.json')
        self.assertEqual('RETIRED_FOR_BLINDED_REVIEW',retirement['status'])
        self.assertTrue(review.retired(retirement['retired_case_ids'][0]))
        from benchmarks.roles.review_packet import prepare
        with self.assertRaises(ValueError):prepare(self.public)

    def test_repository_and_nested_git_destinations_rejected(self):
        with self.assertRaises(ValueError):review.prepare(self.docs,reviewer_dir=private.REPO/'private-study',coordinator_dir=self.secret,test_only=True)
        nested=self.base/'other-checkout';nested.mkdir();(nested/'.git').mkdir()
        with self.assertRaises(ValueError):private.directory(nested/'keys')

    def test_symlink_destinations_and_overlap_rejected(self):
        alias=self.base/'alias';alias.symlink_to(self.base,target_is_directory=True)
        with self.assertRaises(ValueError):private.directory(alias/'unsafe')
        with self.assertRaises(ValueError):review.prepare(self.docs,reviewer_dir=self.public,coordinator_dir=self.public/'keys',test_only=True)

    def test_crypto_fresh_cases_and_no_key_or_engine_labels_in_visible_packet(self):
        first=self.prepare()
        packet=private.read(self.public/'reviewer-1/candidates.json')
        raw=json.dumps(packet)
        self.assertNotIn('role_v2',raw);self.assertNotIn('legacy',raw);self.assertNotIn('assignments',raw)
        self.assertFalse(any(self.public.rglob('blinding-map.json')))
        self.assertTrue(packet['cases'][0]['case_id'].startswith('CASE-'))
        other=review.prepare(self.docs,reviewer_dir=self.base/'pub2',coordinator_dir=self.base/'sec2',test_only=True)
        self.assertNotEqual(first['study_id'],other['study_id'])

    def test_owner_only_permissions_and_separate_reviewer_outputs(self):
        self.prepare()
        self.assertEqual(0,self.secret.stat().st_mode&0o077)
        self.assertEqual(0,(self.secret/'blinding-map.json').stat().st_mode&0o077)
        self.assertTrue((self.public/'reviewer-1/source-first.json').exists())
        self.assertTrue((self.public/'reviewer-2/source-first.json').exists())

    def test_determinism_only_explicit_test_interface(self):
        with self.assertRaises(ValueError):review.prepare(self.docs,reviewer_dir=self.public,coordinator_dir=self.secret,testing_rng=random.Random(4))
        result=self.prepare(testing_rng=random.Random(4))
        self.assertTrue(result['test_only']);self.assertEqual('NOT_RUN',result['human_review'])

    def test_no_overwrite_or_automatic_real_qualification(self):
        self.prepare()
        with self.assertRaises(FileExistsError):self.prepare()
        with self.assertRaises(ValueError):review.prepare(self.docs,reviewer_dir=self.base/'r',coordinator_dir=self.base/'s')
        self.assertEqual('NOT_RUN',review.status(self.secret)['human_review'])

    def test_independent_states_and_finalized_immutability(self):
        self.prepare();review.assign(self.secret,['FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'])
        self.assertEqual('ASSIGNED',review.status(self.secret)['state'])
        review.submit(self.secret,self.record('FICTIONAL-UNIT-1',full=False,finalized=False))
        self.assertEqual('PARTIALLY_REVIEWED',review.status(self.secret)['state'])
        review.submit(self.secret,self.record('FICTIONAL-UNIT-1'))
        with self.assertRaises(ValueError):review.submit(self.secret,self.record('FICTIONAL-UNIT-1'))
        review.submit(self.secret,self.record('FICTIONAL-UNIT-2'))
        state=review.status(self.secret)
        self.assertEqual('INDEPENDENT_REVIEWS_COMPLETE',state['state']);self.assertEqual('NOT_RUN',state['human_review'])
        self.assertEqual({},state['agreement_by_field'])
        self.assertEqual(3,len(list(self.secret.glob('reviewer-*-submission-*.json'))))

    def test_invalid_attestations_sources_and_premature_finalization(self):
        self.prepare();review.assign(self.secret,['FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'])
        for changes in ({'independence_attested':False},{'origin':'human_supplied'},{'packet_sha256':'bad'}):
            with self.assertRaises(ValueError):review.submit(self.secret,{**self.record('FICTIONAL-UNIT-1'),**changes})
        with self.assertRaises(ValueError):review.submit(self.secret,self.record('FICTIONAL-UNIT-1',full=False))

    def test_wrong_version_evidence_and_unknown_case_rejected(self):
        self.prepare();review.assign(self.secret,['FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'])
        record=self.record('FICTIONAL-UNIT-1',label='supported_by_definition')
        record['annotations'][0]['evidence'][0]['version']='wrong'
        with self.assertRaises(ValueError):review.submit(self.secret,record)
        record=self.record('FICTIONAL-UNIT-1');record['annotations'][0]['case_id']='REVIEW-compromised'
        with self.assertRaises(ValueError):review.submit(self.secret,record)

    def test_controlled_unblinding_only_after_completion_with_audit(self):
        self.prepare()
        with self.assertRaises(ValueError):review.unblind(self.secret,finalized_confirmation=True)
        review.assign(self.secret,['FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'])
        for identity in ('FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'):review.submit(self.secret,self.record(identity))
        with self.assertRaises(ValueError):review.unblind(self.secret)
        key=review.unblind(self.secret,finalized_confirmation=True)
        self.assertTrue(key['assignments']);self.assertTrue((self.secret/'unblinding-audit.json').exists())

    def test_disagreement_adjudication_keeps_originals_and_rejects_same_adjudicator(self):
        self.prepare();ids=['FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'];review.assign(self.secret,ids)
        first=self.record(ids[0]);second=self.record(ids[1]);second['annotations'][0]['label']='not_present'
        review.submit(self.secret,first);review.submit(self.secret,second)
        before=[private.digest(private.read(p)) for p in sorted(self.secret.glob('reviewer-*-submission-*.json'))]
        state=review.status(self.secret);self.assertEqual('ADJUDICATION_PENDING',state['state'])
        packet=private.read(self.secret/'study.json')['packet'];unit=packet['cases'][0]['provisions'][0]
        d=state['disagreements'][0]
        decision={'adjudicator_id':ids[0],'origin':'fictional_unit_test','decisions':[{'case_id':d['case_id'],'unit_id':d['unit_id'],'field':d['field'],
                   'label':'unknown','reason':'Fictional test reason; no actual professional decision.', 'evidence':[unit['evidence']]}]}
        with self.assertRaises(ValueError):review.adjudicate(self.secret,decision)
        decision['adjudicator_id']='FICTIONAL-UNIT-3'
        self.assertEqual('ADJUDICATED',review.adjudicate(self.secret,decision)['state'])
        self.assertEqual(before,[private.digest(private.read(p)) for p in sorted(self.secret.glob('reviewer-*-submission-*.json'))])

    def test_json_data_alone_does_not_confirm_real_review_origin(self):
        self.prepare();root=private.read(self.secret/'study.json');root['packet']['test_only']=False
        # Explicit fictional test of the state machine, never a real reviewer record.
        packet=root['packet'];private_path=self.secret/'study.json';private_path.write_text(json.dumps(root))
        ids=['FICTIONAL-UNIT-1','FICTIONAL-UNIT-2'];review.assign(self.secret,ids)
        for identity in ids:
            record=self.record(identity);record['origin']='human_supplied';review.submit(self.secret,record)
        self.assertEqual('PARTIALLY_REVIEWED',review.status(self.secret)['state'])
