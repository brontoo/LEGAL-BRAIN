# Phase 1 Legal Skills Framework

The optional local skills layer selects a professional review methodology before
`/generate` enters the existing LangGraph, RAG, drafting, verification and revision
pipeline. It does not replace that pipeline or create a database/service dependency.

## Architecture and activation

- `skills/schemas.py`: immutable typed manifests, output content contracts,
  jurisdiction context and explainable routing results.
- `validator.py`: exact required fields, scalar/list types, identifiers, numeric
  three-part versions, authority policy, output contracts and restricted frontmatter.
- `loader.py`: sorted local discovery, bounded UTF-8/JSON reads, duplicate-key and
  symlink rejection. It never imports code, runs scripts or follows remote URLs.
- `registry.py`: validated registration, duplicate rejection, enabled resolution,
  dependency availability/cycle validation and category/document/jurisdiction filters.
- `router.py`: explicit selection, structured document type, document classification,
  normalized English/Arabic triggers, jurisdiction compatibility and ambiguity.
- `integration.py`: lazy cached bundled registry and bounded system-instruction
  suffix; no model calls. `risk.py`: deterministic supported ordinal scoring.

Set `ENABLE_LEGAL_SKILLS=true` in the backend environment and restart the server.
The default and `.env.example` value are `false`. Only the string `true`
(case-insensitive, surrounding whitespace ignored) enables the feature.

With the flag off, existing requests without the new optional fields use the same
messages, SSE arguments, response body and headers. The registry is not loaded.
An explicit `skill_id` while disabled returns a clear 400; a new optional field
cannot silently enable the feature. Chat, CLI, Chainlit and smart-office paths
remain unchanged; Phase 1 activation is bounded to verified `/generate` only.

With the flag on, a selected workflow is appended to the existing system message;
the original system rules and user message remain intact. Instructions require
all existing citation, attribution, fact, authority, claim, deadline, rule, language,
review and revision controls. No new source of evidence is registered by a skill.
The existing `_sse_generator` and `_redraft` callable are reused unchanged.

`X-Legal-Skill-Status`, and on selection `X-Legal-Skill` and
`X-Legal-Skill-Version`, expose request-level activation metadata without changing
SSE frames. Clients should call resolution first when they need detailed reasons.
Headers are request-specific; documents and full prompts are not logged by skills.
No selection is persisted in shared chat history.

Automatic ambiguity, no match or incompatibility leaves the original workflow
active and is visible in the status header. An explicitly selected incompatible
skill returns 400 before streaming. Invalid bundled configuration fails closed;
no partially valid registry is used. Malformed request/selection data returns 400
(or transport-level Pydantic 422). Server configuration faults are operator errors;
there is no API that accepts paths, editable instructions or remote skill content.

## Routing and jurisdiction

Explicit enabled ID wins, subject to compatibility. Otherwise scores combine:
structured type match (5), document classification (4), and up to three distinct
workflow trigger matches (5 each). Case/Unicode/Arabic diacritics are normalized;
word boundaries avoid accidental substring matches. NDA classification suppresses
generic agreement classification. No additional LLM calls are made. Sort by score,
then skill ID. A top-score margin of 2 or less is ambiguous; no skill activates.
All candidate scores, reasons, warnings and versions are returned by resolution.

The six context dimensions are independent: `governing_law`,
`court_jurisdiction`, `regulatory_jurisdiction`, `contractual_choice_of_law`,
`subject_matter_jurisdiction`, and `procedural_rules`. Each accepts:
`uae_federal`, `abu_dhabi`, `dubai`, `sharjah`, `other_uae_emirates`, `adgm`,
`difc`, or `unknown`. Unknowns require confirmation; a known forum never fills in
missing governing law. Unsupported values are rejected rather than mapped to UAE.

Existing `CaseFile`/`derive_forum_key` logic checks ADGM/DIFC forums, including
incomplete intake. Conflicting supplied court context blocks activation. A supplied
non-UAE case country is outside the initial scope and requires manual applicability
confirmation. Location alone never establishes law. The existing authority register
and regime notes continue to run in their original pipeline; the router does not
reimplement legal authority validation.

All five playbooks cover the seven named UAE jurisdiction categories as cautious
methodologies. A manifest may narrow these. Compatibility checks every known
dimension and the existing case forum against the manifest; it never treats ADGM
or DIFC as a substitute for federal or local law. This is not a determination of
court competence, conflicts of laws, regulatory scope or enforceability.

## API and proxy

Both new routes use the same `Depends(require_token)` as `/generate`. Existing
behavior remains: a configured `API_TOKEN` requires its bearer header; an unset
token allows development access. No frontend secret is introduced.

`GET /skills` returns `{ "enabled": false, "skills": [] }` when disabled; when
enabled it returns allowlisted metadata for enabled skills. It never serves
SKILL.md bodies, local paths, provenance URLs, dependency definitions or triggers.

`POST /skills/resolve` (404 when disabled):

```json
{
  "prompt": "Assess this confidentiality agreement",
  "doc_type": "nda",
  "jurisdiction": {"governing_law": "uae_federal", "court_jurisdiction": "dubai"},
  "skill_id": "uae-nda-review"
}
```

The response contains `status`, nullable `selected_skill`, ranked `candidates`,
`warnings`, and `reason`. Prompt is required (1..20000 characters); other fields
are optional. Unknown/disabled identifiers and traversal/URL identifiers return 400.

`POST /generate` accepts optional `skill_id`, `skill_jurisdiction` (the same
six-dimension object), and `skill_risk` (below). Existing fields remain compatible.
Use `skill_id` for an intentional override, not a filename.

The existing Next.js catch-all proxy already forwards GET/POST, query strings,
server-side `API_TOKEN`, JSON bodies and SSE. Frontend callers can use `/api/skills`,
`/api/skills/resolve` and `/api/generate`. Its current response-header allowlist
does not forward skill headers; use the resolve response for UI metadata. No UI
or proxy changes are necessary for backend discovery/resolution. A selector and
persistent UI audit display are Phase 2 work, not implemented here.

## Playbooks and output content

Every skill has a substantive SKILL.md with purpose, activation, scope, inputs,
review procedure, research, risk assessment, output content, quality controls,
escalation, prohibited assumptions and lawyer review. Names/descriptions in
frontmatter must match its manifest. Output contracts specify prompt content,
not a new JSON schema imposed on the existing generated document.

| ID | Types and required information | Output |
| --- | --- | --- |
| `uae-contract-review` | Agreement/contract; document and client side | Clause reference, exact source, issue, risk, severity, action, proposed wording, verified authority/status/basis |
| `uae-nda-review` | NDA/confidentiality; document and disclosure direction | Clause findings, criterion, GREEN/YELLOW/RED workflow classification, gaps and lawyer queue; never signature approval |
| `uae-legal-risk` | Risk assessment/transaction; matter and evidence | Risk register, evidence/assumptions, supported ratings, score or unknown, mitigation/residual risk and escalation |
| `uae-contract-negotiation` | Negotiation brief/comparison; document and objectives | Brief, clause comparison, preferred/fallback proposals, concessions and approval needs |
| `uae-corporate-due-diligence` | Corporate records; target, scope and supplied documents | Legal checklist, source/status, transaction impact and missing-evidence requests |

Missing required information is requested and shown as gaps, not fabricated or
silently considered satisfied. Playbook required inputs are workflow requirements,
not new mandatory API fields. The host cannot deterministically prove that free
text includes a complete contract or genuine company records. Human review remains
mandatory. There is no automatic approval or enforcement of model output shape.

Risk scoring is actual host computation, not just a prompt instruction. For the
risk workflow `/generate` may accept:

```json
{"skill_risk": {"severity": 4, "likelihood": 5, "evidence_supported": true}}
```

The host injects score 20/critical with a client-supplied, human-review-required
basis. This boolean records the submitter's support assertion, not independent
verification. Missing support or either rating yields unknown, never zero. No
probability or financial exposure is estimated. Optional `matrix` accepts `levels`
(2..10) and ascending `[upper_bound, label]` bands covering `levels²`, e.g.
`{"levels":3,"bands":[[3,"ordinary"],[9,"escalate"]]}`. Ratings must be integers,
not booleans or numeric strings. Defaults: 1..5; bands 4/9/15/25. Model output is
still reviewed; the deterministic host result is the reference score. Other
workflows reject supplied risk data after selection rather than misusing it.

## Adding, validating and versioning skills

1. Create a reviewed folder under `skills/playbooks/<safe-slug>/` containing
   `manifest.json` and `SKILL.md`. No user upload/API registration is supported.
2. Use exactly the manifest fields shown by the bundled examples; all metadata
   is strictly validated. Use numeric `major.minor.patch`; one ID per registry.
   Adding another version with the same ID is rejected, not silently upgraded.
3. Write independently sourced instructions; set the required authority policy,
   provenance, explicit jurisdiction list, inputs and output content. Keep names
   and descriptions identical in manifest and two-scalar YAML frontmatter.
4. Add focused routing, jurisdiction, security and workflow tests. Dependencies
   are existing skill IDs only; they are validated for availability/cycles, never
   installed, executed or automatically activated. `references/` is optional
   documentation and is not automatically read into prompts.
5. Run validation/tests below. Restart the process to refresh the cached registry.
   Runtime API callers cannot hot-load or modify bundled definitions.

```bash
python -c 'from skills import SkillRegistry; print([s.manifest.skill_id for s in SkillRegistry.discover().available()])'
python -m unittest tests.test_skills tests.test_skills_api -v
python -m unittest discover -s tests -t . -v
PYTHONPATH=. python scripts/smoke_legal_skills.py
cd frontend
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

Unit tests use the repository fake dependency harness and need no external service,
client documents or embedding downloads. The optional smoke script uses real
FastAPI/Pydantic/httpx with fake model/storage dependencies in an isolated process.
Do not run this test harness as a production server. Live Gemini/Supabase behavior
requires separately configured credentials and legal review of actual outputs.

See [provenance](skills-provenance.md) and [validation report](skills-phase1-report.md).
