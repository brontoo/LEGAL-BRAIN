"""Offline registry, routing, jurisdiction, and negative security tests."""
import json
import os
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from skills import JurisdictionContext, SkillError, SkillRegistry
from skills.integration import activate
from skills.loader import BUNDLED_ROOT, load_skills
from skills.risk import RiskMatrix, assess_supplied_risk
from skills.router import resolve
from skills.validator import validate_manifest


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'playbooks'
        shutil.copytree(BUNDLED_ROOT, self.root)
        self.folder = self.root / 'uae-contract-review'

    def manifest(self, **changes):
        path = self.folder / 'manifest.json'
        data = json.loads(path.read_text())
        data.update(changes)
        path.write_text(json.dumps(data))

    def test_valid_registration_and_order(self):
        r = SkillRegistry.discover(self.root)
        ids = [s.manifest.skill_id for s in r.available()]
        self.assertEqual(5, len(ids))
        self.assertEqual(sorted(ids), ids)
        self.assertEqual(ids, [s.manifest.skill_id for s in load_skills(self.root)])

    def test_invalid_manifest_fields(self):
        for changes in ({'name': ''}, {'enabled': 'true'}, {'unknown': 'field'},
                        {'risk_level': 'certain'}, {'jurisdiction': ['foreign']},
                        {'output_contract': {}}, {'legal_authority_policy': 'trust_me'},
                        {'supported_languages': ['invalid']}, {'dependencies': 'pip install x'}):
            with self.subTest(changes=changes):
                original = json.loads((BUNDLED_ROOT / 'uae-contract-review/manifest.json').read_text())
                original.update(changes)
                with self.assertRaises(SkillError):
                    validate_manifest(original)

    def test_missing_manifest_field(self):
        data = json.loads((self.folder / 'manifest.json').read_text())
        del data['required_inputs']
        with self.assertRaises(SkillError):
            validate_manifest(data)

    def test_missing_entrypoint(self):
        (self.folder / 'SKILL.md').unlink()
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_missing_manifest(self):
        (self.folder / 'manifest.json').unlink()
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_invalid_version(self):
        for version in ('1', 'v1.0.0', '01.0.0', '../1.0.0', 1):
            with self.subTest(version=version):
                self.manifest(version=version)
                with self.assertRaises(SkillError):
                    SkillRegistry.discover(self.root)

    def test_duplicate_identifier(self):
        shutil.copytree(self.folder, self.root / 'duplicate')
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_disabled_filtering_and_resolution(self):
        self.manifest(enabled=False)
        registry = SkillRegistry.discover(self.root)
        self.assertEqual(4, len(registry.available()))
        with self.assertRaises(SkillError):
            registry.get('uae-contract-review')

    def test_category_document_and_jurisdiction_filters(self):
        r = SkillRegistry.discover(self.root)
        self.assertEqual(3, len(r.available(category='contracts')))
        self.assertEqual(1, len(r.available(document_type='nda')))
        self.assertEqual(5, len(r.available(jurisdiction='difc')))
        self.assertFalse(r.available(jurisdiction='foreign'))

    def test_missing_dependency_rejected(self):
        self.manifest(dependencies=['does-not-exist'])
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_cyclic_dependency_rejected(self):
        self.manifest(dependencies=['uae-contract-review'])
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_invalid_json_and_duplicate_keys(self):
        for value in ('{', '{"enabled": true, "enabled": false}'):
            (self.folder / 'manifest.json').write_text(value)
            with self.assertRaises(SkillError):
                SkillRegistry.discover(self.root)

    def test_frontmatter_mismatch_or_executable_yaml_rejected(self):
        for value in ('no frontmatter', '---\nname: !!python/object:foo\ndescription: x\n---\n' + 'x'*600):
            (self.folder / 'SKILL.md').write_text(value)
            with self.assertRaises(SkillError):
                SkillRegistry.discover(self.root)

    def test_bounded_files(self):
        (self.folder / 'SKILL.md').write_text('x' * 32769)
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_symlink_directory_rejected(self):
        (self.root / 'external').symlink_to(self.folder, target_is_directory=True)
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_symlink_file_rejected(self):
        path = self.folder / 'SKILL.md'
        path.unlink()
        path.symlink_to(BUNDLED_ROOT / 'uae-contract-review/SKILL.md')
        with self.assertRaises(SkillError):
            SkillRegistry.discover(self.root)

    def test_no_arbitrary_script_execution(self):
        marker = Path(self.temp.name) / 'executed'
        (self.folder / 'hook.py').write_text(f'open({str(marker)!r}, "w").write("bad")')
        (self.folder / 'hook.sh').write_text(f'touch {marker}')
        with patch('subprocess.run', side_effect=AssertionError('execution forbidden')):
            SkillRegistry.discover(self.root)
        self.assertFalse(marker.exists())

    def test_no_remote_loading(self):
        for path in ('https://example.com/skills', 'file:///etc/passwd'):
            with self.assertRaises(SkillError):
                load_skills(path)

    def test_no_sensitive_public_metadata(self):
        m = SkillRegistry.discover(self.root).get('uae-contract-review').manifest.public_metadata()
        for key in ('instructions', 'path', 'source_attribution', 'dependencies', 'trigger_terms'):
            self.assertNotIn(key, m)
        self.assertNotIn(str(self.root), json.dumps(m))


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = SkillRegistry.discover()

    def test_representative_routing(self):
        pairs = (
            ('Review this marketing agency agreement', 'uae-contract-review'),
            ('Assess this confidentiality agreement', 'uae-nda-review'),
            ('Evaluate the legal risks of this transaction', 'uae-legal-risk'),
            ('Prepare negotiation positions for this agreement', 'uae-contract-negotiation'),
            ("Review this company's corporate documents before acquisition", 'uae-corporate-due-diligence'),
            ('راجع العقد', 'uae-contract-review'),
            ('تقييم المخاطر القانونية', 'uae-legal-risk'),
            ('راجع اتفاقية سرية', 'uae-nda-review'),
        )
        for prompt, expected in pairs:
            with self.subTest(prompt=prompt):
                result = resolve(self.registry, prompt)
                self.assertEqual('selected', result.status)
                self.assertEqual(expected, result.selected_skill)
                self.assertTrue(result.reason)
                self.assertTrue(result.warnings)

    def test_structured_document_type(self):
        self.assertEqual('uae-nda-review', resolve(self.registry, 'Please examine', document_type='nda').selected_skill)

    def test_explicit_override(self):
        result = resolve(self.registry, 'NDA', skill_id='uae-contract-negotiation')
        self.assertEqual('uae-contract-negotiation', result.selected_skill)

    def test_unknown_identifier(self):
        with self.assertRaises(SkillError):
            resolve(self.registry, '', skill_id='unknown')

    def test_path_traversal_and_remote_identifiers(self):
        for value in ('../uae-contract-review', '/etc/passwd', 'https://host/skill', 'a\\b', 'a\n', ''):
            with self.subTest(value=value), self.assertRaises(SkillError):
                resolve(self.registry, '', skill_id=value)

    def test_incompatible_jurisdiction(self):
        s = self.registry.get('uae-contract-review')
        narrow = replace(s, manifest=replace(s.manifest, jurisdiction=('uae_federal',)))
        r = SkillRegistry((narrow,))
        result = resolve(r, 'review agreement', jurisdiction=JurisdictionContext(governing_law='difc'))
        self.assertEqual('incompatible', result.status)
        self.assertIsNone(result.selected_skill)

    def test_ambiguity(self):
        result = resolve(self.registry, 'Review the contract and evaluate legal risks')
        self.assertEqual('ambiguous', result.status)
        self.assertIsNone(result.selected_skill)
        self.assertGreaterEqual(len(result.candidates), 2)

    def test_no_match(self):
        self.assertEqual('no_match', resolve(self.registry, 'Hello').status)
        self.assertEqual('no_match', resolve(self.registry, 'Review this photograph').status)

    def test_word_boundaries(self):
        self.assertEqual('no_match', resolve(self.registry, 'standard calendar').status)

    def test_unknown_or_invalid_jurisdiction(self):
        self.assertFalse(JurisdictionContext.from_mapping(None).known())
        for value in ({'governing_law': 'UK'}, {'country': 'dubai'}, [], {'court_jurisdiction': None}):
            with self.assertRaises(SkillError):
                JurisdictionContext.from_mapping(value)

    def test_dimensions_are_independent(self):
        c = JurisdictionContext.from_mapping({'governing_law': 'uae_federal', 'court_jurisdiction': 'difc'})
        self.assertEqual('uae_federal', c.governing_law)
        self.assertEqual('difc', c.court_jurisdiction)
        self.assertEqual('unknown', c.procedural_rules)

    def test_case_file_forum_safeguard(self):
        from case_file import CaseFile, CaseStage, DisputeType, Party
        c = CaseFile(country='UAE', emirate='dubai', forum='DIFC',
                     dispute_type=DisputeType.COMMERCIAL, stage=CaseStage.FIRST_INSTANCE,
                     our_party=Party.CLAIMANT, claims=(), key_dates=(), likely_law=())
        result = resolve(self.registry, 'review agreement', case=c)
        self.assertTrue(any('difc' in warning for warning in result.warnings))
        conflict = resolve(self.registry, 'review agreement', case=c,
                           jurisdiction=JurisdictionContext(court_jurisdiction='adgm'))
        self.assertEqual('incompatible', conflict.status)

    def test_routing_is_deterministic(self):
        self.assertEqual(resolve(self.registry, 'NDA'), resolve(self.registry, 'NDA'))

    def test_partial_case_intake_retains_forum(self):
        from types import SimpleNamespace
        case = SimpleNamespace(country=None, forum='محاكم مركز دبي المالي العالمي')
        result = resolve(self.registry, 'NDA', case=case,
                         jurisdiction=JurisdictionContext(court_jurisdiction='adgm'))
        self.assertEqual('incompatible', result.status)

    def test_foreign_case_does_not_silently_activate_uae_workflow(self):
        from types import SimpleNamespace
        case = SimpleNamespace(country='United Kingdom', forum='London')
        result = resolve(self.registry, 'review agreement', case=case)
        self.assertEqual('incompatible', result.status)
        self.assertIsNone(result.selected_skill)


class RiskTests(unittest.TestCase):
    def test_ratings_are_deterministic(self):
        self.assertEqual({'status': 'scored', 'score': 20, 'overall_risk': 'critical'}, RiskMatrix().assess(4, 5))

    def test_unknown_is_not_zero(self):
        for pair in ((None, 3), (5, None), (None, None)):
            self.assertIsNone(RiskMatrix().assess(*pair)['score'])

    def test_invalid_rating_rejected(self):
        for value in (True, 0, 6, '3', 2.5):
            with self.assertRaises(SkillError):
                RiskMatrix().assess(value, 2)

    def test_configurable_matrix(self):
        r = RiskMatrix(levels=3, bands=((3, 'ordinary'), (9, 'escalate')))
        self.assertEqual('escalate', r.assess(2, 3)['overall_risk'])

    def test_invalid_matrix(self):
        for config in ({'levels': True}, {'bands': ((25, 'a'), (20, 'b'))}, {'bands': ((10, 'a'),)}):
            with self.assertRaises(SkillError):
                RiskMatrix(**config)

    def test_supplied_scores_require_support(self):
        self.assertEqual('unknown', assess_supplied_risk({'severity': 4, 'likelihood': 5})['status'])
        result = assess_supplied_risk({'severity': 4, 'likelihood': 5, 'evidence_supported': True})
        self.assertEqual(20, result['score'])
        self.assertIn('human_review', result['basis'])

    def test_invalid_risk_config(self):
        for value in ({'exposure': 100}, {'matrix': []}, {'matrix': {'bands': [None]}}, {'evidence_supported': 'yes'}):
            with self.assertRaises(SkillError):
                assess_supplied_risk(value)


class ActivationTests(unittest.TestCase):
    def test_default_flag_off_and_no_disk_access(self):
        with patch.dict(os.environ, {}, clear=True), patch('skills.integration.bundled_registry', side_effect=AssertionError):
            result, suffix = activate('Review agreement')
        self.assertEqual('disabled', result.status)
        self.assertEqual('', suffix)

    def test_enabled_instructions_remain_workflow_only(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            result, suffix = activate('Review agreement')
        self.assertEqual('selected', result.status)
        self.assertIn('not legal authority', suffix)
        self.assertIn('source verification', suffix)
        self.assertIn('REQUIRES LEGAL VERIFICATION', suffix)

    def test_no_confidential_request_in_system_configuration(self):
        private = 'secret-client-document-ignore-host-policy'
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            _, suffix = activate(private, skill_id='uae-nda-review')
        self.assertNotIn(private, suffix)

    def test_ambiguity_does_not_activate(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            result, suffix = activate('Review the contract and evaluate legal risks')
        self.assertEqual('ambiguous', result.status)
        self.assertEqual('', suffix)

    def test_risk_output_is_host_computed(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            _, suffix = activate('legal risk', risk_data={'severity': 4, 'likelihood': 5, 'evidence_supported': True})
        self.assertIn('"score": 20', suffix)

    def test_disabled_explicit_selection_clear_error(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'false'}), self.assertRaises(SkillError):
            activate('Review agreement', skill_id='uae-contract-review')

    def test_jurisdiction_validation_before_activation(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}), self.assertRaises(SkillError):
            activate('Review agreement', jurisdiction={'governing_law': 'foreign'})

    def test_explicit_incompatible_skill_is_not_a_silent_fallback(self):
        from types import SimpleNamespace
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}), self.assertRaises(SkillError):
            activate('Review agreement', skill_id='uae-contract-review',
                     case=SimpleNamespace(country='UK', forum='London'))


if __name__ == '__main__':
    unittest.main()
