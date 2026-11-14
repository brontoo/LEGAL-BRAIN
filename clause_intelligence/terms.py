"""Financial mentions and date expressions; amounts never establish a debt or exposure."""
import re
from datetime import date
from .schemas import FinancialTerm, DateTerm, ClauseError
from .evidence import subspan
from .classification import fold, contains
from .segmentation import DIGITS

AMOUNT = r'\d+(?:[,٬]\d{3})*(?:[.٫]\d+)?'
CURRENCY = r'(?:AED|USD|EUR|GBP|د\.?إ\.?|درهم(?:اً|ا)?|دولار)'
MONEY = re.compile(r'(?<!\w)(?:(?P<c1>' + CURRENCY + r')\s*(?P<a1>' + AMOUNT + r')|(?P<a2>' + AMOUNT + r')\s*(?P<c2>' + CURRENCY + r'|%|٪|بالمائة|بالمئة))(?!\w)', re.I)
FINANCIAL_KINDS = {
    'liability_cap': ('liability cap', 'cap on liability', 'حد المسؤولية'),
    'penalty': ('penalty', 'penalties', 'غرامة', 'جزاء'),
    'deposit': ('deposit', 'وديعة', 'تأمين', 'تامين'),
    'advance': ('advance', 'مقدم', 'دفعة مقدمة'),
    'commission': ('commission', 'عمولة'),
    'installment': ('installment', 'instalment', 'قسط'),
    'refund': ('refund', 'رد المبلغ', 'استرداد'),
    'deduction': ('deduction', 'خصم'),
    'interest': ('interest', 'فائدة', 'فوائد'),
    'vat': ('VAT', 'ضريبة القيمة المضافة'),
    'reimbursement': ('reimburse', 'reimbursement', 'رد المصروفات'),
    'contract_price': ('total price', 'contract price', 'السعر الاجمالي', 'الثمن الاجمالي', 'قيمة العقد'),
}
WORDS = {'one': 1, 'two': 2, 'five': 5, 'ten': 10, 'fifteen': 15, 'thirty': 30, 'sixty': 60,
         'خمسة عشر': 15, 'ثلاثين': 30, 'ثلاثون': 30, 'خمسة': 5, 'عشرة': 10, 'ستين': 60, 'ستون': 60}
RELATIVE = re.compile(r'(?<!\w)(?P<amount>\d{1,4}|' + '|'.join(sorted(WORDS, key=len, reverse=True)) +
                      r')\s+(?P<unit>working days?|business days?|calendar days?|days?|weeks?|months?|years?|يوم عمل|أيام عمل|ايام عمل|يوماً? تقويمياً?|يوم(?:اً|ا)?|أيام|ايام|أسبوع|اسبوع|أسابيع|اسابيع|أشهر|اشهر|شهر|سنوات|سنة)(?!\w)', re.I)
ABSOLUTE = re.compile(r'(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})(?!\d)')


def sentence_bounds(text, start, end):
    # Do not split decimal numbers into separate contexts.
    left = list(re.finditer(r'[;؛\n]|[.!?](?=\s|$)', text[:start]))
    right = re.search(r'[;؛\n]|[.!?](?=\s|$)', text[end:])
    return (left[-1].end() if left else 0, end + right.end() if right else len(text))


def financial(clauses):
    results = []
    for clause in clauses:
        for match in MONEY.finditer(clause.span.quote):
            start, end = sentence_bounds(clause.span.quote, match.start(), match.end())
            context = subspan(clause, start, end)
            kinds = [k for k, cues in FINANCIAL_KINDS.items() if any(contains(context.quote, cue) for cue in cues)]
            # More than one type in a sentence is ambiguous, never copy one label onto every amount.
            kind = kinds[0] if len(kinds) == 1 else 'ambiguous_financial_context' if kinds else 'amount_mention'
            currency = match.group('c1') or match.group('c2')
            if currency.lower() in ('aed', 'درهم', 'درهما', 'درهماً', 'د.إ', 'دإ', 'د.إ.'):
                currency = 'AED'
            elif currency.upper() in ('USD', 'EUR', 'GBP'):
                currency = currency.upper()
            elif currency in ('%', '٪', 'بالمائة', 'بالمئة'):
                currency = 'percent'
            else:
                currency = 'USD_unspecified_dollar' if currency == 'دولار' else None
            amount = (match.group('a1') or match.group('a2')).translate(DIGITS).replace(',', '').replace('٬', '').replace('٫', '.')
            results.append(FinancialTerm(f'M-{len(results)+1:04d}', clause.clause_id, amount, currency,
                                         kind, subspan(clause, match.start(), match.end()), context))
    return tuple(results)


def dates(clauses, conditions):
    results = []
    for clause in clauses:
        text = clause.span.quote
        for match in ABSOLUTE.finditer(text):
            normalized = match.group().translate(DIGITS)
            resolved = None
            if '-' in normalized:
                try:
                    resolved = date.fromisoformat(normalized).isoformat()
                except ValueError:
                    pass
            results.append(DateTerm(f'D-{len(results)+1:04d}', clause.clause_id, 'absolute', match.group(),
                                    subspan(clause, match.start(), match.end()), resolved_date=resolved,
                                    status='explicit_date_mention' if resolved else 'ambiguous_date'))
        for match in RELATIVE.finditer(text):
            raw = match.group('amount').translate(DIGITS).lower()
            amount = int(raw) if raw.isdigit() else WORDS.get(raw)
            unit = fold(match.group('unit'))
            basis = 'working' if 'working' in unit or 'business' in unit or 'عمل' in unit else 'calendar' if 'calendar' in unit or 'تقويم' in unit else 'unknown'
            canonical = 'months' if 'month' in unit or 'شهر' in unit or 'اشهر' in unit else 'years' if 'year' in unit or 'سنة' in unit or 'سنوات' in unit else 'weeks' if 'week' in unit or 'سبوع' in unit or 'سابيع' in unit else 'days'
            start, end = sentence_bounds(text, match.start(), match.end())
            trigger = next((c.referenced_condition for c in conditions if c.source_clause == clause.clause_id
                            and c.relationship_type == 'trigger' and start <= c.evidence.start - clause.span.start < end), None)
            results.append(DateTerm(f'D-{len(results)+1:04d}', clause.clause_id, 'relative', match.group(),
                                    subspan(clause, match.start(), match.end()), amount, canonical, basis, trigger))
    from dataclasses import replace
    contexts = {'effective': ('effective', 'تاريخ النفاذ'), 'commencement': ('commencement', 'يبدأ', 'بدء'),
                'expiry': ('expiry', 'expires', 'الانتهاء', 'ينتهي'), 'renewal': ('renew', 'renewal', 'تجديد', 'يتجدد'),
                'notice': ('notice', 'اشعار', 'اخطار'), 'cure': ('cure', 'تصحيح', 'تدارك'),
                'payment': ('pay', 'payment', 'سداد', 'دفع'), 'delivery': ('deliver', 'تسليم')}
    by_id = {c.clause_id: c for c in clauses}
    contextual = []
    for item in results:
        clause = by_id[item.source_clause]
        start, end = sentence_bounds(clause.span.quote, item.evidence.start-clause.span.start, item.evidence.end-clause.span.start)
        text = clause.span.quote[start:end]
        matches = [k for k, cues in contexts.items() if any(contains(text, cue) for cue in cues)]
        contextual.append(replace(item, contractual_context=matches[0] if len(matches) == 1 else 'ambiguous' if matches else 'unspecified'))
    return tuple(contextual)


def calculate_deadline(term, anchor, convention, holidays=None):
    """Explicit caller-only adapter. The API never guesses an anchor or counting convention."""
    from deadlines import add_period, Unit, Convention, DayCount
    if not isinstance(anchor, date) or not isinstance(convention, Convention) or term.amount is None or term.kind != 'relative':
        raise ClauseError('A confirmed trigger date and explicit convention are required')
    if term.day_basis == 'working' and convention.unit_basis != DayCount.WORKING:
        raise ClauseError('Working-day expression requires a working-day convention')
    if term.day_basis == 'calendar' and convention.unit_basis != DayCount.CALENDAR:
        raise ClauseError('Calendar expression requires a calendar convention')
    return add_period(anchor, term.amount, Unit(term.unit), convention, holidays)
