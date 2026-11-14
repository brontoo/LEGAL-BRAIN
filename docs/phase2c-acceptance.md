# Phase 2C acceptance record

Date: 2026-11-12 (Asia/Dubai). Engineering passes refer to the executed local/
fictional scope. They are not expert legal acceptance or production readiness.

| Gate | Observed outcome |
| --- | --- |
| AC-01 correct branch | PASS existing `feature/phase2c-legal-reasoning-validation`, ancestry from `a4814627869aebdeba255dcf335f56b2402111ef` verified |
| AC-02 Phase 2B baseline | PASS actual 1,469 tests before edits; original extraction/fixture preserved with v2 off |
| AC-03 role hardening | PASS additive Obligation adapter, evidenced actor/action/object/beneficiary and uncertainty |
| AC-04 negation | PASS specified English/Arabic negative forms, neither-party, negative entitlement and ambiguous-scope tests |
| AC-05 roles measured | PASS actual actor/action/beneficiary P/R/F1 and pairing/tuple metrics on frozen corpus |
| AC-06 conditions measured | PASS typed/nested qualifications, fulfilment unknown, trigger/exception/deadline metrics and cross-actor scope tests |
| AC-07 mixed language | PASS ten genuinely mixed documents, marker-based alignment and separate results |
| AC-08 source integrity | PASS 1,111/1,111 legacy and 1,771/1,771 v2 spans; wrong-source/version/hash/quote tests |
| AC-09 unsupported semantics | PASS 120/120 attacks rejected per mode; structural support limited to exact field-expression presence |
| AC-10 no enforceability approval | PASS legal claims require verification; signature approval absent; fulfilment/liability unknown |
| AC-11 safeguards | PASS existing citation/fact/authority plus review/revision regressions, no competing verifier |
| AC-12 skills | PASS five adapters plus feature-combination generation tests |
| AC-13 retrieval | PASS offline compatibility/source filtering/missing-infrastructure behavior; live project remains BLOCKED |
| AC-14 API | PASS existing path/proxy/phase2b.v1, additive v2 fields, real HTTP and loopback production-proxy test |
| AC-15 default off | PASS independent `ENABLE_CLAUSE_ROLE_V2=false`; normal analysis behavior retained |
| AC-16 shadow corpus | PASS 30 docs / 210 provisions / 131 roles, frozen hashed authoring separate from prediction |
| AC-17 comparison | PASS both modes on identical bytes/labels; raw errors and regressions retained |
| AC-18 granular metrics | PASS positive-field P/R/F1, modality/polarity/conditionality, pairs/full/partial tuples and denominators |
| AC-19 mixed weaknesses | PASS mixed beneficiary F1 .769231 and remaining error/annotation limits explicitly reported |
| AC-20 lawyer workflow | PASS 30-case A/B packet, empty forms, independent review/adjudication protocol and comparison tooling prepared |
| AC-21 lawyer status | PASS accurate reporting: actual lawyer evaluation NOT RUN; no agreement/approval manufactured |
| AC-22 Gemini | Live evaluation BLOCKED; absence of credentials/packages and no real model execution accurately reported |
| AC-23 Supabase | Live project/migration/e5 validation BLOCKED; safe audit prerequisite check and reproducible procedure documented |
| AC-24 security/privacy | PASS negative tests, request/version isolation, cancellation-safe admission, safe errors, injection/tracing/logging tests |
| AC-25 local stress | PASS 20 disposable process cases, expected accepts/rejections, CPU/AS/wall bounds; no production stress |
| AC-26 full Python | PASS final 1,540 tests, 71 added; no failures/skips |
| AC-27 frontend | PASS lint, TypeScript and production build; no UI redesign or mobile-fix claim |
| AC-28 documentation | PASS eight reports, method/provenance/metrics/API/security/live/legal limits and exact inventory |
| AC-29 boundaries | PASS no merge, deployment, production mutation, SQL migration, credential edit or real-client upload |
| AC-30 delivery | Final Git history/response records implementation commit and verified push to the designated branch only |

## Executed commands

- `python -m unittest discover -s tests -t . -v`: baseline 1,469, final 1,540 PASS.
- Focused new role, evaluation and security modules executed separately; final
  full suite includes 71 new tests and all existing tests.
- `PYTHONPATH=. python scripts/smoke_phase2c.py`: PASS real HTTP all 16 flag cases,
  legacy/v2 clause modes, generation citations/SSE/auth and local capacity/429.
  External integrations are mocked, not live model reasoning.
- `python -m benchmarks.roles.runner --memory --output <new-path>`: actual both-mode
  prediction/evaluation with strict span/unsupported-claim gates PASS.
- `python -m benchmarks.roles.stress --output <new-path>`: 20 cases, all expected.
- `python -m benchmarks.roles.review_packet --output-dir <new-directory>`: 30-case
  fictional packet prepared; review status NOT RUN.
- `PYTHONPATH=. python scripts/evaluate_phase2c_reviews.py --output <new-path>`
  without human inputs: NOT_RUN, no agreement statistic or legal approval.
- `npm run lint`, `npx tsc --noEmit`, `npm run build`: all exit 0.
- Compile checks and `git diff --check`: PASS.
- Actual local production Next.js proxy to real FastAPI/v2 core: bilingual negative
  roles, exact offsets, old schema and server-only token PASS; direct no-token 401.

The full comparison/stress/regression was rerun after additional cross-actor
qualification tests exposed and corrected a trigger/exception scope leak in v2.
This was a new engineering defect, not a gold-label change. Final extraction
metrics remain identical to the prior measured corpus result. No final required
local engineering check is failing.

## Outstanding release gates

Genuine independent qualified-lawyer review, adjudication/IAA, authorized live
Gemini/Supabase/e5 evaluation, representative untouched held-out evaluation,
authenticated frontend ingress, provider timeout/capacity/privacy review and
production-sized load tests are not granted or completed. Current engineering
completion does not override these blockers. Production legal readiness is **not
granted**, regardless of passing synthetic scores and unit tests.
