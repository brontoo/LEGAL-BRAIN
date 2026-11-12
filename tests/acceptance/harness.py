"""Offline paired plumbing run. Scripted output is identical in both modes."""
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import fake_deps
fake_deps.install()
import main
from citations import CITATIONS_BEGIN, CITATIONS_END

SCENARIOS = json.loads(Path(__file__).with_name('scenarios.json').read_text())
# Fictional contractual evidence: never described as legislation/current law.
CLAUSE = 'يلتزم الطرف الثاني بتقديم تقرير شهري عن الخدمات المتفق عليها.'
QUOTE = 'تقديم تقرير شهري عن الخدمات المتفق عليها'
SCRIPTED_DRAFT = 'مخرج افتراضي لاختبار مسار التنفيذ فقط.\n' + CLAUSE


def run_offline(scenario, language, *, enabled=True, explicit=False, quote=QUOTE,
                draft=None, evidence=True, redraft_output=None):
    variant = scenario['variants'][language]
    prompt = variant['prompt'] + ('\n\n' + variant['document'] if variant['document'] else '')
    fake_deps.reset()
    if scenario['id'] == '10':
        evidence = False
    if draft is None:
        draft = ('يرجى تقديم العقد والمرفقات. لا يمكن اعتماد مستند لم يقدم. تلزم مراجعة المحامي.'
                 if scenario['id'] == '10' else SCRIPTED_DRAFT)
    if evidence:
        fake_deps.FAKE_SUPABASE.set_rows('match_legal_contracts', [fake_deps.make_row(
            chunk_id=15001, document_name='FICTIONAL service clause; not legislation', chunk_content=CLAUSE)])
    body = draft + f'\n{CITATIONS_BEGIN}\nC1 :: {quote}\n{CITATIONS_END}'
    fake_deps.AGENT_SCRIPT = [{'tool': 'search_contract_clauses', 'args': {'query': prompt}}, {'content': body}]
    req = main.GenerateRequest(prompt=prompt, doc_type=scenario['document_type'],
                               skill_jurisdiction=scenario['jurisdiction'])
    if explicit:
        req.skill_id = scenario['expected_skill']
    if scenario.get('risk_inputs'):
        req.skill_risk = scenario['risk_inputs'][0]
    # No official source is supplied; the existing authority frame must say so.
    req.authority = {'authorities': [{'key':'fixture', 'instrument':'FICTIONAL internal policy',
                                     'article':'', 'kind':'secondary'}]}
    raw_stream = main.agent.stream
    captured = []
    def stream(state, *args, **kwargs):
        captured.extend(state['messages'])
        return raw_stream(state, *args, **kwargs)
    async def consume():
        response = await main.generate(req)
        chunks = [chunk async for chunk in response.content]
        return response, [json.loads(chunk.removeprefix('data: ').strip()) for chunk in chunks]
    with patch.dict(os.environ, {'ENABLE_LEGAL_SKILLS': str(enabled).lower()}), \
         patch.object(main.agent, 'stream', side_effect=stream), \
         patch.object(main.llm, 'invoke', return_value=SimpleNamespace(content='[]')) as review_call, \
         patch.object(main, '_authority_frame', wraps=main._authority_frame) as authority_call, \
         patch.object(main, '_redraft', return_value=draft.replace('**', '') if redraft_output is None else redraft_output) as redraft_call, \
         contextlib.redirect_stdout(io.StringIO()):
        response, events = asyncio.run(consume())
    by_type = {event['type']:event for event in events}
    return {'headers':response.headers, 'events':events, 'frames':by_type,
            'system':captured[0].content, 'user':captured[1].content,
            'review_calls':review_call.call_count, 'authority_calls':authority_call.call_count,
            'redraft_calls':redraft_call.call_count}


def offline_comparison():
    rows = []
    for scenario in SCENARIOS:
        for language in ('en','ar'):
            original = run_offline(scenario, language, enabled=False)
            skilled = run_offline(scenario, language, enabled=True)
            rows.append({
                'scenario':scenario['id'], 'language':language, 'mode':'offline_scripted',
                'expected_skill':scenario['expected_skill'],
                'selected_skill':skilled['headers'].get('X-Legal-Skill'),
                'host_prompt_preserved':skilled['system'].startswith(original['system']),
                'user_input_identical':original['user'] == skilled['user'],
                'scripted_output_identical':original['frames']['done']['document'] == skilled['frames']['done']['document'],
                'citation_reports_identical':original['frames']['citations'] == skilled['frames']['citations'],
                'authority_executed':skilled['authority_calls'] > 0,
                'review_executed':skilled['review_calls'] > 0,
                'diagnostics_present':'skill_diagnostics' in skilled['frames']['done'],
                'legal_quality':'NOT RUN — requires live paired outputs and lawyer scoring',
            })
    return {'mode':'offline_scripted', 'current_law_verified':False,
            'legal_reasoning_quality_assessed':False, 'results':rows}
