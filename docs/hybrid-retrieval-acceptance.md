# Phase 2A acceptance matrix

Baseline: 1,299 passing Python tests. Final: **1,391 passing Python tests**, including
**92 new offline tests**. The optional disposable database suite executed **20
additional checks**; these are not silently included in the 1,391 unit total.

| Criterion | Status / evidence |
| --- | --- |
| AC-01 Existing Phase 2A branch only | PASSED: tracked the already-existing remote branch; no duplicate remote branch |
| AC-02 Phase 1.5 baseline preserved | PASSED: start `8b1a188`, all 1,299 prior tests included in final passing run |
| AC-03 Hybrid package integrated | PASSED: original five tools → new engine → original collector and graph pipeline |
| AC-04 e5 / vector(1024) retained | PASSED implementation/contract tests; live e5 loading/ranking BLOCKED by unavailable integration dependencies |
| AC-05 Safe lexical retrieval | PASSED: actual PostgreSQL FTS/exact RPCs, bound values, GIN/index/permission tests |
| AC-06 Exact references | PASSED: bilingual article/instrument pairs, clause paths, years, partial/wrong identities and unverified-field negatives |
| AC-07 Deterministic RRF | PASSED: standard score, rank contributions, unique ranks, ties, dedup, conflicts and optional ordering controls |
| AC-08 Family boundaries | PASSED: five-family contracts, metadata purpose checks and family+ID identities |
| AC-09 Precedents not promoted to law | PASSED retrieval/classification tests; no claim of complete LLM misuse prevention |
| AC-10 Jurisdiction filtering | PASSED: seven categories, unknown, independent dimensions, special-regime conflicts, no forum→law inference |
| AC-11 Unknown provenance/time unverified | PASSED: explicit research-lead/strict policies and SQL/Python parity |
| AC-12 Evidence/citations | PASSED: final allocation, exact displayed text, unreturned/excluded text rejection and revision re-verification |
| AC-13 Concurrent isolation | PASSED: simultaneous separate regimes/collectors and shared-scope embedding lock |
| AC-14 Default false | PASSED: environment example, config and legacy regression tests |
| AC-15 All four flag combinations | PASSED offline generation and real FastAPI HTTP with external-service fakes |
| AC-16 Hybrid-off legacy compatibility | PASSED: old RPC arguments/thresholds/counts/output and collector behavior; no schema.sql changes |
| AC-17 Additive documented migration | PASSED: migration/repetition/rollback executed in disposable database; original RPC definitions and rows preserved |
| AC-18 No production migration | PASSED: only local disposable database touched |
| AC-19 Bilingual benchmark | PASSED: 100 individually evaluated EN/AR cases, 300 fictional rows, fixed labels |
| AC-20 Measured comparison | PASSED for actual SQL with synthetic vectors; real multilingual-e5 quality comparison remains BLOCKED/unverified |
| AC-21 Negative security/eligibility | PASSED: source purpose, conflicting branches, invalid metadata, SQL/permissions/RLS, privacy, prompt fencing |
| AC-22 Full Python regression | PASSED: 1,391, no failed/skipped tests |
| AC-23 Lint / TypeScript | PASSED: `npm run lint`, `npx tsc --noEmit` |
| AC-24 Production build | PASSED: `npm run build`, retained local fonts |
| AC-25 Documentation | PASSED: architecture, migration, benchmark, legal safeguards, this matrix and completion report |
| AC-26 Commit/push | Delivered on the requested branch; exact final commit in completion response/Git history |
| AC-27 No merge/deployment | PASSED: no PR opened, no merge/deployment/publication |

## Explicitly unverified / blocked scope

Live nonproduction Supabase, Gemini and actual e5 end-to-end testing remain
**BLOCKED**: credentials and the existing integration/model dependencies are absent.
Actual e5 retrieval-quality gains and production-scale performance are **NOT RUN**.
Do not read AC-04/AC-20's synthetic/contract evidence as live model acceptance or
claim unrestricted Phase 2A production readiness. Human legal review is NOT RUN.
The Phase 1.5 mobile workspace overflow remains known and unchanged.

The disposable test used PostgreSQL 16.12 and pgvector 0.8.1. It exercised SQL rather
than merely parsing it: before-limit filtering, all families, normalization/exact
references, eligibility parity (including null/invalid metadata), original text,
index usability, invoker grants/base privileges/RLS, aggregate audit, repeatability
and rollback/reapplication. See the committed measured result artifact.
