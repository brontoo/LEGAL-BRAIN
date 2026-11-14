"""Internal reference resolution and bounded iterative dependency-cycle detection."""
import re
from .segmentation import NUMBER, ORDINALS, canonical_label
from .schemas import CrossReference
from .evidence import subspan

REFERENCE = re.compile(r'(?P<kind>Clauses?|Articles?|Schedules?|Annex|Appendix|للبند|للمادة|للملحق|البند|المادة|الملحق|ملحق)\s+(?P<label>' +
                       NUMBER + '|' + '|'.join(ORDINALS) + r'|[A-Zأ-ي])(?=\s|[.,،;:؛)]|$)', re.I)


def resolve(clauses):
    labels = {}
    for clause in clauses:
        if clause.label:
            labels.setdefault(clause.label, []).append(clause.clause_id)
    result = []
    for clause in clauses:
        for match in REFERENCE.finditer(clause.span.quote):
            # A heading is a definition, not a self-reference.
            if not clause.span.quote[:match.start()].strip():
                continue
            label = canonical_label(match.group('label'))
            schedule = match.group('kind').lower() in ('schedule', 'schedules', 'annex', 'appendix', 'الملحق', 'للملحق', 'ملحق')
            if schedule:
                label = 'schedule:' + label
            targets = tuple(labels.get(label, ()))
            status = 'resolved' if len(targets) == 1 else 'ambiguous' if targets else 'unavailable_schedule' if schedule else 'missing_clause'
            result.append(CrossReference(f'R-{len(result)+1:04d}', clause.clause_id, label, targets, status,
                                         subspan(clause, match.start(), match.end())))
    graph = {c.clause_id: set() for c in clauses}
    for ref in result:
        graph[ref.source_clause].update(ref.target_clauses)
    cycles = set()
    for start in graph:
        queue = list(graph[start])
        seen = set()
        while queue:
            node = queue.pop()
            if node == start:
                cycles.add(start)
                break
            if node not in seen:
                seen.add(node)
                queue.extend(graph[node] - seen)
    return tuple(result), tuple(sorted(cycles)), {label: tuple(ids) for label, ids in labels.items() if len(ids) > 1}
