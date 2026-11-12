# Phase 2B evidence and reasoning safeguards

This subsystem assesses documentary grounding, not the truth of every contractual
statement or the legal enforceability of a clause. A matching quotation does not
establish performance, entitlement, liability, authority, current law or approval.

## Claim-to-evidence schema

Each `Finding` contains ID, category, claim text/type, exact evidence spans,
support status, analytical basis, contrary evidence, missing information, legal
verification requirements, unknown risk level, unassessed legal applicability
and pending human review. Original source observations, uncertain inferences,
legal-review questions and proposed amendments remain distinct categories.

| State | Actual implementation |
| --- | --- |
| SUPPORTED_BY_TEXT | Generated exact source observation, or one exact-quote claim identical to its validated quotation |
| CONTRADICTED_BY_TEXT | Narrow standardized denial that the cited clause contains a supplied quote, contradicted by the validated quote's presence |
| INSUFFICIENT_EVIDENCE | Missing/rejected evidence or support that was not established |
| AMBIGUOUS | Present quotation with unverified interpretation, competing evidence or a potential conflict |
| REQUIRES_LEGAL_VERIFICATION | Proposed legal conclusion/assertion or legal-effect review question |
| NOT_ASSESSED | Explicit nonassessment, model proposal or unverified language equivalence |

The standardized denial is `The cited clause does not contain the quoted text.`
or `البند المشار إليه لا يتضمن النص المقتبس.`. This deliberately limited rule
does not pretend to solve arbitrary semantic contradiction. An arbitrary
paraphrase is never marked supported simply because it cites a real quotation.
Competing passages remain ambiguous; their legal precedence is not resolved.

For example, a fictional contract specifying AED 100,000 supports an observation
that the quoted amount appears. “The penalty is enforceable” requires verified
applicable authority and professional review. A missing completion certificate
does not establish that a brokerage condition failed or was satisfied.

## Deterministic evidence checks

Before evidence enters a finding/citation bridge, validate all of:

1. Exact document ID and version.
2. SHA-256 of the original source text, even if a version label was reused.
3. Genuine integer offsets in bounds; booleans are not accepted as integers.
4. Exact source slice equals the full quotation, without normalization.
5. Referenced clause exists and contains the complete span.

Wrong document/version, invented quotation, omitted appendix, wrong clause,
altered text and invalid offsets cannot become verified textual evidence. If a
caller mixes valid and invalid evidence, the assessment stays insufficient.

After these structural checks, existing `citations.verify_citations` provides
the established quote-presence check using existing `Evidence`/`RefAllocator`.
Refs are local to this report; `C1` in another request is unrelated. Source
spans are pointers, not a competing citation system. Existing `attribution.py`
still governs attribution verification in drafting. Existing fact fidelity,
claims/authority registers, second review and revision checks are unchanged.
New facts use `Standing.UNCERTAIN`, never `AGREED`. No contract observation is
automatically promoted into the case's authoritative factual or legal register.

## Optional interpretation

Both an explicit `model_assisted` request and
`ENABLE_CLAUSE_MODEL_ASSISTANCE=true` are required. The endpoint uses the existing
Gemini object with one bounded call; no new provider or model is installed.
Core analysis always runs without it. Model output is a JSON array of at most
20 strict proposals: `clause_id`, known `category`, bounded `interpretation`, and
one full evidence-span object. Unknown fields, invented evidence, malformed JSON,
wrong clause/version or excessive output reject the proposal batch. SDK errors
are reduced to a safe status without returning/logging exception text.

Even valid output is `unverified_model_interpretation` / `NOT_ASSESSED`. Evidence
presence is checked; semantic support, correct classification and enforceability
are not thereby established. No confidence number supplies legal verification.
Document content is fenced with the host untrusted-input protection. Tracing
opt-ins are blocked for endpoint model calls; operators must also prevent unsafe
global SDK logging. Explicit model mode sends fictional/authorized text to the
existing provider only when configured; there is no automatic document upload.

**BLOCKED — LIVE MODEL INTEGRATION NOT EXECUTED.** Current credentials and real
Gemini/Supabase/e5 packages are absent. Offline callback tests validate transport
contracts and rejection behavior, not real model reasoning or legal NLI.

## UAE legal and human review boundaries

Preserve federal, Abu Dhabi, Dubai, Sharjah, other Emirates, ADGM and DIFC as
distinct scopes. Governing law and court jurisdiction are independent. A Dubai
address/court clause never populates governing law automatically. No foreign
legal rule, invented authority or article number is introduced. Research through
Phase 2A preserves source-class/jurisdiction/time filters and always leaves a
legal research gap until existing authority checks and counsel resolve it.

Before reliance, a qualified UAE lawyer must:

- Confirm document completeness, authenticity, operative version and attachments.
- Review segmentation, aliases, obligations, negation, conditions and exceptions.
- Confirm performance evidence and trigger dates; choose a lawful counting convention.
- Resolve language precedence, amendments, conflicting scope and missing schedules.
- Verify applicable current authority and distinguish contractual wording from law.
- Set commercial positions and supported risk ratings; tailor any proposed wording.
- Review privacy, access rights and the final document independently before signature.

The API returns `signature_approval: "not_provided"` and human review pending.
No lawyer has approved the fixture or implementation as a legal opinion. The
existing shared service token does not establish tenant isolation. No real client
documents, production records or analysis storage were used or introduced.
