"""Modal candidates, with sentence-local conditions and unresolved participants explicit."""
import re
from .evidence import subspan
from .schemas import Obligation
from .entities import resolve_role
from .terms import sentence_bounds

MODAL = re.compile(r'(?P<modal>\bshall not\b|\bmust not\b|\bmay not\b|\bshall\b|\bmust\b|\bis entitled to\b|\bmay\b|\brepresents\b|\bwarrants\b|\bintends to\b|\bis\b|لا يجوز|يحظر|يلتزم|يتعين على|يجب على|يحق ل|يجوز ل|يسقط حقه|يستحق|يقر|يعتزم)', re.I)


def extract(clauses, entities, conditions, dates):
    results = []
    for clause in clauses:
        text = clause.span.quote
        for match in MODAL.finditer(text):
            modal = match.group().lower()
            start, end = sentence_bounds(text, match.start(), match.end())
            sentence = text[start:end]
            # A second modal is an additional candidate, never confirmation of a shared actor.
            prefix = text[start:match.start()].strip()
            prefix = re.sub(r'^(?:(?:Clause|Article|المادة|البند)\s+)?\d+(?:[./]\d+)*(?:\([a-z]\))?\s*[:.)-]?\s*', '', prefix, flags=re.I)
            # A heading or introductory condition is not a participant.
            if ',' in prefix or '،' in prefix:
                prefix = re.split('[,،]', prefix)[-1].strip()
            prefix = re.sub(r'^(?:Payment|Termination|Delivery|الدفع|السداد)\s*:\s*', '', prefix, flags=re.I)
            if MODAL.search(prefix):
                continue
            actor = prefix or None
            action_start = match.end()
            if re.search(r'[\u0600-\u06ff]', modal):
                tail = text[match.end():end]
                party = re.match(r'\s*((?:الطرف\s+(?:الأول|الاول|الثاني))|(?:المورد|العميل|الشركة|المشتري|البائع|المؤجر|المستأجر|الوكيل|الموكل))(?=\s)', tail)
                if party:
                    actor = party.group(1)
                    action_start += party.end()
                else:
                    actor = None
            resolved = resolve_role(actor or '', entities)
            actor = resolved or actor
            kind = ('prohibited' if modal in ('shall not', 'must not', 'may not', 'لا يجوز', 'يحظر') else
                    'discretionary_right' if modal in ('may', 'يجوز ل') else
                    'right' if modal in ('is entitled to', 'يحق ل', 'يستحق') else
                    'representation' if modal in ('represents', 'warrants', 'يقر') else
                    'commercial_intention' if modal in ('intends to', 'يعتزم') else
                    'statement_of_fact' if modal == 'is' else
                    'right_lapse' if modal == 'يسقط حقه' else 'mandatory')
            local = [c for c in conditions if c.source_clause == clause.clause_id
                     and start <= c.evidence.start - clause.span.start < end]
            required = tuple(c.relationship_id for c in local if c.relationship_type != 'exception')
            if kind == 'mandatory' and required:
                kind = 'conditional_obligation'
            action_end = min((c.evidence.start - clause.span.start for c in local
                              if c.evidence.start - clause.span.start > action_start), default=end)
            action = text[action_start:action_end].strip(' \t.;؛')
            if not action and kind == 'right_lapse':
                action = match.group()
            if not action:
                continue
            beneficiary_match = re.search(r'\bfor the benefit of\s+((?:the )?[A-Z][\w ]{1,60})(?=[.;,]|$)|لصالح\s+([^.;؛]{1,80})', sentence)
            beneficiary = (beneficiary_match.group(1) or beneficiary_match.group(2)) if beneficiary_match else None
            trigger = next((c.referenced_condition for c in local if c.relationship_type == 'trigger'), None)
            deadline_ids = tuple(d.date_id for d in dates if d.source_clause == clause.clause_id
                                 and start <= d.evidence.start - clause.span.start < end)
            consequences = tuple(m.group() for m in re.finditer(r'(?i)(?:in default|failing which|في حال الإخلال|في حال الاخلال)[^.;؛]{0,200}', sentence))
            results.append(Obligation(f'O-{len(results)+1:04d}', clause.clause_id, kind, actor, beneficiary,
                                      action, action, trigger, required, deadline_ids,
                                      tuple(c.relationship_id for c in local if c.relationship_type == 'exception'),
                                      consequences, subspan(clause, start, end)))
    return tuple(results)
