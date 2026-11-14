# Phase 2A completion report

Repository: `brontoo/LEGAL-BRAIN`. Branch:
`feature/phase2a-hybrid-legal-retrieval` (existing remote branch).
Starting commit: `8b1a1889a9f477084770ffa5416323437e12ff4a`.
Fetched/verified ancestry and a clean working tree before edits; the remote had no
additional commits. The final implementation commit/push is recorded in Git history
and the completion response. No duplicate remote branch, PR, merge, deployment,
production migration, credential edit or knowledge-record mutation occurred.

## Implementation

The optional local `retrieval` package provides typed requests/results/provenance,
conservative bilingual normalization, exact references including years, parameterized
semantic/lexical RPC adapters, standard RRF with deterministic ordering, source/
jurisdiction/date eligibility, safe diagnostics and request-scoped embedding reuse.
The original e5 encoder, query prefix, 1024 dimensions, lazy-load lock, five tool
entrypoints, legacy RPCs and final passage caps remain intact. No model or external
search service was added; production requirements/lockfiles are unchanged.

Exact and compatible-metadata preferences are separately configurable and leave
RRF scores unchanged. Missing IDs and conflicting source versions fail closed.
Metadata compatibility never becomes a legal-applicability ruling. Unknown metadata
remains an explicitly unverified lead or is excluded by strict policy. No excluded
source can be restored through another branch or an unfiltered legacy fallback.

Only final displayed passages receive existing collector references. Duplicate
ranker results and repeated tool retrievals do not duplicate citation IDs within
one collector. Untrusted titles/passages are fenced; verification sees exactly the
displayed body. Context/cache/diagnostics remain isolated between requests. The
Phase 1.5 post-revision citation/language refresh remains active and is tested with
hybrid evidence. Existing authority/review/revision infrastructure is reused.

`POST /generate` adds optional validated `retrieval_context` while hybrid is enabled;
there is no new endpoint or SSE frame type. Skills and retrieval flags are independent.
Existing Next.js proxy forwarding, server-side authentication and frontend behavior
remain in place; no frontend source was modified. Mobile overflow is not fixed.

## Executed validation

| Check | Actual outcome |
| --- | --- |
| Before: full `python -m unittest discover -s tests -t . -v` | PASSED: 1,299 |
| Final full Python suite | PASSED: 1,391, including 92 new offline tests, no failures/skips |
| Disposable PostgreSQL suite | PASSED: 20 separate checks, PostgreSQL 16.12 / pgvector 0.8.1 |
| Migration, repetition and rollback/reapply | PASSED in disposable database; original rows/RPC definitions/HNSW indexes preserved |
| Actual SQL synthetic benchmark | PASSED: 100 EN/AR queries, 300 fictional rows; fixed labels, real SQL ranking/filters |
| Four flags / evidence / revision / privacy / concurrency | PASSED offline unit coverage |
| `PYTHONPATH=. python scripts/smoke_hybrid_retrieval.py` | PASSED real HTTP auth/context/four flags/SSE with external-service fakes |
| Existing skills HTTP smoke | PASSED with external-service fakes |
| Actual production Next.js proxy | PASSED forwarded new context; DIFC selected / conflicting federal scope excluded evidence; authenticated SSE retained |
| `npm run lint` | PASSED |
| `npx tsc --noEmit` | PASSED |
| `npm run build` | PASSED, local fonts retained |
| `git diff --check` | PASSED for Phase 2A changes |
| Live nonproduction Supabase/Gemini/real e5 | BLOCKED: credentials/integration dependencies absent |
| Production-size load / legal-quality acceptance | NOT RUN |

No live RPC/model success is inferred from fakes. The database checks actually
executed the migration/functions/index plans/permissions/RLS and benchmark, rather
than reporting SQL syntax inspection as execution. Test services/container are
stopped after validation; no prepared snapshot or production service was published.

## Measured findings

The final synthetic SQL run reports semantic-only versus default hybrid:
Recall@K 0.55 → 1.00, Precision@K 0.375 → 0.70, MRR 0.525 → 1.00,
nDCG@K 0.517300 → 1.00, hit rate 0.60 → 1.00. Arabic and English strata show
the same figures in this controlled fixture. Hybrid jurisdiction/legal exclusion,
fixture provenance status and displayed-evidence integrity are 1.00. There are no
per-query recall regressions in this fixture. False-positive extras and false
negatives remain explicitly listed in the committed artifact.

These are **synthetic vector and SQL-engine measurements**, not actual e5 semantic
quality or improved legal reasoning. Feature vectors encode family/topic and produce
semantically similar confusers; no scripted ranking lists are substituted for SQL.
Latency numbers and limits are detailed in the benchmark report/artifact, with no
production-scale assertion. Human review/current-law acceptance remains mandatory.

## Blockers and limits

All required engineering checks above passed within their stated scopes. AC-04 and
AC-20 remain qualified by unavailable live e5 validation; unrestricted end-to-end
semantic/production readiness is not claimed. Current GOOGLE_API_KEY, SUPABASE_URL
and SUPABASE_KEY presence checks found them absent; the real Supabase, sentence-
transformers and Gemini integration packages are absent from the ordinary runtime.
Only optional test psycopg was installed in a separate temporary virtual environment.
No credentials were requested in chat or extracted from another service.

The additive migration is ready for operator review, **not deployed**. Existing
real records need authorized provenance audit/backfill before strict mode is useful.
JSON review flags are attestations, not automatic proof; metadata can be incomplete
or wrong. Common FTS terms and ANN filtering need production-sized plans/timeouts.
The prefix display budget can hide long-chunk suffixes, which cannot support quotes.
Diversity may intentionally cap additional distinct articles and reports exclusions;
configure it for multi-article work rather than treating titles as unique identities.

Existing service-role bypass/shared-token authorization limitations remain. There
is no new identity provider, NLI/entailment guarantee, automatic statutory update,
full Arabic morphology, cross-encoder, reingestion or frontend redesign. The mobile
workspace issue from Phase 1.5 is unchanged and not claimed fixed. Qualified UAE
lawyer review and safe nonproduction live validation remain outstanding.

The technical layer can support scoped Phase 2B development; production release
requires the manual migration review, authorized nonproduction corpus/model tests,
provenance review, realistic load plans and human legal acceptance. See the
[acceptance matrix](hybrid-retrieval-acceptance.md) for every AC and its qualifications.

## Files created

- `benchmarks/__init__.py`
- `benchmarks/hybrid/__init__.py`
- `benchmarks/hybrid/build_fixture.py`
- `benchmarks/hybrid/fixture.json`
- `benchmarks/hybrid/metrics.py`
- `benchmarks/hybrid/postgres.py`
- `benchmarks/hybrid/results.json`
- `benchmarks/hybrid/runner.py`
- `docs/hybrid-retrieval-acceptance.md`
- `docs/hybrid-retrieval-architecture.md`
- `docs/hybrid-retrieval-benchmark.md`
- `docs/hybrid-retrieval-legal-safeguards.md`
- `docs/hybrid-retrieval-migration.md`
- `docs/phase2a-completion-report.md`
- `migrations/phase2a_hybrid_retrieval.sql`
- `migrations/phase2a_hybrid_retrieval_rollback.sql`
- `retrieval/__init__.py`
- `retrieval/config.py`
- `retrieval/context.py`
- `retrieval/diagnostics.py`
- `retrieval/eligibility.py`
- `retrieval/engine.py`
- `retrieval/evidence.py`
- `retrieval/fusion.py`
- `retrieval/lexical.py`
- `retrieval/normalization.py`
- `retrieval/provenance.py`
- `retrieval/query_analysis.py`
- `retrieval/schemas.py`
- `retrieval/semantic.py`
- `scripts/audit_retrieval_metadata.py`
- `scripts/smoke_hybrid_retrieval.py`
- `scripts/test_hybrid_database.py`
- `tests/retrieval/__init__.py`
- `tests/retrieval/helpers.py`
- `tests/retrieval/test_benchmark.py`
- `tests/retrieval/test_core.py`
- `tests/retrieval/test_integration.py`

## Files modified

- `.env.example`
- `README.md`
- `legal_agent.py`
- `main.py`
