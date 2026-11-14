"""Validated immutable local registry with deterministic discovery."""
import json
from dataclasses import asdict
from .loader import BUNDLED_ROOT, load_skills
from .schemas import LegalSkill, SkillError
from .validator import identifier, validate_entrypoint, validate_manifest


class SkillRegistry:
    def __init__(self, skills: tuple[LegalSkill, ...]):
        self._skills = {}
        for skill in skills:
            validate_manifest(json.loads(json.dumps(asdict(skill.manifest))))
            validate_entrypoint(skill.instructions, skill.manifest)
            key = identifier(skill.manifest.skill_id)
            if key in self._skills:
                raise SkillError('Duplicate skill identifier')
            self._skills[key] = skill
        for skill in skills:
            for dependency in skill.manifest.dependencies:
                if dependency not in self._skills or not self._skills[dependency].manifest.enabled:
                    raise SkillError('Unavailable skill dependency')
        # Phase 1 dependencies describe prerequisites only; never activate or install them.
        def visit(key, stack):
            if key in stack:
                raise SkillError('Cyclic skill dependency')
            for dependency in self._skills[key].manifest.dependencies:
                visit(dependency, stack | {key})
        for key in self._skills:
            visit(key, set())

    @classmethod
    def discover(cls, root=BUNDLED_ROOT):
        return cls(load_skills(root))

    def get(self, skill_id: str) -> LegalSkill:
        skill = self._skills.get(identifier(skill_id))
        if skill is None or not skill.manifest.enabled:
            raise SkillError('Unknown or disabled skill identifier')
        return skill

    def available(self, *, category=None, jurisdiction=None, document_type=None) -> tuple[LegalSkill, ...]:
        return tuple(skill for _, skill in sorted(self._skills.items())
                     if skill.manifest.enabled
                     and (category is None or skill.manifest.category == category)
                     and (jurisdiction is None or jurisdiction in skill.manifest.jurisdiction)
                     and (document_type is None or document_type in skill.manifest.document_types))
