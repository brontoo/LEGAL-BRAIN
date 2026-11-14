"""Skills integration through the repository's offline fake dependency harness."""
import asyncio
import json
import os
import unittest
from unittest.mock import patch

from tests import fake_deps
fake_deps.install()
import main
from tests.test_main import MainTestBase, scripted_turn, GENUINE_QUOTE, FORGED_QUOTE


class SkillsAPITests(MainTestBase):
    def run(self, result=None):
        # Hermetic feature flag; individual tests enable it explicitly.
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'false'}):
            return super().run(result)

    def test_new_routes_require_existing_authentication(self):
        for method, path, fn, kwargs in main.app.routes:
            if path in {'/skills', '/skills/resolve'}:
                self.assertEqual([main.require_token], kwargs['dependencies'])
        with patch.object(main, 'API_TOKEN', 'test-token'):
            with self.assertRaises(main.HTTPException) as ctx:
                asyncio.run(main.require_token(None))
            self.assertEqual(401, ctx.exception.status_code)
            asyncio.run(main.require_token('Bearer test-token'))

    def test_discovery_disabled(self):
        self.assertEqual({'enabled': False, 'skills': []}, asyncio.run(main.list_legal_skills()))

    def test_discovery_public_metadata_only(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            response = asyncio.run(main.list_legal_skills())
        self.assertEqual(5, len(response['skills']))
        text = json.dumps(response)
        self.assertNotIn('instructions', text)
        self.assertNotIn('/workspace', text)
        self.assertNotIn('trigger_terms', text)

    def test_resolve_disabled(self):
        with self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(main.resolve_legal_skill(main.SkillResolveRequest(prompt='nda')))
        self.assertEqual(404, ctx.exception.status_code)

    def test_resolve_enabled(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            response = asyncio.run(main.resolve_legal_skill(main.SkillResolveRequest(prompt='nda')))
        self.assertEqual('uae-nda-review', response['selected_skill'])
        self.assertIn('reason', response)

    def test_invalid_explicit_ids_return_400(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
            for skill_id in ('../secret', 'not-known', 'https://host/skill'):
                with self.subTest(skill_id=skill_id), self.assertRaises(main.HTTPException) as ctx:
                    asyncio.run(main.resolve_legal_skill(main.SkillResolveRequest(prompt='nda', skill_id=skill_id)))
                self.assertEqual(400, ctx.exception.status_code)

    def test_invalid_context_returns_400(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}), self.assertRaises(main.HTTPException) as ctx:
            asyncio.run(main.resolve_legal_skill(main.SkillResolveRequest(prompt='nda', jurisdiction={'governing_law': 'foreign'})))
        self.assertEqual(400, ctx.exception.status_code)

    def test_generation_disabled_preserves_messages_headers_and_arguments(self):
        req = main.GenerateRequest(prompt='review agreement', doc_type='agreement')
        expected = main._build_messages(req.prompt, req.doc_type, main._case_from_payload(None))
        with patch.object(main, '_sse_generator', return_value=iter(())) as stream:
            response = asyncio.run(main.generate(req))
        actual = stream.call_args.args[0]
        self.assertEqual([m.content for m in expected], [m.content for m in actual])
        self.assertFalse(any(k.startswith('X-Legal-Skill') for k in response.headers))
        self.assertEqual('text/event-stream', response.media_type)
        self.assertIs(stream.call_args.args[3], main._redraft)

    def test_generation_activates_only_system_configuration(self):
        req = main.GenerateRequest(prompt='private-original', doc_type='agreement', skill_id='uae-contract-review')
        expected = main._build_messages(req.prompt, req.doc_type, main._case_from_payload(None))
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}), patch.object(main, '_sse_generator', return_value=iter(())) as stream:
            response = asyncio.run(main.generate(req))
        messages = stream.call_args.args[0]
        self.assertTrue(messages[0].content.startswith(expected[0].content))
        self.assertEqual(expected[1].content, messages[1].content)
        self.assertEqual('uae-contract-review', response.headers['X-Legal-Skill'])
        self.assertEqual('1.0.0', response.headers['X-Legal-Skill-Version'])
        self.assertIs(stream.call_args.args[3], main._redraft)

    def test_invalid_generation_never_starts_agent(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}), patch.object(main, '_sse_generator') as stream:
            with self.assertRaises(main.HTTPException) as ctx:
                asyncio.run(main.generate(main.GenerateRequest(prompt='review', doc_type='agreement', skill_id='../secret')))
        self.assertEqual(400, ctx.exception.status_code)
        stream.assert_not_called()

    def test_enabled_generation_keeps_citation_verification(self):
        for quote, expected_key in ((GENUINE_QUOTE, 'verified'), (FORGED_QUOTE, 'rejected')):
            with self.subTest(quote=quote):
                fake_deps.AGENT_SCRIPT = scripted_turn(quote)
                with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}):
                    response = asyncio.run(main.generate(main.GenerateRequest(prompt='review agreement', doc_type='agreement')))
                    async def consume():
                        return [chunk async for chunk in response.content]
                    events = [json.loads(chunk.removeprefix('data: ').strip()) for chunk in asyncio.run(consume())]
                citation = next(e for e in events if e['type'] == 'citations')
                # Existing stream shape is used without introducing skill-specific frames.
                self.assertTrue(citation['report'][expected_key])
                kinds = {e['type'] for e in events}
                self.assertIn('facts', kinds)
                self.assertIn('case', kinds)

    def test_no_match_header_and_fallback(self):
        with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': 'true'}), patch.object(main, '_sse_generator', return_value=iter(())) as stream:
            response = asyncio.run(main.generate(main.GenerateRequest(prompt='Hello', doc_type='unknown')))
        self.assertEqual('no_match', response.headers['X-Legal-Skill-Status'])
        self.assertEqual(main.SYSTEM_PROMPT_CITED, stream.call_args.args[0][0].content)


if __name__ == '__main__':
    unittest.main()
