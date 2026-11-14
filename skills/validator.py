"""Strict manifests and deliberately restricted YAML frontmatter."""
import json
import re
from dataclasses import fields

from .schemas import (Jurisdiction, OutputContract, SkillError, SkillManifest,
                      SourceAttribution)

IDENTIFIER = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
VERSION = re.compile(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z')
AUTHORITY_POLICY = 'workflow_only_verified_authority_required'


def identifier(value: str) -> str:
    if not isinstance(value, str) or len(value) > 80 or not IDENTIFIER.fullmatch(value):
        raise SkillError('Invalid skill identifier')
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise SkillError('Expected bounded nonempty text')
    return value


def _strings(value: object, *, empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 100 or (not value and not empty):
        raise SkillError('Expected a bounded list of strings')
    result = tuple(_text(v) for v in value)
    if len(set(result)) != len(result):
        raise SkillError('Duplicate metadata values')
    return result


def validate_manifest(data: object) -> SkillManifest:
    if not isinstance(data, dict) or set(data) != {f.name for f in fields(SkillManifest)}:
        raise SkillError('Manifest fields are missing or unknown')
    data = dict(data)
    identifier(data['skill_id'])
    if not isinstance(data['version'], str) or not VERSION.fullmatch(data['version']):
        raise SkillError('Version must be numeric major.minor.patch')
    for key in ('name', 'description', 'category'):
        _text(data[key])
    for key in ('jurisdiction', 'supported_languages', 'document_types', 'trigger_terms',
                'required_inputs', 'optional_inputs', 'dependencies', 'review_requirements'):
        data[key] = _strings(data[key], empty=key in ('dependencies', 'optional_inputs'))
    if set(data['jurisdiction']) - {j.value for j in Jurisdiction if j != Jurisdiction.UNKNOWN}:
        raise SkillError('Invalid supported jurisdiction')
    if set(data['supported_languages']) - {'ar', 'en'}:
        raise SkillError('Unsupported language')
    if type(data['enabled']) is not bool or data['risk_level'] not in {'low', 'medium', 'high'}:
        raise SkillError('Invalid enabled flag or risk level')
    if data['legal_authority_policy'] != AUTHORITY_POLICY:
        raise SkillError('Skill must require verified legal authority')
    output = data['output_contract']
    if not isinstance(output, dict) or set(output) != {'sections', 'item_fields'}:
        raise SkillError('Invalid output contract')
    data['output_contract'] = OutputContract(_strings(output['sections']), _strings(output['item_fields']))
    source = data['source_attribution']
    if not isinstance(source, dict) or set(source) != {'urls', 'adaptation'}:
        raise SkillError('Invalid attribution')
    urls = _strings(source['urls'])
    if any(not url.startswith('https://github.com/') for url in urls):
        raise SkillError('Attribution must identify reviewed GitHub references')
    data['source_attribution'] = SourceAttribution(urls, _text(source['adaptation']))
    return SkillManifest(**data)


def validate_entrypoint(text: str, manifest: SkillManifest) -> None:
    # Only two scalar keys are supported. No YAML tags, aliases or object loading.
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        raise SkillError('Missing SKILL.md frontmatter')
    try:
        end = lines.index('---', 1)
        front = {}
        for line in lines[1:end]:
            key, value = line.split(':', 1)
            if key in front or key not in {'name', 'description'}:
                raise SkillError('Invalid frontmatter keys')
            value = value.strip()
            # Quoted JSON strings are a supported subset of YAML scalars.
            front[key] = json.loads(value) if value.startswith('"') else value
        if front != {'name': manifest.name, 'description': manifest.description}:
            raise SkillError('Frontmatter must match manifest name and description')
        if len('\n'.join(lines[end + 1:]).strip()) < 500:
            raise SkillError('Skill instructions are incomplete')
    except (ValueError, TypeError) as exc:
        raise SkillError('Invalid SKILL.md frontmatter or body') from exc
