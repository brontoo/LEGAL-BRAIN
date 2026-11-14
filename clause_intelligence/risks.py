"""Issue register, not estimated likelihood, severity, liability or approval."""
from .schemas import Finding, SupportStatus as S
from skills.risk import RiskMatrix


def register(clauses, entities, references, cycles, duplicate_labels, conflicts, language):
    findings = []
    def add(category, text, evidence, basis, missing=(), status=S.AMBIGUOUS):
        if language == 'ar':
            text = {'evidence_gap': 'المحتوى المشار إليه غير متاح أو ملتبس.',
                    'duplicate_numbering': 'ترقيم تعاقدي مكرر يتطلب المراجعة.',
                    'circular_reference': 'إحالات داخلية دائرية تتطلب مراجعة السياق.',
                    'ambiguous_party_alias': 'الاسم المعرف يشير إلى أكثر من طرف.',
                    'potential_conflict': 'تعارض محتمل يتطلب مراجعة النطاق والشروط وترتيب الأولوية.',
                    'legal_review_question': 'الأثر القانوني يتطلب سنداً منطبقاً ومراجعة مهنية.'}.get(category, text)
            basis = {'evidence_gap': 'فحص بنيوي للإحالة الداخلية؛ لا يتم اختلاق النص الناقص.',
                     'duplicate_numbering': 'تكرر رقم البند في المصدر؛ لا يحدد الفحص أي نسخة لها الأولوية.',
                     'circular_reference': 'توجد دورة في الإحالات؛ الأثر القانوني غير محسوم.',
                     'ambiguous_party_alias': 'تعارض في تعريف الأطراف؛ تظل نسبة الالتزام ملتبسة.',
                     'potential_conflict': 'توجد عبارات تبدو مختلفة؛ قد تفسرها شروط أو نطاقات أو تعديلات مختلفة.',
                     'legal_review_question': 'التصنيف موضوع للمراجعة وليس إثباتاً للبطلان أو للمخاطر.'}.get(category, basis)
        findings.append(Finding(f'ISSUE-{len(findings)+1:04d}', category, text, 'uncertain_inference', tuple(evidence),
                                status.value, basis, missing_information=tuple(missing)))
    for ref in references:
        if ref.status != 'resolved':
            add('evidence_gap', 'Referenced content is unavailable or ambiguous.' if language != 'ar' else 'المحتوى المشار إليه غير متاح أو ملتبس.',
                (ref.evidence,), 'Internal reference lookup: ' + ref.status, (ref.target_label,), S.INSUFFICIENT)
    for label, ids in duplicate_labels.items():
        add('duplicate_numbering', 'Repeated contractual label requires review.',
            [c.span for c in clauses if c.clause_id in ids], 'Repeated label: ' + label)
    if cycles:
        add('circular_reference', 'Circular internal references require contextual review.',
            [c.span for c in clauses if c.clause_id in cycles], 'Directed reference graph contains a cycle; legal effect is not determined.')
    for entity in entities:
        if entity.ambiguity:
            add('ambiguous_party_alias', 'A defined alias identifies multiple parties.', (entity.evidence,),
                'Explicit alias collision; party attribution must remain unresolved.')
    for category, evidence, basis in conflicts:
        add('potential_conflict', 'Potential conflict in ' + category.replace('_', ' ') + '.', evidence, basis)
    if language == 'bilingual':
        add('language_equivalence_unverified', 'Language versions have not been verified as equivalent.', (),
            'No automatic bilingual equivalence or language-precedence decision is performed.', ('language_precedence_and_comparison',), S.NOT_ASSESSED)
    for clause in clauses:
        sensitive = set(clause.categories) & {'commission_brokerage', 'non_compete', 'limitation_liability', 'corporate_authority'}
        if sensitive:
            add('legal_review_question', 'Legal effect requires applicable authority and professional review.', (clause.span,),
                'Category is a review prompt, not proof of risk or invalidity.', ('verified_applicable_authority',), S.LEGAL)
    return tuple(findings), RiskMatrix().assess(None, None)
