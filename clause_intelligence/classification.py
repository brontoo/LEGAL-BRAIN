"""Auditable bilingual lexical candidates, not enforceability predictions or NLI."""
from dataclasses import replace
import re
import unicodedata


def fold(text):
    text = unicodedata.normalize('NFKC', text).lower()
    text = re.sub(r'[\u064b-\u065f\u0670ـ]', '', text)
    return text.translate(str.maketrans('أإآ٠١٢٣٤٥٦٧٨٩', 'ااا0123456789'))


# Every category has positive lexical cues. Absence is not proof of missing protection.
TAXONOMY = {
    'parties_definitions': ('defined as', 'definitions', 'hereinafter', 'the company', 'التعريفات', 'يقصد ب', 'ويشار إليه'),
    'scope_services': ('scope', 'services', 'نطاق', 'الخدمات'),
    'deliverables': ('deliver', 'report', 'تسليم', 'تقرير'),
    'payment': ('payment', 'pay', 'invoice', 'دفع', 'سداد', 'الفاتورة'),
    'commission_brokerage': ('commission', 'brokerage', 'عمولة', 'الوساطة'),
    'representations_warranties': ('represents', 'warrants', 'warranty', 'يقر', 'يتعهد بصحة'),
    'conditions_precedent': ('subject to', 'provided that', 'شريطة', 'رهنا ب', 'يتوقف علي', 'يتوقف على'),
    'conditions_subsequent': ('ceases upon', 'lapses upon', 'ينتهي عند', 'يسقط حقه'),
    'default_breach': ('breach', 'default', 'اخلال', 'تخلف'),
    'termination': ('terminate', 'termination', 'انهاء', 'فسخ'),
    'renewal': ('renew', 'renewal', 'تجديد', 'يتجدد'),
    'indemnification': ('indemnify', 'indemnity', 'تعويض', 'يعوض'),
    'limitation_liability': ('liability', 'liability cap', 'المسؤولية', 'حد المسؤولية'),
    'confidentiality': ('confidential', 'confidentiality', 'سرية', 'سري', 'افشاء'),
    'intellectual_property': ('intellectual property', 'copyright', 'ملكية فكرية', 'حقوق الملكية'),
    'non_compete': ('non-compete', 'not compete', 'عدم المنافسة', 'لا ينافس'),
    'non_solicitation': ('non-solicitation', 'not solicit', 'عدم الاستقطاب', 'لا يستقطب'),
    'assignment_transfer': ('assign', 'transfer', 'تنازل', 'نقل الملكية'),
    'force_majeure': ('force majeure', 'قوة قاهرة', 'القوة القاهرة'),
    'governing_law': ('governed by', 'governing law', 'القانون الواجب', 'يخضع هذا العقد'),
    'jurisdiction_arbitration': ('jurisdiction', 'arbitration', 'courts', 'اختصاص', 'تحكيم', 'المحاكم'),
    'notices': ('notice', 'notices', 'اشعار', 'اخطار'),
    'remedies': ('remedy', 'remedies', 'injunction', 'سبل الانتصاف', 'حقوق اخرى'),
    'security_guarantees': ('deposit', 'guarantee', 'guarantor', 'تامين', 'ضمان', 'وديعة'),
    'maintenance_repair': ('maintenance', 'repair', 'صيانة', 'اصلاح'),
    'corporate_authority': ('approval', 'authorized signatory', 'board', 'موافقة', 'مجلس الادارة', 'المفوض بالتوقيع'),
    'other': (),
}


def contains(text, cue):
    prefix = r'(?:[وف]?[بل]?(?:ال)?)?' if re.search(r'[\u0600-\u06ff]', cue) else ''
    return re.search(r'(?<!\w)' + prefix + re.escape(fold(cue)) + r'(?!\w)', fold(text)) is not None


def classify(clauses):
    results = []
    for clause in clauses:
        categories = [k for k, cues in TAXONOMY.items() if any(contains(clause.span.quote, cue) for cue in cues)]
        if re.search(r'\(\s*the\s+[A-Za-z ]{2,40}\)', clause.span.quote, re.I) and 'parties_definitions' not in categories:
            categories.insert(0, 'parties_definitions')
        results.append(replace(clause, categories=tuple(categories) or ('other',)))
    return tuple(results)
