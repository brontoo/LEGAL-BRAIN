"""Reuse existing extraction/counting contracts; extend bounded word-number coverage."""
import re
from . import terms
from .schemas import DateTerm
from .evidence import subspan
from .role_text import TextView

NUMBERS = {'twenty': 20, 'forty': 40, 'ninety': 90, 'عشرين': 20, 'اربعين': 40, 'تسعين': 90}
EXTRA_PERIOD = re.compile(r'(?<!\w)(?P<number>'+'|'.join(NUMBERS)+r')\s+(?P<unit>(?:(?:business|working|calendar)\s+)?days?|يوم عمل|ايام عمل|يوما|يوم|ايام)(?!\w)')


def dates(clauses, conditions):
    result = list(terms.dates(clauses, conditions))
    for clause in clauses:
        view = TextView.of(clause.span.quote)
        for match in EXTRA_PERIOD.finditer(view.text):
            span = view.span(clause, match.start(), match.end())
            if any(d.evidence.start == span.start and d.evidence.end == span.end for d in result):
                continue
            expression = match.group('unit')
            basis = 'working' if 'business' in expression or 'working' in expression or 'عمل' in expression else 'calendar' if 'calendar' in expression else 'unknown'
            result.append(DateTerm(f'D-{len(result)+1:04d}', clause.clause_id, 'relative', span.quote, span,
                                   NUMBERS[match.group('number')], 'days', basis))
    return tuple(result)
