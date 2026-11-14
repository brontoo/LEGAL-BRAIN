"""Read local, version-controlled data only; no imports, network or execution."""
import json
from pathlib import Path

from .schemas import LegalSkill, SkillError
from .validator import identifier, validate_entrypoint, validate_manifest

BUNDLED_ROOT = Path(__file__).parent / 'playbooks'


def _read(path: Path, limit: int) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise SkillError('Missing, linked or oversized skill file')
    return path.read_text(encoding='utf-8')


def _unique_pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SkillError('Duplicate JSON key')
        result[key] = value
    return result


def load_skills(root: Path = BUNDLED_ROOT) -> tuple[LegalSkill, ...]:
    # root is a developer-only local Path; it is never accepted from an API request.
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise SkillError('Skills require a trusted local directory')
    try:
        skills = []
        for folder in sorted(root.iterdir(), key=lambda p: p.name):
            if folder.is_symlink():
                raise SkillError('Linked skill directory is forbidden')
            if not folder.is_dir():
                continue
            identifier(folder.name)
            manifest = validate_manifest(json.loads(_read(folder / 'manifest.json', 65536),
                                                     object_pairs_hook=_unique_pairs))
            instructions = _read(folder / 'SKILL.md', 32768)
            validate_entrypoint(instructions, manifest)
            skills.append(LegalSkill(manifest, instructions))
        return tuple(skills)
    except (OSError, UnicodeError, ValueError) as exc:
        raise SkillError('Invalid bundled skill configuration') from exc
