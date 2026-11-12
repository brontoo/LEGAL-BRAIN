"""Conservative issue candidates. Differences in scope are not confirmed contradictions."""
import re
from .classification import fold


def detect(clauses, obligations, financial, dates, definitions=()):
    issues = []
    # Exact same actor/action/trigger/exceptions is required before deadline comparison.
    groups = {}
    by_date = {d.date_id: d for d in dates}
    for item in obligations:
        if not item.obligated_party or item.kind not in ('mandatory', 'conditional_obligation'):
            continue
        action = fold(re.split(r'(?i)\bwithin\b|\bno later than\b|خلال', item.action)[0]).strip()
        if not action:
            continue
        # Exceptions and conditions compare source wording, not unrelated generated IDs.
        if item.exceptions or item.conditions and not item.trigger:
            continue
        key = (fold(item.obligated_party), action, fold(item.trigger or ''), item.kind)
        for other in groups.get(key, []):
            a = {(by_date[x].amount, by_date[x].unit, by_date[x].day_basis) for x in item.deadlines if by_date[x].kind == 'relative'}
            b = {(by_date[x].amount, by_date[x].unit, by_date[x].day_basis) for x in other.deadlines if by_date[x].kind == 'relative'}
            if a and b and a != b and item.source_clause != other.source_clause:
                issues.append(('payment_or_performance_deadline', (other.evidence, item.evidence),
                               'Same apparent actor/action/trigger has different periods; scope, amendments and precedence require review.'))
        groups.setdefault(key, []).append(item)
    # Governing-law wording is contractual evidence, never an applicability decision.
    laws = [c for c in clauses if 'governing_law' in c.categories]
    for index, left in enumerate(laws):
        for right in laws[index+1:]:
            scopes = ('difc', 'adgm', 'federal', 'اتحادي', 'دبي', 'ابوظبي', 'أبوظبي', 'الشارقة')
            a = {fold(s) for s in scopes if fold(s) in fold(left.span.quote)}
            b = {fold(s) for s in scopes if fold(s) in fold(right.span.quote)}
            if a and b and a != b:
                issues.append(('governing_law_wording', (left.span, right.span),
                               'Different governing-law wording; separate instruments, language versions or amendments may explain it.'))
    # Same named liability cap in separate clauses, no silent merging of mixed contexts.
    caps = [m for m in financial if m.kind == 'liability_cap']
    for index, left in enumerate(caps):
        for right in caps[index+1:]:
            if left.source_clause != right.source_clause and left.currency == right.currency and left.amount != right.amount:
                # Require identical surrounding language apart from amounts and clause labels.
                def skeleton(term):
                    text = fold(term.context.quote)
                    text = re.sub(r'^\s*(?:clause\s+)?\d+(?:[./]\d+)*[.:]?\s*', '', text)
                    return re.sub(r'\d+(?:[,.]\d+)*', '#', text)
                if skeleton(left) == skeleton(right):
                    issues.append(('liability_cap_wording', (left.context, right.context),
                                   'Matching apparent scope has different cap amounts; review exceptions and version precedence.'))
    for index, left in enumerate(definitions):
        for right in definitions[index+1:]:
            if fold(left.term) == fold(right.term) and fold(left.definition) != fold(right.definition):
                issues.append(('defined_term_wording', (left.evidence, right.evidence),
                               'The same defined term has different wording; scope, language and amendments require review.'))
    notices = []
    for clause in clauses:
        match = re.search(r'(?i)(?:notice address|عنوان الإخطارات|عنوان الاخطارات)\s*[:：]\s*([^\n.;؛]+)', clause.span.quote)
        if match:
            notices.append((match.group(1), clause))
    for index, (address, left) in enumerate(notices):
        for other_address, right in notices[index+1:]:
            if fold(address) != fold(other_address):
                issues.append(('notice_address_wording', (left.span, right.span),
                               'Different notice addresses may concern different parties or a later amendment; confirm addressee and precedence.'))
    return tuple(issues[:100])
