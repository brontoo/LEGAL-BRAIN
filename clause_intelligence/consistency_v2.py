"""Budgeted comparisons of evidenced scopes. No automatic amendment resolution."""
from collections import defaultdict
import re
from .role_text import clean_party, TextView

MAX_COMPARISONS = 5000
MAX_ISSUES = 100


def detect(clauses, obligations, financial, dates, definitions):
    issues, groups = [], defaultdict(list)
    comparisons = 0
    by_date = {d.date_id: d for d in dates}
    qualifications = any(re.search(r'amendment|supersed|prevail|تعديل|يسود|الاولوية', TextView.of(c.span.quote).text) for c in clauses)
    def add(category, left, right, basis):
        if len(issues) < MAX_ISSUES:
            issues.append((category, (left, right), basis))
    for item in obligations:
        role = item.semantic_role
        if (role.actor.status not in ('explicit', 'from_definition') or role.action.value is None
                or role.modality != 'mandatory' or role.exception_ids or role.condition_ids):
            continue
        scope = TextView.of(item.evidence.quote).text
        # Explicit stage/schedule scope is not silently discarded in the key.
        scope_markers = tuple(re.findall(r'(?:stage|phase|schedule|المرحلة|ملحق)\s+[\w-]{1,30}', scope))
        key = (clean_party(role.actor.value), role.action.value, TextView.of(role.object.value or '').text,
               TextView.of(item.trigger or '').text, scope_markers)
        current = {(by_date[d].amount, by_date[d].unit, by_date[d].day_basis) for d in role.deadline_ids if d in by_date}
        for previous, period in groups[key]:
            comparisons += 1
            if comparisons > MAX_COMPARISONS:
                break
            if current and period and current != period and item.source_clause != previous.source_clause and not qualifications:
                add('performance_deadline', previous.evidence, item.evidence,
                    'Matching evidenced actor/action/object/trigger has different periods; legal effect remains unassessed.')
        if comparisons > MAX_COMPARISONS:
            break
        groups[key].append((item, current))
    cap_groups = defaultdict(list)
    for term in financial:
        if term.kind != 'liability_cap':
            continue
        context = TextView.of(term.context.quote).text
        context = re.sub(r'^\s*\d+(?:[./]\d+)*[.:]?\s*', '', context)
        key = (term.currency, re.sub(r'\d+(?:[,.٬٫]\d+)*', '#', context))
        for previous in cap_groups[key]:
            comparisons += 1
            if comparisons > MAX_COMPARISONS:
                break
            if term.amount != previous.amount and not qualifications:
                add('liability_cap', previous.context, term.context, 'Same apparent cap scope/currency has different amounts; review required.')
        cap_groups[key].append(term)
    term_groups = defaultdict(list)
    for term in definitions:
        for other in term_groups[clean_party(term.term)]:
            comparisons += 1
            if comparisons > MAX_COMPARISONS:
                break
            if TextView.of(term.definition).text != TextView.of(other.definition).text and not qualifications:
                add('definition_wording', other.evidence, term.evidence, 'Same defined term differs; context and language need review.')
        term_groups[clean_party(term.term)].append(term)
    laws = [c for c in clauses if 'governing_law' in c.categories]
    for index, left in enumerate(laws):
        for right in laws[index+1:]:
            comparisons += 1
            if comparisons > MAX_COMPARISONS:
                break
            def scope(c):
                text = TextView.of(c.span.quote).text
                return {w for w in ('adgm', 'difc', 'federal', 'اتحادي', 'دبي', 'الشارقة', 'ابوظبي') if w in text}
            if scope(left) and scope(right) and scope(left) != scope(right) and not qualifications:
                add('governing_law_wording', left.span, right.span, 'Different law wording, without selecting applicable law or clause precedence.')
    return tuple(issues), {'comparison_budget_exhausted': comparisons > MAX_COMPARISONS,
                          'issue_budget_reached': len(issues) >= MAX_ISSUES,
                          'amendment_or_precedence_review_required': qualifications,
                          'comparisons': min(comparisons, MAX_COMPARISONS)}
