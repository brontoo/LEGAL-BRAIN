"""Advisory content-label checks, not a legal or semantic approval mechanism."""
from .router import matches, normalize

# Conservative bilingual aliases. A missing label can mean different wording;
# an observed label does not prove its section is correct or complete.
ALIASES = {
    'scope_and_gaps': ('scope and gaps', 'scope', 'النطاق', 'نواقص'),
    'jurisdiction': ('jurisdiction', 'governing law', 'الاختصاص', 'القانون الحاكم'),
    'clause_findings': ('clause findings', 'clause analysis', 'تحليل البنود', 'ملاحظات البنود'),
    'priority_actions': ('priority actions', 'priorities', 'الاولويات', 'الاجراءات'),
    'human_review': ('human review', 'lawyer review', 'مراجعة المحامي', 'مراجعة بشرية'),
    'nda_findings': ('nda findings', 'confidentiality findings', 'تحليل السرية', 'نتائج السرية'),
    'workflow_classification': ('workflow classification', 'green', 'yellow', 'red', 'تصنيف المخاطر', 'تصنيف سير العمل'),
    'risk_register': ('risk register', 'سجل المخاطر'),
    'mitigation_plan': ('mitigation plan', 'خطة التخفيف', 'خطة المعالجة'),
    'negotiation_brief': ('negotiation brief', 'موجز التفاوض'),
    'clause_comparison': ('clause comparison', 'مقارنة البنود'),
    'proposed_amendments': ('proposed amendments', 'التعديلات المقترحة'),
    'counterproposal_notes': ('counterproposal notes', 'المقترح المقابل'),
    'legal_checklist': ('legal checklist', 'قائمة الفحص القانوني', 'قائمة التحقق'),
    'transaction_risks': ('transaction risks', 'مخاطر الصفقة'),
    'evidence_gap_report': ('evidence gap', 'missing documents', 'نواقص الادلة', 'المستندات الناقصة'),
}


def diagnose_output(text: str, manifest) -> dict:
    """Return metadata only; never repeat output, fabricate findings or edit text."""
    normalized = normalize(text)
    observed, missing = [], []
    for section in manifest.output_contract.sections:
        terms = (section, section.replace('_', ' '), *ALIASES.get(section, ()))
        # Word boundaries matter: e.g. "red" is not present inside "required".
        found = any(matches(term, normalized) for term in terms)
        (observed if found else missing).append(section)
    return {
        'skill_id': manifest.skill_id,
        'version': manifest.version,
        'status': 'labels_observed' if not missing else 'labels_missing',
        'observed_sections': observed,
        'missing_sections': missing,
        'advisory_only': True,
        'legal_quality': 'not_assessed',
        'human_review_required': True,
    }
