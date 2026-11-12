"""Bounded bilingual modal frames; lexical candidates with field-level evidence.

Recognizes controlled grammatical constructions, not arbitrary legal entailment.
Unknown/ambiguous actors never become confirmed from generic sentence prefixes.
"""
from dataclasses import replace
from bisect import bisect_left
import re
from . import entities as legacy_entities
from .schemas import Entity, ClauseError
from .role_contracts import RoleValue, SemanticRole, RoleObligation
from .role_text import TextView, clean_party, sentences

EXTRA_ROLES = ('consultant', 'contractor', 'customer', 'الوسيط', 'الموظف', 'صاحب العمل')
PARTY_WORDS = (*legacy_entities.ROLE_WORDS, *EXTRA_ROLES, 'Neither party', 'either party', 'both parties', 'لأي من الطرفين')
MODAL = re.compile(r'(?<!\w)(?:is not required to|is required to|is entitled to|shall not|must not|may not|shall|must|may|represents|warrants|lapses|ceases|لا تعتبر|لا تستحق|لا يستحق|لا يلتزم|لا يحق|لا يجوز|(?:و)?يلتزم|يتعين على|يجب على|يحق|يجوز|يستحق|يقر|يسقط)(?!\w)', re.I)
ACTION_FORMS = {
    'pay': ('pay', 'payable', 'سداد', 'السداد', 'دفع'),
    'deliver': ('deliver', 'تسليم'), 'provide': ('provide', 'تقديم'),
    'refund': ('refund', 'recover', 'استرداد'), 'disclose': ('disclose', 'افصاح', 'الافصاح'),
    'terminate': ('terminate', 'انهاء'), 'assign': ('assign', 'تنازل', 'التنازل'),
    'substitute': ('substitute', 'استبدال'),
    'transfer': ('transfer', 'نقل'), 'complete': ('complete', 'اتمام'),
    'inspect': ('inspect', 'فحص'), 'repair': ('repair', 'اصلاح'),
    'notify': ('notify', 'اخطار'), 'deduct': ('deduct', 'خصم'),
    'adjust': ('adjust', 'تعديل'), 'retain': ('retain', 'احتفاظ', 'الاحتفاظ'),
    'return': ('return', 'رد'), 'reject': ('reject', 'رفض'),
    'appoint': ('appoint', 'تعيين'), 'solicit': ('solicit', 'استقطاب'),
    'resign': ('resign', 'استقالة', 'الاستقالة'), 'withhold': ('withhold', 'حجز'),
    'sign': ('sign', 'توقيع', 'التوقيع'), 'collect': ('collect', 'تحصيل'),
    'reimburse': ('reimburse',), 'preserve': ('preserve', 'حفظ'),
    'entitle': ('due', 'مستحقة', 'يستحق', 'تستحق'),
    'represent': ('represents', 'warrants', 'يقر'), 'lapse': ('lapses', 'ceases', 'يسقط'),
}
ACTION_LOOKUP = {word: action for action, words in ACTION_FORMS.items() for word in words}
ACTION = re.compile(r'(?<!\w)(?P<prefix>[وب]?)(?P<word>'+'|'.join(sorted(map(re.escape, ACTION_LOOKUP), key=len, reverse=True))+r')(?!\w)', re.I)


def parties(clauses):
    result = list(legacy_entities.extract(clauses))
    # Extend only explicit parenthesized definitions for the extra controlled roles.
    words = '|'.join(map(re.escape, EXTRA_ROLES))
    pattern = re.compile(r'(?P<name>[^\n;؛:()]{2,160}?)\s*\(\s*(?:the\s+|ويشار اليه بـ?\s*["“«]?)?(?P<alias>'+words+r')["”»]?\s*\)', re.I)
    for clause in clauses:
        view = TextView.of(clause.span.quote)
        for match in pattern.finditer(view.text):
            span = view.span(clause, match.start(), match.end())
            ns, ne = view.bounds(match.start('name'), match.end('name'))
            name = re.sub(r'^\d+[.:]?\s*', '', clause.span.quote[ns:ne]).strip()
            alias = view.span(clause, match.start('alias'), match.end('alias')).quote
            if not any(e.name == name and clean_party(alias) in [clean_party(a) for a in e.aliases] for e in result):
                result.append(Entity(f'E-{len(result)+1:04d}', name, (alias,), alias, 'unknown', span))
    return tuple(replace(e, ambiguity=any(other.name != e.name and {clean_party(a) for a in e.aliases} &
                                         {clean_party(a) for a in other.aliases} for other in result)) for e in result)


def party_pattern(entities):
    from .classification import fold
    words = set(PARTY_WORDS)
    for entity in entities:
        words.add(entity.name)
        words.update(entity.aliases)
    variants = {fold(w) for w in words}
    variants.update('ل'+w[1:] for w in tuple(variants) if w.startswith('ال'))
    choices = '|'.join(sorted(map(re.escape, variants), key=len, reverse=True))
    return re.compile(r'(?<!\w)(?:the\s+)?(?:'+choices+r')(?!\w)', re.I)


def party_value(clause, view, match, entities):
    span = view.span(clause, match.start(), match.end())
    key = clean_party(span.quote)
    matches = [e for e in entities if key in [clean_party(e.name), *(clean_party(a) for a in e.aliases)]]
    if matches and (len({e.name for e in matches}) > 1 or any(e.ambiguity for e in matches)):
        return RoleValue(None, (span, *(e.evidence for e in matches)), 'ambiguous')
    if matches:
        return RoleValue(matches[0].name, (span, matches[0].evidence), 'from_definition')
    return RoleValue(span.quote, (span,), 'explicit')


def modality(modal, prefix):
    negative_prefix = re.search(r'(?i)\bneither\b|\bno\s+\w+\s*$|^\s*لا\s', prefix)
    if modal in ('shall not', 'must not', 'may not', 'لا يجوز', 'لا يحق') or modal == 'may' and negative_prefix:
        return 'prohibited', 'negative'
    if modal in ('is not required to', 'لا يلتزم', 'لا يستحق', 'لا تستحق', 'لا تعتبر') or negative_prefix and modal in ('shall', 'must'):
        return 'negative_entitlement', 'negative'
    if modal in ('may', 'يحق', 'يجوز', 'is entitled to', 'يستحق'):
        return 'permitted', 'positive'
    if modal in ('represents', 'warrants', 'يقر'):
        return 'representation', 'positive'
    if modal in ('lapses', 'ceases', 'يسقط'):
        return 'fact', 'positive'
    return 'mandatory', 'positive'


def extract(clauses, entities, conditions, dates, financial=()):
    output = []
    party_re = party_pattern(entities)
    for clause in clauses:
        view = TextView.of(clause.span.quote)
        for sentence_start, sentence_end in sentences(view.text):
            modals = list(MODAL.finditer(view.text, sentence_start, sentence_end))
            if len(modals) > 128:
                raise ClauseError('Too many modal frames in one sentence')
            for index, modal in enumerate(modals):
                modal_source_start = clause.span.start+view.bounds(modal.start(), modal.end())[0]
                if any(c.source_clause == clause.clause_id and c.parent_relationship is None
                       and c.condition_role in ('exception', 'carve_out')
                       and c.evidence.start < modal_source_start < c.evidence.end for c in conditions):
                    continue
                left = modals[index-1].end() if index else sentence_start
                right = modals[index+1].start() if index+1 < len(modals) else sentence_end
                candidates = list(party_re.finditer(view.text, left, modal.start()))
                actor_match = candidates[-1] if candidates and not view.text[candidates[-1].end():modal.start()].strip(' ,،:') else None
                if index+1 < len(modals):
                    following = list(party_re.finditer(view.text, modal.end(), modals[index+1].start()))
                    if following and not view.text[following[-1].end():modals[index+1].start()].strip():
                        right = following[-1].start()
                        while right > modal.end() and view.text[right-1] in ' ,،':
                            right -= 1
                        right = modal.end()+len(re.sub(r'(?:\band|و)\s*$', '', view.text[modal.end():right]))
                modal_word = modal.group().removeprefix('و') if modal.group().startswith('ويلتزم') else modal.group()
                mode, polarity = modality(modal_word, view.text[sentence_start:modal.start()])
                if (modal_word.endswith('not') and re.match(r'\s*(?:only|necessarily|fail to)\b', view.text[modal.end():right])
                        or re.match(r'\s*(?:perhaps|possibly)\b', view.text[modal.end():right])):
                    mode, polarity = 'ambiguous', 'ambiguous'
                actor = party_value(clause, view, actor_match, entities) if actor_match else RoleValue()
                action_start = modal.end()
                if re.search(r'[\u0600-\u06ff]', modal_word) and modal_word not in ('لا تعتبر', 'يسقط'):
                    tail_party = party_re.match(view.text, action_start + len(view.text[action_start:right])-len(view.text[action_start:right].lstrip()), right)
                    if tail_party:
                        actor = party_value(clause, view, tail_party, entities)
                        action_start = tail_party.end()
                raw_left, raw_right = view.bounds(sentence_start, sentence_end)
                frame_start = actor_match.start() if actor_match else modal.start()
                if re.search(r'[\u0600-\u06ff]', modal_word):
                    frame_start = modal.start()
                source_frame_start = clause.span.start+view.bounds(frame_start, modal.end())[0]
                source_first_modal = clause.span.start+view.bounds(modals[0].start(), modals[0].end())[0]
                local_conditions = [c for c in conditions if c.source_clause == clause.clause_id and c.parent_relationship is None
                                    and clause.span.start+raw_left <= c.evidence.start < clause.span.start+raw_right
                                    and (c.evidence.start >= source_frame_start or c.evidence.start < source_first_modal)]
                # A qualification following the next actor's modal is not attached backward.
                local_conditions = [c for c in local_conditions if c.evidence.start < clause.span.start+view.bounds(max(action_start, modal.start()), right)[1]] if action_start < right else local_conditions
                cut = min((bisect_left(view.positions, c.evidence.start-clause.span.start)
                           for c in local_conditions if c.evidence.start >= clause.span.start+view.bounds(modal.start(), modal.end())[1]), default=right)
                action_end = min(right, cut)
                available_actions = list(ACTION.finditer(view.text, action_start, action_end))
                action_matches = []
                for candidate in available_actions:
                    if not action_matches or candidate.group('prefix') == 'و' or re.search(
                            r'(?:\band(?:\s+to)?|و)\s*$', view.text[action_matches[-1].end():candidate.start()]):
                        action_matches.append(candidate)
                # Modal verbs can themselves be the action (entitlement, representation, lapse).
                if modal_word in ('يستحق', 'لا يستحق', 'لا تستحق', 'represents', 'warrants', 'يقر', 'lapses', 'ceases', 'يسقط'):
                    action_matches = list(ACTION.finditer(view.text, modal.start(), modal.end()))[:1]
                if len(action_matches) > 32:
                    raise ClauseError('Too many coordinated actions')
                if not action_matches:
                    action_matches = [None]
                for action_index, action_match in enumerate(action_matches):
                    action_name = ACTION_LOOKUP[action_match.group('word')] if action_match else None
                    uncertainty = ['deterministic_linguistic_candidate_requires_review']
                    action_evidence = (view.span(clause, action_match.start('word'), action_match.end('word')),) if action_match else ()
                    action = RoleValue(action_name, action_evidence, 'lexical_candidate' if action_match else 'unknown')
                    beneficiary = RoleValue()
                    object_value = RoleValue()
                    begin = max(action_match.end(), action_start) if action_match else action_start
                    end = action_matches[action_index+1].start() if action_index+1 < len(action_matches) else action_end
                    section = view.text[begin:end]
                    # Time modifiers are not the grammatical object of the action.
                    time_marker = re.search(r'\bwithin\b|\bno later than\b|خلال', section)
                    if time_marker:
                        end = begin+time_marker.start()
                        section = view.text[begin:end]
                    party_matches = list(party_re.finditer(view.text, begin, end))
                    if party_matches:
                        candidate = party_matches[0]
                        before = view.text[begin:candidate.start()].strip()
                        is_recipient = (not before and action_name in ('pay', 'reimburse', 'notify') or
                                        re.search(r'(?:\bto|\bfor|ل)\s*$', before) or candidate.group().startswith('لل'))
                        if is_recipient and mode != 'prohibited':
                            beneficiary = party_value(clause, view, candidate, entities)
                            if candidate.start() == begin+len(section)-len(section.lstrip()):
                                begin = candidate.end()
                            else:
                                end = candidate.start()
                    if modal_word == 'لا تعتبر' and action_match and action_start < action_match.start():
                        a, b = action_start, action_match.start()
                        while a < b and view.text[a].isspace():
                            a += 1
                        while b > a and view.text[b-1].isspace():
                            b -= 1
                        nominal = view.span(clause, a, b)
                        object_value = RoleValue(nominal.quote, (nominal,), 'explicit_expression')
                    elif action_name == 'lapse' and view.text[sentence_start:modal.start()].strip():
                        a, b = sentence_start, modal.start()
                        while a < b and view.text[a].isspace():
                            a += 1
                        while b > a and view.text[b-1].isspace():
                            b -= 1
                        nominal = view.span(clause, a, b)
                        object_value = RoleValue(nominal.quote, (nominal,), 'explicit_expression')
                    elif action_name in ('pay', 'entitle') and re.search(r'\b(?:commission|penalty)\b|المبالغ|الغرامة|العمولة', view.text[sentence_start:modal.start()]):
                        nominal = re.search(r'\b(?:commission|penalty)\b|المبالغ|الغرامة|العمولة', view.text[sentence_start:modal.start()])
                        object_value = RoleValue(view.span(clause, sentence_start+nominal.start(), sentence_start+nominal.end()).quote,
                                                 (view.span(clause, sentence_start+nominal.start(), sentence_start+nominal.end()),), 'explicit')
                    else:
                        raw = view.text[begin:end]
                        lead = re.match(r'\s*(?:(?:to|عن|على)\s+)?', raw)
                        begin += lead.end()
                        while end > begin and view.text[end-1] in ' .;؛,،':
                            end -= 1
                        trimmed = re.sub(r'\s+(?:and|و)$', '', view.text[begin:end])
                        trimmed = re.sub(r'\s+(?:to|for)$', '', trimmed)
                        if trimmed.strip() in ('and', 'و'):
                            trimmed = ''
                        end = begin+len(trimmed)
                        if begin < end:
                            obj = view.span(clause, begin, end)
                            object_value = RoleValue(obj.quote, (obj,), 'explicit_expression')
                    trigger_ids = tuple(c.relationship_id for c in local_conditions if c.condition_role in ('trigger', 'condition_subsequent'))
                    exception_ids = tuple(c.relationship_id for c in local_conditions if c.condition_role in ('exception', 'carve_out'))
                    condition_ids = tuple(c.relationship_id for c in local_conditions if c.condition_role in ('condition_precedent', 'dependency'))
                    conditional = bool(trigger_ids or condition_ids or any(c.condition_role == 'exception' for c in local_conditions))
                    # Bind local modifiers to the action region. A later actor's
                    # amount/deadline must not leak into an earlier frame.
                    modifier_start = action_match.start() if action_match else modal.start()
                    modifier_end = action_matches[action_index+1].start() if action_index+1 < len(action_matches) else right
                    source_modifier_start, source_modifier_end = view.bounds(modifier_start, modifier_end)
                    local_dates = tuple(d.date_id for d in dates if d.source_clause == clause.clause_id
                                        and clause.span.start+source_modifier_start <= d.evidence.start < clause.span.start+source_modifier_end)
                    local_money = tuple(m.financial_id for m in financial if m.source_clause == clause.clause_id
                                        and clause.span.start+source_modifier_start <= m.evidence.start < clause.span.start+source_modifier_end)
                    kind = ('prohibited' if mode == 'prohibited' else 'representation' if mode == 'representation' else
                            'statement_of_fact' if mode in ('negative_entitlement', 'fact', 'ambiguous') else
                            'discretionary_right' if mode == 'permitted' else 'conditional_obligation' if conditional else 'mandatory')
                    obligation_type = 'conditional_right' if conditional and mode == 'permitted' else mode if mode in ('negative_entitlement', 'prohibited') else kind
                    if actor.status in ('unknown', 'ambiguous'):
                        uncertainty.append('actor_'+actor.status)
                    if action_name is None:
                        uncertainty.append('action_unknown')
                    if mode == 'ambiguous':
                        uncertainty.append('negation_or_modal_scope_ambiguous')
                    consequence = RoleValue()
                    consequence_match = re.search(r'\bfailing which\b|\bin default\b|والا|وإلا', view.text[modal.end():right])
                    if consequence_match:
                        consequence_span = view.span(clause, modal.end()+consequence_match.start(), right)
                        consequence = RoleValue(consequence_span.quote, (consequence_span,), 'candidate_consequence')
                    frame = SemanticRole(actor, action, object_value, beneficiary, mode, polarity, obligation_type,
                                         (view.span(clause, modal.start(), modal.end()),), conditional, condition_ids,
                                         trigger_ids, exception_ids, local_dates, local_money, consequence=consequence,
                                         uncertainty=tuple(uncertainty))
                    evidence = view.span(clause, sentence_start, sentence_end)
                    trigger = next((c.referenced_condition for c in local_conditions if c.relationship_id in trigger_ids), None)
                    output.append(RoleObligation(f'O-{len(output)+1:04d}', clause.clause_id, kind, actor.value,
                                                 beneficiary.value, action_evidence[0].quote if action_evidence else '',
                                                 object_value.value or '', trigger, condition_ids, local_dates, exception_ids,
                                                 (), evidence, semantic_role=frame))
                    if len(output) > 2000:
                        raise ClauseError('Too many obligation records')
    return tuple(output)
