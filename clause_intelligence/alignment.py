"""Marker-driven bilingual comparison, never inferred translation or precedence."""
from collections import defaultdict
import re
from .role_text import TextView

MARKER = re.compile(r'\b(?P<language>AR|EN)\s+version\s+(?:Clause|Article)\s+(?P<label>\d+(?:[./]\d+)*)\s*:', re.I)


def compare(clauses, obligations, financial, dates):
    groups = defaultdict(lambda: defaultdict(list))
    for clause in clauses:
        match = MARKER.search(clause.span.quote)
        if match:
            groups[match.group('label')][match.group('language').upper()].append(clause)
    alignments = []
    for label, versions in sorted(groups.items()):
        if len(versions['AR']) != 1 or len(versions['EN']) != 1:
            alignments.append({'label': label, 'status': 'alignment_uncertain',
                               'evidence': [c.span for values in versions.values() for c in values],
                               'reason': 'Missing or repeated explicit language marker; no inferred pairing.'})
            continue
        left, right = versions['AR'][0], versions['EN'][0]
        def values(clause):
            duties = [o for o in obligations if o.source_clause == clause.clause_id]
            return {'modality': sorted({o.semantic_role.modality for o in duties}),
                    'polarity': sorted({o.semantic_role.polarity for o in duties}),
                    'amount': sorted({(m.currency or 'unknown', m.amount) for m in financial if m.source_clause == clause.clause_id}),
                    'deadline': sorted({(d.amount or 0, d.unit or 'unknown', d.day_basis) for d in dates if d.source_clause == clause.clause_id})}
        a, b = values(left), values(right)
        differences = [key for key in a if a[key] and b[key] and a[key] != b[key]]
        # Explicit oral-vs-written contrasts are lexical divergence candidates only.
        text = TextView.of(left.span.quote+' '+right.span.quote).text
        if ('oral' in text and 'كتابة' in text) or ('written' in text and 'شفوي' in text):
            differences.append('notice_form')
        alignments.append({'label': label, 'status': 'divergence_candidate' if differences else 'equivalence_not_established',
                           'dimensions': differences, 'evidence': (left.span, right.span),
                           'basis': 'Explicit same-number AR/EN markers only; neither language is selected as prevailing.',
                           'human_review_required': True})
    return tuple(alignments)
