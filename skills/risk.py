"""Deterministic ordinal scoring; never estimate probabilities or exposure."""
from dataclasses import dataclass
from .schemas import SkillError


def assess_supplied_risk(data: dict | None) -> dict:
    """Only client-supported ordinal inputs; absent evidence cannot become a score."""
    if data is None:
        return RiskMatrix().assess(None, None)
    if not isinstance(data, dict) or set(data) - {'severity', 'likelihood', 'evidence_supported', 'matrix'}:
        raise SkillError('Invalid skill_risk fields')
    config = data.get('matrix', {})
    if not isinstance(config, dict) or set(config) - {'levels', 'bands'}:
        raise SkillError('Invalid risk matrix fields')
    try:
        matrix = RiskMatrix(**config)
    except (TypeError, ValueError) as exc:
        raise SkillError('Invalid risk matrix') from exc
    supported = data.get('evidence_supported', False)
    if type(supported) is not bool:
        raise SkillError('evidence_supported must be boolean')
    # Validate even unsupported inputs; no coercion of strings/bools to ratings.
    assessment = matrix.assess(data.get('severity'), data.get('likelihood'))
    if not supported:
        return matrix.assess(None, None)
    return {**assessment, 'basis': 'client_supplied_ratings_requiring_human_review'}


@dataclass(frozen=True)
class RiskMatrix:
    levels: int = 5
    bands: tuple[tuple[int, str], ...] = ((4, 'low'), (9, 'medium'), (15, 'high'), (25, 'critical'))

    def __post_init__(self):
        if type(self.levels) is not int or not 2 <= self.levels <= 10 or not self.bands:
            raise SkillError('Invalid risk matrix levels')
        previous = 0
        for bound, label in self.bands:
            if type(bound) is not int or bound <= previous or not isinstance(label, str) or not label:
                raise SkillError('Risk bands must have increasing integer bounds and labels')
            previous = bound
        if previous != self.levels ** 2:
            raise SkillError('Risk bands must cover the complete matrix')

    def assess(self, severity: int | None, likelihood: int | None) -> dict:
        for value in (severity, likelihood):
            if value is not None and (type(value) is not int or not 1 <= value <= self.levels):
                raise SkillError('Risk ratings must be supported ordinal integers or null')
        if severity is None or likelihood is None:
            return {'status': 'unknown', 'score': None, 'overall_risk': 'unknown'}
        score = severity * likelihood
        label = next(label for bound, label in self.bands if score <= bound)
        return {'status': 'scored', 'score': score, 'overall_risk': label}
