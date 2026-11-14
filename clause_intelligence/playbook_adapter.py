"""Reuse bundled methodology and risk logic. A playbook is never evidence."""
from dataclasses import asdict
from skills import integration
from skills.schemas import SkillError
from .schemas import ClauseError

SUPPORTED = ('uae-contract-review', 'uae-nda-review', 'uae-legal-risk',
             'uae-contract-negotiation', 'uae-corporate-due-diligence')


def adapt(request, clauses, obligations, findings):
    if request.playbook is None:
        return {'status': 'not_requested', 'methodology_is_legal_authority': False}
    if request.playbook not in SUPPORTED:
        raise ClauseError('Unsupported clause analysis playbook')
    if not integration.enabled():
        return {'status': 'disabled', 'methodology_is_legal_authority': False}
    try:
        result, _ = integration.activate('Review supplied contractual provisions', skill_id=request.playbook,
                                        jurisdiction=asdict(request.jurisdiction))
        skill = integration.bundled_registry().get(request.playbook)
    except SkillError:
        raise ClauseError('Playbook incompatible with supplied jurisdiction') from None
    focus = {'uae-nda-review': {'confidentiality', 'intellectual_property', 'non_compete', 'non_solicitation', 'remedies'},
             'uae-corporate-due-diligence': {'corporate_authority', 'assignment_transfer', 'representations_warranties'}}.get(request.playbook)
    selected = [c for c in clauses if focus is None or set(c.categories) & focus]
    from skills.risk import assess_supplied_risk
    proposals = []
    if request.playbook == 'uae-contract-negotiation':
        for finding in findings:
            if finding.category not in ('evidence_gap', 'potential_conflict'):
                continue
            arabic = request.language == 'ar'
            if finding.category == 'evidence_gap':
                preferred = ('لا يسري الالتزام المرتبط بالملحق إلى حين تحديد الملحق وإرفاقه واعتماده كتابة من الطرفين.' if arabic else
                             'The obligation referring to the attachment takes effect only after the attachment is identified, attached and approved in writing by both parties.')
                fallback = ('يؤكد الطرفان كتابة محتوى الملحق المشار إليه قبل تنفيذ الالتزام المرتبط به.' if arabic else
                            'The parties will confirm the contents of the referenced attachment in writing before performing the related obligation.')
            else:
                preferred = ('يتفق الطرفان كتابة على حكم موحد يحل محل الأحكام المتعارضة المحددة في هذا التقرير.' if arabic else
                             'The parties will agree in writing on one provision replacing the conflicting provisions identified in this report.')
                fallback = ('يتفق الطرفان كتابة على ترتيب أولوية الأحكام المحددة في هذا التقرير.' if arabic else
                            'The parties will agree in writing on the order of precedence of the provisions identified in this report.')
            proposals.append({'issue_id': finding.finding_id, 'source_clause_ids': [s.clause_id for s in finding.evidence],
                              'preferred_proposal': preferred, 'fallback_proposal': fallback,
                              'status': 'unagreed_illustrative_draft', 'client_position': request.client_role,
                              'required_review': 'Lawyer must tailor scope, commercial position and exact clause references before use.'})
    return {'status': result.status, 'skill_id': request.playbook, 'version': skill.manifest.version,
            'methodology_is_legal_authority': False, 'required_information': skill.manifest.required_inputs,
            'output_sections': skill.manifest.output_contract.sections,
            'clause_ids': [c.clause_id for c in selected],
            'obligation_ids': [o.obligation_id for o in obligations if o.source_clause in {c.clause_id for c in selected}],
            'issue_ids': [f.finding_id for f in findings if f.claim_type != 'source_observation'],
            'risk_assessment': assess_supplied_risk(None) if request.playbook == 'uae-legal-risk' else None,
            'negotiation_status': 'proposals_require_separate_draft_and_approval' if request.playbook == 'uae-contract-negotiation' else None,
            'proposed_amendments': proposals,
            'human_review_required': True}
