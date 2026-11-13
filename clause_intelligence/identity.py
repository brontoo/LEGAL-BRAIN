"""Same-document source-definition identity, never registry/legal capacity proof."""
from dataclasses import dataclass
import hashlib
from .evidence import validate_span
from .role_text import clean_party
from .schemas import EvidenceSpan


@dataclass(frozen=True)
class Identity:
    surface_mention: str | None = None
    defined_role: str | None = None
    canonical_entity_id: str | None = None
    canonical_name: str | None = None
    resolution_basis: str = 'unknown'
    definition_references: tuple[EvidenceSpan, ...] = ()
    ambiguity_status: str = 'unknown'


def resolve(mention, document, clauses, entities):
    if not isinstance(mention,str) or not mention.strip():
        return Identity()
    key=clean_party(mention)
    matches=[]
    for entity in entities:
        if key not in [clean_party(entity.name),*(clean_party(a) for a in entity.aliases)]:
            continue
        if not validate_span(document,clauses,entity.evidence) or entity.name not in entity.evidence.quote:
            continue
        matches.append(entity)
    if len({e.name for e in matches})>1 or any(e.ambiguity for e in matches):
        return Identity(mention, resolution_basis='conflicting_definitions',
                        definition_references=tuple(e.evidence for e in matches),ambiguity_status='ambiguous')
    if matches and any(c.structure=='schedule' for c in clauses):
        return Identity(mention,resolution_basis='instrument_or_schedule_scope_requires_review',
                        definition_references=tuple(e.evidence for e in matches),ambiguity_status='ambiguous')
    if not matches:
        return Identity(mention,resolution_basis='surface_only_no_definition',ambiguity_status='unresolved')
    entity=matches[0]
    material='\0'.join((document.document_id,document.version,document.digest,entity.name))
    canonical='ENTITY-'+hashlib.sha256(material.encode()).hexdigest()
    return Identity(mention,entity.role,canonical,entity.name,'explicit_same_document_definition',
                    tuple(e.evidence for e in matches),'unambiguous')


def equivalent(left,right,document,clauses,entities):
    a,b=resolve(left,document,clauses,entities),resolve(right,document,clauses,entities)
    if a.ambiguity_status=='ambiguous' or b.ambiguity_status=='ambiguous':
        return None
    if a.canonical_entity_id and b.canonical_entity_id:
        return a.canonical_entity_id==b.canonical_entity_id
    # Exact surface equality is not cross-alias equivalence or confirmed identity.
    return None
