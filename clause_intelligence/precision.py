"""Opt-in targeted corrections; no gold labels or document-specific answer rules."""
from dataclasses import dataclass,field,replace
import re
from .identity import Identity,resolve
from .role_contracts import SemanticRole,RoleValue
from .role_text import TextView


@dataclass(frozen=True)
class ActionValue(RoleValue):
    alternatives: tuple[str,...]=()
    resolution_basis: str='lexical_candidate'


@dataclass(frozen=True)
class PreciseRole(SemanticRole):
    actor_identity: Identity=field(default_factory=Identity)
    beneficiary_identity: Identity=field(default_factory=Identity)
    recipient: RoleValue=field(default_factory=RoleValue)
    destination: RoleValue=field(default_factory=RoleValue)
    scope_qualifier: RoleValue=field(default_factory=RoleValue)
    boundary_status: str='not_assessed'


def arabic_action(role,document,duty):
    if not role.action.evidence or TextView.of(role.action.evidence[0].quote).text.strip() not in ('رد','الرد'):
        return role.action
    context=TextView.of(role.object.value or '').text
    tail=TextView.of(document.text[role.action.evidence[0].end:duty.evidence.end]).text.strip()
    expense=bool(re.search(r'(?<!\w)و?(?:ال)?(?:مصروفات|نفقات|تكاليف|مصاريف)(?!\w)',context))
    request=bool(re.search(r'(?<!\w)و?(?:ال)?(?:طلب|طلبات|عرض|عروض|التماس)(?!\w)',context))
    physical=bool(re.search(r'(?<!\w)و?(?:ال)?(?:جواز|جوازات|مستندات|وثائق|اصول|معدات|كتب)(?!\w)',context))
    if re.match(r'(?:على|علي)\s+',tail):
        action,basis='respond','explicit_response_preposition'
    elif sum((expense,request,physical))>1:
        return ActionValue(None,role.action.evidence,'ambiguous',('return','reimburse','reject'),'conflicting_object_classes')
    elif expense:
        action,basis='reimburse','expense_object_class'
    elif request:
        action,basis='reject','request_or_offer_object_class'
    elif physical:
        action,basis='return','physical_record_object_class'
    else:
        return ActionValue(None,role.action.evidence,'ambiguous',('return','refund','reimburse','reject','respond'),'insufficient_disambiguating_context')
    return ActionValue(action,role.action.evidence,'contextual_candidate',(action,),basis)


def boundaries(role,clause):
    obj=role.object
    recipient=RoleValue()
    destination=RoleValue()
    qualifier=RoleValue()
    if role.beneficiary.evidence:
        recipient=RoleValue(role.beneficiary.evidence[0].quote,(role.beneficiary.evidence[0],),'explicit_recipient_candidate')
    if not obj.evidence or role.action.value not in ('disclose','deliver','provide','return','transfer','notify'):
        return obj,recipient,destination,qualifier,'not_applicable_or_unknown'
    span=obj.evidence[0]
    view=TextView.of(clause.span.quote)
    from bisect import bisect_left
    start=bisect_left(view.positions,span.start-clause.span.start)
    end=bisect_left(view.positions,span.end-clause.span.start)
    matches=list(re.finditer(r'(?<!\w)(?:to|into|الى|الي)\s+',view.text[start:end]))
    if not matches:
        return obj,recipient,destination,qualifier,'no_explicit_recipient_boundary'
    first=matches[0]
    boundary=start+first.start()
    target_start=start+first.end()
    tail=view.text[target_start:end]
    # Infinitives and repeated "to" are ambiguous, not a confident recipient.
    if len(matches)>1 or re.match(r'(?:retain|perform|disclose|pay|provide|be)\b',tail):
        return replace(obj,status='ambiguous'),recipient,destination,qualifier,'ambiguous_prepositional_attachment'
    scope=re.search(r'\s+(?:for|at|during|لاغراض|بغرض|اثناء)\s+',tail)
    target_end=target_start+scope.start() if scope else end
    while boundary>start and view.text[boundary-1].isspace():boundary-=1
    if boundary<=start or target_start>=target_end:
        return obj,recipient,destination,qualifier,'ambiguous_prepositional_attachment'
    direct=view.span(clause,start,boundary)
    target=view.span(clause,target_start,target_end)
    value=RoleValue(target.quote,(target,),'explicit_recipient_candidate')
    if re.match(r'(?:the\s+)?(?:archive|portal|site|office|warehouse)\b|(?:الارشيف|المستودع|الموقع|البوابة)',tail):
        destination=replace(value,status='destination_candidate')
    else:
        recipient=value
    if scope:
        q=view.span(clause,target_start+scope.start(),end)
        qualifier=RoleValue(q.quote,(q,),'scope_qualifier_candidate')
    return RoleValue(direct.quote,(direct,),'explicit_direct_object_candidate'),recipient,destination,qualifier,'explicit_prepositional_boundary'


def refine(document,clauses,entities,duties):
    output=[]; by_clause={c.clause_id:c for c in clauses}
    for duty in duties:
        role=duty.semantic_role
        clause=by_clause[duty.source_clause]
        if role.action.value is None and role.object.evidence:
            original=role.object.evidence[0]; local=TextView.of(original.quote)
            match=re.match(r'\s*ب?(?P<word>الرد|رد)(?!\w)\s*',local.text)
            if match:
                from .evidence import subspan
                a,b=local.bounds(match.start('word'),match.end('word'))
                word=subspan(clause,original.start-clause.span.start+a,original.start-clause.span.start+b)
                rest_start=local.bounds(match.end()-1,match.end())[1]
                rest=original.quote[rest_start:].strip()
                rest_offset=original.quote.find(rest,rest_start) if rest else 0
                obj=RoleValue(rest,(subspan(clause,original.start-clause.span.start+rest_offset,original.end-clause.span.start),),'explicit_expression') if rest else RoleValue()
                role=replace(role,action=RoleValue('return',(word,),'lexical_candidate'),object=obj)
        action=arabic_action(role,document,duty)
        revised=replace(role,action=action)
        obj,recipient,destination,qualifier,status=boundaries(revised,by_clause[duty.source_clause])
        def identity(value):
            surface=value.evidence[0].quote if value.evidence else None
            return resolve(surface,document,clauses,entities)
        fields={name:getattr(revised,name) for name in SemanticRole.__dataclass_fields__}
        fields['object']=obj
        actor_identity=identity(role.actor);beneficiary_identity=identity(role.beneficiary)
        for name,identity_value in (('actor',actor_identity),('beneficiary',beneficiary_identity)):
            if identity_value.ambiguity_status=='ambiguous':
                fields[name]=replace(fields[name],value=None,status='ambiguous')
                fields['uncertainty']=(*fields['uncertainty'],name+'_identity_or_scope_ambiguous')
        if action.status=='ambiguous':
            fields['uncertainty']=(*fields['uncertainty'],'arabic_action_ambiguous')
        refined=PreciseRole(**fields,actor_identity=actor_identity,beneficiary_identity=beneficiary_identity,
                           recipient=recipient,destination=destination,scope_qualifier=qualifier,boundary_status=status)
        output.append(replace(duty,semantic_role=refined,subject=obj.value or '',
                              obligated_party=refined.actor.value,beneficiary=refined.beneficiary.value))
    return tuple(output)
