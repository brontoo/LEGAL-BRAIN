"""Explicit condition/exception phrases. Fulfilment is always unknown from wording alone."""
import re
from .schemas import Condition
from .evidence import subspan

MARKERS = {
    'exception': r'\bunless\b|\bexcept(?: as)?\b|ما لم|باستثناء|دون الإخلال|دون الاخلال',
    'condition': r'\bsubject to\b|\bprovided that\b|\bon condition that\b|شريطة أن|شريطة ان|رهناً ب|رهنا ب',
    'trigger': r'\bafter\b|\bfollowing\b|\bupon\b|\bin the event of\b|بعد|عند|في حال|بشرط',
    'consent_dependency': r'\bprior written consent\b|موافقة خطية مسبقة|موافقة كتابية مسبقة',
}


def extract(clauses, entities=()):
    results = []
    for clause in clauses:
        for kind, pattern in MARKERS.items():
            for match in re.finditer('(?:' + pattern + r')[^\n.;؛]{0,500}', clause.span.quote, re.I):
                quote = match.group()
                parties = tuple(e.name for e in entities if any(a in quote for a in e.aliases))
                results.append(Condition(f'COND-{len(results)+1:04d}', clause.clause_id, kind, quote,
                                         parties, subspan(clause, match.start(), match.end())))
    return tuple(results)
