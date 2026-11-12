# Legal safeguards and provenance

Retrieval relevance, exact identifier matching and quotation matching are not
proof of applicable, current law. The original `authority.py`, citation,
attribution, review and revision checks remain primary. Human legal review is
mandatory. No foreign dataset or research index establishes UAE law.

## Source purpose

Source classes are `official_legislation`, `judicial_decision`,
`administrative_regulatory`, `contractual_evidence`, `drafting_precedent`,
`internal_policy`, `external_commentary`, and `unknown`. `legal_documents` is not
assumed to contain only legislation. A known prohibited source purpose is excluded
even if its classification has not yet been independently reviewed; an unverified
positive authority declaration never upgrades a record to verified authority.
AI-generated records flagged in metadata are excluded.

Legislation/judgment tools accept the three authority-oriented classes plus
explicit unknown research leads under the configured policy. Draft tools accept
drafting precedents; contracts/notices/POA accept contractual evidence. A contract,
policy or drafting example cannot gain authority simply by occupying a table or
appearing in a ranked list. The framework cannot detect undisclosed provenance
fraud or AI generation that is absent from metadata.

## Optional metadata contract

All values below are optional. Boolean review flags must be real JSON booleans;
missing flags mean unverified. Missing/null text/date fields remain null. Invalid
metadata is excluded, not converted into verified defaults. Original records are
never backfilled automatically.

`metadata.retrieval_v1` can contain:

- `source_class`, `classification_verified`, `ai_generated`;
- `instrument_id` (canonical examples `law:12`, `law:12:2020`), `issuing_authority`,
  `official_url`, `original_title`, `article_reference`, `clause_reference`;
- `jurisdiction` (six independent dimensions), `jurisdiction_verified`, `language`;
- `publication_date`, `effective_from`, `effective_to`, `amendment_version`;
- `identity_verified`, `verified_at`, `temporal_verified_through`;
- `source_document_id`, `content_checksum` (source-supplied identity/version data).

Example identifiers/numbers are fictional format examples, not real UAE citations.
A recorded checksum is retained as provenance, not independently certified by the
engine; define its source scope during authorized backfill. Only operator-reviewed
metadata should set positive review flags. A syntactically HTTPS URL is not proof
that its host is official. The engine does not browse or validate official websites.

The internal result separately records source identity status, jurisdiction
metadata compatibility, temporal support and exact-reference match basis. The
existing citation verifier separately determines whether text actually supplied
to the model supports a quotation. There is no single flag asserting all four.

## Jurisdiction and time

The seven existing categories and `unknown` are reused. Requested dimensions are
compared independently; location/forum never fills governing law. A matching
metadata scope is not a court-competence, conflicts-of-laws or subject-matter
opinion. Federal/local mismatch is a search-scope exclusion, not a legal ruling
that federal law cannot operate in an emirate. Request separate scopes when a
matter needs multiple regimes. ADGM and DIFC remain distinct.

Verified conflicting metadata is excluded. Missing context or missing/unreviewed
source dimensions remain unknown. With `research_lead` they are visibly labeled
UNVERIFIED and never called compatible; strict `exclude` omits them. A reviewed
source can still be an unverified research lead for the requested date or scope.

Known effective-range conflicts are excluded for an explicit `as_of`. No date is
silently inferred from upload time. An empty expiry date alone does not prove
current force. Temporal support requires effective-from, independent review date
and `temporal_verified_through` covering the requested date. These are metadata
attestations, not a replacement for legal authority/application checks.

## Evidence and security

Only selected passages receive existing allocator IDs. Family+chunk identity
prevents cross-family collisions. Missing IDs, inconsistent versions and known
incompatibility in either branch fail closed. Repeated displayed sources reuse a
reference within the current collector; simultaneous requests stay isolated.

Original candidate passages are retained intact. Only the displayed prefix enters
`Evidence.text`; the host's existing fence-marker escaping is applied consistently
to that body. Verification uses exactly the displayed body, not the hidden suffix,
title or a fabricated truncation marker. Reserved-marker spelling may be escaped
for presentation; inspect the original source for literal-marker quotations.
Titles are fenced separately; raw title instructions do not enter trusted headers.
Safe source class/status and jurisdiction-enum metadata accompany evidence.

No arbitrary SQL, remote skill code, external reranker or publicly accessible
search-debug route is added. SQL values are bound, family/function names allowlisted,
new functions are invoker-security, PUBLIC execution is revoked, and the view
respects base privileges/RLS. Existing service-role RLS bypass remains a deployment
limitation; a shared backend token is not user/tenant authorization.

Raw queries, passages, URLs, credentials and provider exception bodies do not enter
retrieval diagnostics or logs. Request-local embedding caches are bounded and
cleaned with context lifecycle. Review upstream SDK/hosting logging configuration
separately. No production credentials or records were used during validation.

## Methodological reference

Reviewed `maastrichtlawtech/awesome-legal-nlp` at
`397ef5e0fbbe52be13867c43072332376ea4c28f`, including BSARD/COLIEE/CLERC retrieval
entries and LLeQA source-grounded QA. Its repository license is MIT (existing
notice in `docs/third-party/legal-nlp-MIT.txt`). The index informed passage-level
labels, ranking metrics and separation of retrieval from legal/source verification.
No external code, model, dataset or foreign legal content was imported. Licenses
of linked datasets/models are not covered by the index license or cleared here.
