# Phase 2B acceptance record

Validation date: 2026-11-12. Branch `feature/phase2b-clause-intelligence`, based
on `8aecd97d9f4825b2487146bbd446e82ab504df4a`. PASS below describes the executed
engineering/fictional-test scope, not general legal accuracy or production approval.

| Criterion | Outcome and evidence |
| --- | --- |
| AC-01 correct branch/ancestry | PASS: existing remote branch fetched, tracked locally, starting SHA and ancestry verified |
| AC-02 Phase 2A preserved | PASS: existing tests, legacy/hybrid tool behavior, citations, skills and HTTP smoke checks |
| AC-03 functional package | PASS: offline parser/extraction/analysis/report pipeline executed |
| AC-04 segmentation | PASS within fixture: 140/140 exact segments; nested/Arabic/ambiguous/unnumbered tests; complex layouts remain unvalidated |
| AC-05 offsets | PASS: 673/673 nested fixture spans; wrong identity/version/hash/clause/offset/quote rejection tests |
| AC-06 classification | PASS implementation/measurement: 27 labels, multi-label F1 0.958084; 8 FP / 6 FN retained |
| AC-07 entities/definitions | PASS: explicit aliases, ambiguity, quoted defined terms; important-name P 0.954545 / R 1.0 in fixture |
| AC-08 financial terms | PASS focused tests: contexts, Arabic numerals, currencies/percentages; no debt/exposure inferred |
| AC-09 dates/conditions | PASS: relative/absolute/working-day/unknown trigger, exception/dependency and existing deadline adapter tests |
| AC-10 obligations/rights | PASS candidates: mandatory/conditional/prohibited/rights/representations/facts/intentions; fixture clause/kind P/R 0.982456 |
| AC-11 cross-references | PASS: 12/12 fixture tuples, nested/Arabic/duplicate/missing schedule/cycle tests |
| AC-12 conflicts | PASS conservative implementation: 3/3 fixture pairs, distinct scope negative tests, two original spans; not comprehensive legal contradiction detection |
| AC-13 claim grounding | PASS six-state contract, narrow observation support and exact structural validation |
| AC-14 unsupported uncertain | PASS: 140/140 unsupported/invalid-version/fabricated-quote attacks rejected from verification |
| AC-15 no enforceability approval | PASS: legal-claim guards, unknown applicability, mandatory review, no signature approval |
| AC-16 host verification reused | PASS: existing citation allocator/checker, uncertain FactLedger and authority assertion guard; attribution/review/revision regressions pass |
| AC-17 playbooks | PASS all five adapters; independent skill flag; unagreed negotiation drafts and unknown deterministic risk |
| AC-18 hybrid compatibility | PASS offline: real engine adapters/filters, authority enums, missing migration gap; LIVE DATABASE BLOCKED |
| AC-19 default-off flag | PASS `.env.example`, request activation and independent feature tests |
| AC-20 eight flag combinations | PASS: generation/citations/review/revision/authority frames and clause endpoint tested in unit and real HTTP smoke |
| AC-21 authenticated API | PASS: token dependency, wrong/missing token, development no-token 503, flag-off 404, safe 400/413 and actual Next.js proxy |
| AC-22 bilingual fixture | PASS: 20 docs, 120 provisions, English/Arabic/mixed coverage, 12 adversarial/incomplete docs |
| AC-23 extraction metrics | PASS: committed measured artifact, denominators, language strata, error lists, timing and diagnostic scope |
| AC-24 security/concurrency | PASS offline tests: prompt injection, no document logs, tracing block, bounded inputs, isolated concurrent documents/versions/refs |
| AC-25 full regression | PASS: actual baseline 1,391; final 1,469 tests, no failures or skips |
| AC-26 frontend checks | PASS: lint, TypeScript and production build; no frontend source changes |
| AC-27 documentation | PASS six reports, API/schema examples, limits, metrics and human-review checklist |
| AC-28 live accurately reported | PASS reporting; **BLOCKED — LIVE MODEL INTEGRATION NOT EXECUTED**; live Supabase/e5 also blocked |
| AC-29 no false human approval | PASS report always pending / not_provided; fixture not lawyer-adjudicated |
| AC-30 Git delivery | Delivery SHA/remote synchronization recorded in final response and Git history; no force push or alternate remote branch |
| AC-31 no merge/deploy/prod writes | PASS: only local implementation, fictional tests and designated branch push; no production migration/data mutation |

## Commands and observed checks

- Before changes: `python -m unittest discover -s tests -t . -v`: 1,391 PASS.
- Final same command: 1,469 PASS; 78 added tests, no failures/skips.
- Focused clause suite executed separately during development; the final full
  suite includes all final focused tests.
- `PYTHONPATH=. python scripts/smoke_clause_intelligence.py`: PASS real FastAPI/
  Pydantic HTTP, eight flags, authentication, context/errors and existing SSE;
  external Gemini/Supabase/e5 fakes are disclosed.
- Existing hybrid and legal-skills HTTP smoke scripts: PASS with external fakes.
- Actual `next start` production server → real FastAPI → real offline clause core:
  PASS nested `/api/analyze/clauses`, server-only token, Arabic period/trigger,
  unresolved date and missing schedule. Direct unauthenticated backend: 401.
- `npm run lint`, `npx tsc --noEmit`, `npm run build`: all exit 0.
- `python -m compileall -q clause_intelligence benchmarks/clauses scripts/smoke_clause_intelligence.py`
  and `git diff --check`: PASS.
- Fictional benchmark executed with actual analyzer; strict integrity gates PASS.

No final required engineering command failed. Earlier tests exposed nested parent
and Arabic-reference bugs, the intentionally changed route allowlist, an adapter
test lacking a corporate-authority clause, and JSON tuple/list fixture comparison;
these were corrected and the full suite rerun. Gold annotations were not changed.

## Blocked and unassessed work

Current environment checks found GOOGLE_API_KEY, SUPABASE_URL and SUPABASE_KEY
absent, and real supabase/sentence_transformers/langchain_google_genai packages
absent. No confidential values were requested or printed. No live model/database
success is inferred from a fake. The historical Phase 2A 20-check disposable SQL
result is preserved documentation, **not rerun as a Phase 2B live database test**.
Phase 2B adds no migration and offline analysis does not require one.

Live deterministic-versus-Gemini comparison, production load, independent legal
adjudication, representative held-out Arabic/bilingual evaluation and human legal
approval remain **NOT EXECUTED / NOT GRANTED**. The subsystem is suitable for
scoped Phase 2C development and nonproduction review, not an autonomous current-law
opinion, compliance decision or signature approval.
