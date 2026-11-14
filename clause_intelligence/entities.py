"""Explicit party definitions only. Names/aliases are source text, not capacity checks."""
from dataclasses import replace
import re
from .evidence import subspan
from .classification import fold
from .schemas import Entity, DefinedTerm

ROLE_WORDS = ('supplier', 'service provider', 'company', 'client', 'buyer', 'seller', 'landlord', 'tenant',
              'employer', 'employee', 'principal', 'agent', 'licensor', 'licensee', 'disclosing party',
              'receiving party', 'assignor', 'assignee', 'guarantor', 'authorized signatory',
              'الطرف الأول', 'الطرف الاول', 'الطرف الثاني', 'الشركة', 'العميل', 'المورد', 'المشتري',
              'البائع', 'المؤجر', 'المستأجر', 'الوكيل', 'الموكل', 'الضامن', 'المفوض بالتوقيع')
ROLES = '|'.join(sorted((re.escape(r) for r in ROLE_WORDS), key=len, reverse=True))
DEFINITION = re.compile(r'(?P<name>[^\n;؛:()]{2,160}?)\s*\(\s*(?:(?:the|hereinafter(?: the)?)\s+|(?:ويشار إليه ب[ـ]?|ويشار اليه ب[ـ]?|بصفته)\s*)?["“«]?(?P<alias>' + ROLES + r')["”»]?\s*\)', re.I)
ROLE_NAME = re.compile(r'(?<!\w)(?P<alias>' + ROLES + r')\s*[:：]\s*(?P<name>[^\n;؛()]{2,160})', re.I)


def extract(clauses):
    entities = []
    for clause in clauses:
        for pattern in (DEFINITION, ROLE_NAME):
            for match in pattern.finditer(clause.span.quote):
                raw = match.group('name')
                # Remove heading/introduction, without changing the matched name characters.
                lead = re.search(r'(?i)(?:between|and|بين|و)\s+(.+)$', raw)
                name = (lead.group(1) if lead else raw).strip(' \t.,،')
                name = re.sub(r'^\d+(?:[./]\d+)*[.:]?\s+', '', name)
                if not name:
                    continue
                alias = match.group('alias')
                span = subspan(clause, match.start(), match.end())
                person = 'legal_person_indicator' if re.search(r'(?i)\b(?:LLC|Ltd|Limited|Inc)\b|ذ\.م\.م|شركة', name) else 'unknown'
                if not any(e.name == name and fold(e.role) == fold(alias) for e in entities):
                    entities.append(Entity(f'E-{len(entities)+1:04d}', name, (alias,), alias, person, span))
    return tuple(replace(e, ambiguity=any(fold(a) == fold(b) and other.name != e.name
                                         for other in entities for a in e.aliases for b in other.aliases))
                 for e in entities)


def resolve_role(text, entities):
    cleaned = fold(text.strip(' \t.,،:'))
    exact = [e for e in entities if cleaned in (fold(e.name), *(fold(a) for a in e.aliases),
                                               *('the ' + fold(a) for a in e.aliases))]
    if len(exact) == 1 and not exact[0].ambiguity:
        return exact[0].name
    return None


def defined_terms(clauses):
    pattern = re.compile(r'["“«](?P<term>[^"”»\n]{1,80})["”»]\s+(?:means|shall mean|يعني|يقصد به)\s+(?P<definition>[^\n;؛]{1,500})', re.I)
    result = []
    for clause in clauses:
        for match in pattern.finditer(clause.span.quote):
            result.append(DefinedTerm(f'TERM-{len(result)+1:04d}', match.group('term'), match.group('definition'),
                                      subspan(clause, match.start(), match.end())))
    return tuple(result)
