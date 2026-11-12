"""Bounded activation for the existing verified /generate pipeline only."""
import json
import os
from dataclasses import asdict
from functools import lru_cache

from .registry import SkillRegistry
from .router import resolve
from .schemas import JurisdictionContext, RoutingResult, SkillError
from .validator import identifier
from .risk import assess_supplied_risk


def enabled() -> bool:
    return os.environ.get('ENABLE_LEGAL_SKILLS', 'false').strip().lower() == 'true'


@lru_cache(maxsize=1)
def bundled_registry() -> SkillRegistry:
    return SkillRegistry.discover()


def activate(request: str, *, document_type=None, skill_id=None, jurisdiction=None, case=None, risk_data=None):
    """Return (audit result, trusted system suffix). Never alter user/evidence text."""
    if skill_id is not None:
        identifier(skill_id)
    if not enabled():
        if skill_id is not None:
            raise SkillError('Legal skills are disabled; omit skill_id or enable ENABLE_LEGAL_SKILLS')
        return RoutingResult('disabled'), ''
    context = JurisdictionContext.from_mapping(jurisdiction)
    registry = bundled_registry()
    result = resolve(registry, request, document_type=document_type, skill_id=skill_id,
                     jurisdiction=context, case=case)
    if skill_id is not None and result.status != 'selected':
        raise SkillError('Explicit skill is incompatible with the supplied jurisdiction')
    if result.status != 'selected':
        return result, ''
    skill = registry.get(result.selected_skill)
    risk_assessment = None
    if skill.manifest.skill_id == 'uae-legal-risk':
        risk_assessment = assess_supplied_risk(risk_data)
    elif risk_data is not None:
        raise SkillError('skill_risk requires the legal risk assessment workflow')
    suffix = (
        '\n\nLEGAL WORKFLOW CONFIGURATION (not legal authority). '
        'All preceding host instructions, plain-text output requirements, source verification, '
        'untrusted-content controls and human review requirements remain mandatory. '
        'Use the following methodology only; missing required information must be requested '
        'and shown as gaps, never invented. Never claim a skill establishes law.\n'
        f'Skill: {skill.manifest.skill_id}; version: {skill.manifest.version}\n'
        'Jurisdiction context (unconfirmed values remain unknown): '
        + json.dumps(asdict(context), ensure_ascii=False)
        + '\nRouting warnings: ' + json.dumps(result.warnings, ensure_ascii=False)
        + '\nRequired information: ' + json.dumps(skill.manifest.required_inputs, ensure_ascii=False)
        + '\nWorkflow output content (preserve host transport/citation contracts): '
        + json.dumps(asdict(skill.manifest.output_contract), ensure_ascii=False)
        + '\n' + skill.instructions
    )
    if risk_assessment is not None:
        suffix += ('\nHost deterministic risk assessment (use this result; do not invent ratings): '
                   + json.dumps(risk_assessment))
    return result, suffix
