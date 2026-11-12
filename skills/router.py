"""Explainable routing. Document classification is evidence, never a legal finding."""
import re
import unicodedata
from dataclasses import asdict

from case_file import derive_forum_key

from .schemas import Candidate, JurisdictionContext, RoutingResult


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).casefold()
    text = re.sub('[\u064b-\u065f\u0670\u0640]', '', text)
    return text.translate(str.maketrans('أإآى', 'اااي'))


def matches(term: str, text: str) -> bool:
    return bool(re.search(r'(?<!\w)' + re.escape(normalize(term)) + r'(?!\w)', text))


# Aliases classify the task/document, never the applicable law.
DOCUMENT_CLASSES = {
    'nda': ('nda', 'confidentiality agreement', 'non-disclosure', 'اتفاقية سرية', 'عدم الافصاح'),
    'corporate_records': ('corporate documents', 'company records', 'due diligence', 'before acquisition',
                          'مستندات الشركة', 'العناية الواجبة', 'قبل الاستحواذ'),
    'agreement': ('agreement', 'contract', 'عقد', 'اتفاقية'),
}


def resolve(registry, request: str, *, document_type: str | None = None,
            jurisdiction: JurisdictionContext | None = None, skill_id: str | None = None,
            case=None) -> RoutingResult:
    # Validate explicit selection even when intake itself is incompatible.
    eligible = (registry.get(skill_id),) if skill_id is not None else registry.available()
    context = jurisdiction or JurisdictionContext()
    warnings = []
    if not context.known():
        warnings.append('Jurisdiction unknown: confirm governing law, forum and applicable regime before legal conclusions')
    else:
        missing = [key for key, value in asdict(context).items() if value == 'unknown']
        if missing:
            warnings.append('Unconfirmed jurisdiction dimensions: ' + ', '.join(missing))
    case_forum = None
    if case is not None:
        # Reuse CaseFile's normalization even for an incomplete intake payload.
        case_forum = derive_forum_key(getattr(case, 'forum', None) or '')
        country = normalize(getattr(case, 'country', None) or '')
        if country and country not in {'uae', 'u.a.e.', 'united arab emirates', 'الامارات', 'الامارات العربية المتحدة'}:
            return RoutingResult('incompatible', warnings=tuple(warnings),
                                 reason='Case country is outside the UAE workflow scope; confirm applicability before activation')
        if case_forum in {'adgm', 'difc'}:
            warnings.append(f'Case forum is {case_forum}; do not infer governing law from court jurisdiction')
            if context.court_jurisdiction != 'unknown' and context.court_jurisdiction != case_forum:
                return RoutingResult('incompatible', warnings=tuple(warnings),
                                     reason='Jurisdiction context conflicts with existing case forum')
    text = normalize(request)
    classified = {key for key, aliases in DOCUMENT_CLASSES.items()
                  if any(matches(alias, text) for alias in aliases)}
    if 'nda' in classified:
        classified.discard('agreement')
    ranked = []
    incompatible = False
    for skill in eligible:
        m = skill.manifest
        known = list(context.known())
        if case_forum in {'adgm', 'difc'}:
            known.append(case_forum)
        if any(j not in m.jurisdiction for j in known):
            incompatible = True
            continue
        score, reasons = 0, []
        if skill_id is not None:
            score, reasons = 100, ['Explicit validated skill selection']
        else:
            if document_type and normalize(document_type) in {normalize(t) for t in m.document_types}:
                score += 5
                reasons.append('Structured document type matches')
            types = classified.intersection(m.document_types)
            if types:
                score += 4
                reasons.append('Document classification: ' + ', '.join(sorted(types)))
            triggers = [term for term in m.trigger_terms if matches(term, text)]
            if triggers:
                score += min(len(triggers), 3) * 5
                reasons.append('Workflow triggers: ' + ', '.join(triggers))
        if score:
            ranked.append(Candidate(m.skill_id, m.version, score, tuple(reasons)))
    ranked.sort(key=lambda c: (-c.score, c.skill_id))
    if not ranked:
        return RoutingResult('incompatible' if incompatible else 'no_match', warnings=tuple(warnings),
                             reason='No compatible skill' if incompatible else 'No workflow evidence; existing workflow retained')
    if len(ranked) > 1 and ranked[0].score - ranked[1].score <= 2:
        return RoutingResult('ambiguous', candidates=tuple(ranked), warnings=tuple(warnings),
                             reason='Several plausible workflows; explicit selection required')
    return RoutingResult('selected', ranked[0].skill_id, tuple(ranked), tuple(warnings),
                         '; '.join(ranked[0].reasons))
