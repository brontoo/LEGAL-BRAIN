"""Typed source qualifications. Wording never proves fulfilment of an event."""
import re
from .role_contracts import QualifiedCondition
from .role_text import TextView
from .schemas import ClauseError
from .roles_v2 import MODAL, party_pattern

PATTERNS = (
    ('reservation_of_rights', r'without prejudice to|دون الاخلال'),
    ('condition_precedent', r'provided that|subject to|on condition that|until|before|with(?:out)? prior written consent|الا بعد|شريطة(?: ان)?|رهنا|حتى|قبل|دون'),
    ('exception', r'unless|ما لم'),
    ('carve_out', r'except(?: as provided)?|باستثناء'),
    ('trigger', r'after|following|upon|if|in the event of|بعد|عند|في حال'),
    ('dependency', r'prior written consent|موافقة خطية مسبقة|موافقة كتابية مسبقة'),
)
COMBINED = re.compile(r'(?<!\w)(?:' + '|'.join('(?P<K'+str(i)+'>'+p+')' for i, (_, p) in enumerate(PATTERNS)) + r')(?!\w)', re.I)


def extract(clauses, entities=()):
    result = []
    parties = party_pattern(entities)
    for clause in clauses:
        view = TextView.of(clause.span.quote)
        matches = list(COMBINED.finditer(view.text))
        modals = list(MODAL.finditer(view.text))
        for index, match in enumerate(matches):
            kind = PATTERNS[int(match.lastgroup[1:])][0]
            end = min(len(view.text), match.end()+500)
            punctuation = re.search(r'[,،;؛\n]|[.!?](?=\s|$)', view.text[match.end():end])
            if punctuation:
                end = match.end()+punctuation.start()
            # A coordinated new actor/modal ends this qualification. An embedded
            # event inside an exception is not promoted to a fresh primary scope.
            for upcoming in modals:
                if not match.end() <= upcoming.start() < end:
                    continue
                prior_modals = [m for m in modals if m.start() < match.start()
                                and not re.search(r'[.;؛\n]', view.text[m.end():match.start()])]
                preceding = list(parties.finditer(view.text, match.end(), upcoming.start()))
                if preceding and not view.text[preceding[-1].end():upcoming.start()].strip():
                    party_start = preceding[-1].start()
                    join = re.search(r'(?:\band|و)\s*$', view.text[match.end():party_start])
                    if join or not prior_modals:
                        end = match.end()+join.start() if join else party_start
                        break
                if upcoming.group().startswith('و') or not prior_modals and re.search(r'[\u0600-\u06ff]', upcoming.group()):
                    end = upcoming.start()
                    break
            while end > match.end() and view.text[end-1].isspace():
                end -= 1
            span = view.span(clause, match.start(), end)
            earlier = view.text[:match.start()]
            if kind == 'exception' and re.search(r'\bno\b[^.;\n]{0,120}\b(?:payable|due)\b|لا (?:يستحق|تستحق|تعتبر)', earlier):
                kind = 'condition_precedent'
            if kind == 'trigger' and re.search(r'\b(?:lapses|ceases)\b|يسقط|ينتهي', earlier):
                kind = 'condition_subsequent'
            legacy = 'trigger' if kind in ('trigger', 'condition_subsequent') else 'exception' if kind in ('exception', 'carve_out', 'reservation_of_rights') else 'condition'
            parent = next((c.relationship_id for c in reversed(result) if c.source_clause == clause.clause_id
                           and c.evidence.start < span.start < c.evidence.end), None)
            result.append(QualifiedCondition(f'COND-{len(result)+1:04d}', clause.clause_id, legacy,
                                             span.quote, (), span, condition_role=kind, parent_relationship=parent))
            if len(result) > 2000:
                raise ClauseError('Too many conditional relationships')
    return tuple(result)
