"""Metadata eligibility only. authority.py still decides legal application checks."""
from dataclasses import asdict
from .schemas import AUTHORITY_CLASSES, SourceClass, Eligibility


def evaluate(candidate, request):
    p=candidate.provenance
    reasons=[]
    if request.context.unsupported:
        return Eligibility('incompatible',('unsupported_jurisdiction',))
    if p.ai_generated:
        return Eligibility('incompatible',('ai_generated_source',))
    allowed=AUTHORITY_CLASSES if request.family=='legislation' else (
        {SourceClass.DRAFT} if request.family=='drafts' else {SourceClass.CONTRACT})
    if p.declared_source_class!=SourceClass.UNKNOWN and p.declared_source_class not in allowed:
        return Eligibility('incompatible',('source_purpose_conflict',))
    if p.source_class==SourceClass.UNKNOWN: reasons.append('source_class_unknown')
    identity='verified' if p.identity_verified and p.verified_at and p.official_url else 'unverified'
    if request.family=='legislation' and identity=='unverified': reasons.append('source_identity_unverified')
    jurisdiction='metadata_compatible' if request.context.jurisdiction.known() else 'unverified'
    for dimension,wanted in asdict(request.context.jurisdiction).items():
        actual=getattr(p.jurisdiction,dimension)
        if wanted=='unknown':
            continue
        if p.jurisdiction_verified and actual!='unknown' and actual!=wanted:
            return Eligibility('incompatible',('jurisdiction_conflict',),identity_status=identity)
        if not p.jurisdiction_verified or actual=='unknown': jurisdiction='unverified'
    if jurisdiction=='unverified': reasons.append('jurisdiction_unverified')
    temporal='unverified'
    if request.context.as_of:
        when=request.context.as_of
        if p.effective_from and when<p.effective_from or p.effective_to and when>p.effective_to:
            return Eligibility('incompatible',('outside_effective_range',),identity_status=identity)
        if (p.effective_from and p.temporal_verified_through and p.verified_at
                and p.temporal_verified_through>=when): temporal='metadata_supported'
    if request.family=='legislation' and temporal=='unverified': reasons.append('temporal_unverified')
    return Eligibility('unknown' if reasons else 'compatible',tuple(reasons),temporal,jurisdiction,identity)
