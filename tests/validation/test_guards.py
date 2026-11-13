import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch,Mock
from validation import datasets,private,preflight,live
from validation.provider_bounds import bounded_model
from validation.readiness import assess
from clause_intelligence import Document
from benchmarks.roles.metrics import FIELDS


class ExternalCorpus(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='external-unit-fixture-');self.root=Path(self.temp.name)
        doc=Document('external-fictional','1 Buyer shall pay Seller.','v1')
        self.value={'version':'test-v1','source_provenance':{'origin':'fictional_unit_test','reference':'unit fixture','independent_attested':False},
                    'annotation_provenance':{'origin':'fictional_unit_test','reference':'manually authored unit fixture','independent_attested':False},
                    'documents':[{'document_id':doc.document_id,'version':doc.version,'text':doc.text,'sha256':doc.digest,'language':'en',
                    'provisions':[{'start':0,'end':len(doc.text),'quote':doc.text,'roles':[{f:False if f=='conditional' else None for f in FIELDS}]}]}]}
    def tearDown(self):self.temp.cleanup()

    def freeze(self):
        source=self.root/'source.json';source.write_text(json.dumps(self.value));return datasets.freeze(source,self.root/'frozen')

    def test_missing_real_external_data_not_run(self):
        self.assertEqual(datasets.NOT_RUN,datasets.evaluate()['status'])

    def test_freeze_provenance_hash_no_overwrite_and_gold_not_changed(self):
        self.freeze();before=(self.root/'frozen/corpus.json').read_bytes()
        result=datasets.evaluate(self.root/'frozen')
        self.assertEqual('NOT_INDEPENDENTLY_ATTESTED',result['independence'])
        self.assertEqual(before,(self.root/'frozen/corpus.json').read_bytes())
        with self.assertRaises(FileExistsError):datasets.freeze(self.root/'source.json',self.root/'frozen')

    def test_wrong_hash_duplicate_id_and_missing_provenance_rejected(self):
        value=copy.deepcopy(self.value);value['documents'][0]['sha256']='bad'
        with self.assertRaises(ValueError):datasets.validate(value)
        value=copy.deepcopy(self.value);value['documents']*=2
        with self.assertRaises(ValueError):datasets.validate(value)
        value=copy.deepcopy(self.value);del value['annotation_provenance']
        with self.assertRaises(ValueError):datasets.validate(value)

    def test_source_offset_and_frozen_label_manipulation_rejected(self):
        value=copy.deepcopy(self.value);value['documents'][0]['provisions'][0]['quote']='invented'
        with self.assertRaises(ValueError):datasets.validate(value)
        self.freeze();path=self.root/'frozen/corpus.json';path.chmod(0o600);path.write_text('{}')
        with self.assertRaises(ValueError):datasets.evaluate(self.root/'frozen')

    def test_known_development_overlap_reported(self):
        value=copy.deepcopy(self.value)
        old=private.read(private.REPO/'benchmarks/roles/corpus.json')['documents'][0]['provisions'][0]['text']
        value['documents'][0]['provisions'][0]['quote']=old
        self.assertEqual(1,datasets.overlap(value)['exact_provision_matches'])


class LiveGuards(unittest.TestCase):
    def test_expired_backend_claim_is_rejected_without_authorization_inference(self):
        import base64
        token='fixture.'+base64.urlsafe_b64encode(json.dumps({'role':'service_role','exp':1}).encode()).decode().rstrip('=')+'.not-a-real-signature'
        self.assertEqual('expired',preflight.claimed_backend_role(token,now=100))
        self.assertIsNone(preflight.claimed_backend_role('opaque-fixture-key'))
    def test_presence_does_not_establish_authorization_and_no_secret_output(self):
        values={'GOOGLE_API_KEY':'PRIVATE_TEST_SECRET','SUPABASE_URL':'https://private.invalid','SUPABASE_KEY':'PRIVATE_TEST_TOKEN'}
        with patch.dict(os.environ,values,clear=True),patch.object(preflight,'available',return_value=True):
            result=preflight.inspect()
        self.assertEqual(preflight.UNVERIFIED,result['gemini'])
        self.assertNotIn('PRIVATE_TEST',json.dumps(result));self.assertNotIn('private.invalid',json.dumps(result))

    def test_missing_packages_or_config_are_blocked_without_connections(self):
        with patch.dict(os.environ,{},clear=True),patch.object(preflight,'available',return_value=False):
            result=preflight.inspect()
            self.assertEqual(preflight.CONFIG,result['gemini'])
            self.assertEqual(preflight.DEPENDENCY,result['e5_model'])
            with patch.object(live.subprocess,'run') as called:
                result=live.guarded_child('gemini',execute=True,confirm_nonproduction=True,max_cost_usd='.01')
                called.assert_not_called()
        self.assertTrue(result['status'].startswith('BLOCKED'))

    def test_supabase_target_identity_and_https_guard(self):
        env={'LEGAL_BRAIN_LIVE_ENV':'nonproduction','SUPABASE_URL':'https://wrong.supabase.co','SUPABASE_KEY':'fake',
             'LEGAL_BRAIN_TEST_PROJECT_REF':'abcdefghijklmno'}
        with patch.dict(os.environ,env,clear=True),patch.object(preflight,'available',return_value=True):
            self.assertEqual('FAILED_PREFLIGHT',preflight.inspect(confirm_nonproduction=True,operator_opt_in=True)['supabase'])

    def test_no_opt_in_even_with_ready_credentials_never_starts_worker(self):
        with patch.object(live,'inspect',return_value={'gemini':preflight.READY}),patch.object(live.subprocess,'run') as worker:
            result=live.guarded_child('gemini')
        worker.assert_not_called();self.assertEqual(0,result['provider_requests'])

    def test_gemini_requires_budget_and_operator_prices(self):
        with patch.object(live,'inspect',return_value={'gemini':preflight.READY}),patch.dict(os.environ,{},clear=True),patch.object(live.subprocess,'run') as worker:
            result=live.guarded_child('gemini',execute=True,confirm_nonproduction=True)
        worker.assert_not_called();self.assertIn('budget',result['reason'])

    def test_provider_timeout_kills_child_contract_without_leaking_error(self):
        env={'GEMINI_INPUT_USD_PER_MTOK':'1','GEMINI_OUTPUT_USD_PER_MTOK':'2'}
        with patch.object(live,'inspect',return_value={'gemini':preflight.READY}),patch.dict(os.environ,env,clear=True),\
             patch.object(live.subprocess,'run',side_effect=subprocess.TimeoutExpired('PRIVATE_SECRET',.1)):
            result=live.guarded_child('gemini',execute=True,confirm_nonproduction=True,max_cost_usd='.01',timeout=1)
        self.assertEqual('FAILED_PROVIDER_TIMEOUT',result['status']);self.assertNotIn('PRIVATE',json.dumps(result))

    def test_trace_flags_and_call_caps_fail_closed(self):
        with self.assertRaises(ValueError):live.guarded_child('gemini',max_calls=999)
        with patch.object(live,'inspect',return_value={'gemini':preflight.READY}),patch.dict(os.environ,{'LANGSMITH_TRACING':'true'}):
            result=live.guarded_child('gemini',execute=True,confirm_nonproduction=True)
        self.assertEqual('prompt_tracing_enabled',result['reason'])

    def test_runtime_sdk_timeout_interface_must_be_present(self):
        class VerifiedFakeSDK:
            model_fields={'timeout':None,'max_retries':None,'max_output_tokens':None}
            def model_copy(self,update):return update
        self.assertEqual({'timeout':3,'max_retries':0,'max_output_tokens':512},bounded_model(VerifiedFakeSDK(),3,512))
        with self.assertRaises(ValueError):bounded_model(object())

    def test_release_states_never_collapse_to_one_ready_boolean(self):
        result=assess(engineering_passed=True)
        self.assertEqual('PASSED_EXECUTED_SCOPE',result['engineering'])
        self.assertEqual('BLOCKED',result['live_integration'])
        self.assertEqual('NOT_APPROVED',result['legal_review'])
        self.assertEqual('BLOCKED',result['public_deployment'])
