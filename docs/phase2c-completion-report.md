# Phase 2C completion report

Repository: `brontoo/LEGAL-BRAIN`.
Branch: `feature/phase2c-legal-reasoning-validation` (existing remote branch).
Starting commit: `a4814627869aebdeba255dcf335f56b2402111ef`.
The remote was fetched, clean state and ancestry verified before editing; there
were no newer branch commits at inspection. A local fetch mapping/tracking branch
was added for the already-existing remote branch, not a duplicate remote branch.
Final implementation SHA and verified push state are supplied in the completion
response/Git history. User work was not reset or discarded.

## Implemented improvements and compatibility

Default-off `ENABLE_CLAUSE_ROLE_V2=false` preserves Phase 2B behavior and schema.
The optional path extends the existing Obligation with evidenced semantic-role
fields, explicit/defined/ambiguous/unknown actor identity, canonical lexical action
candidates, beneficiary/object, polarity/modality, qualifications, local amounts/
deadlines, consequences and uncertainty. It addresses reproduced neither-party,
Arabic negative entitlement, generic actor-prefix, missing beneficiary and
collapsed multi-actor/action weaknesses. Qualified events never establish fulfilment,
currently payable debt, liability or enforceability.

Typed conditions retain nested scope and distinguish precedent/subsequent,
exception, trigger, carve-out, reservation and dependency. Cross-actor tests ensure
one actor's postposed trigger/exception does not become another's condition.
Explicit parallel-language markers support conservative divergence candidates;
no translation, equivalence or prevailing language is automatically established.
Budgeted conflicts respect actor/object/trigger/scope/currency/exception boundaries
and leave amendments/precedence for review.

All source spans retain exact document/version/hash/clause/Unicode offsets/quote.
Existing citations, uncertain facts, authority guard, five skills, retrieval filters
and review/revision checks remain active. New narrow structural support verifies
field-expression presence only; arbitrary semantics remain unverified. No second
citation/fact/authority engine, NLI claim or new paid provider was introduced.

The existing authenticated endpoint and Next.js server proxy remain. New v2 fields
are additive under `phase2b.v1`. Generation/SSE, chat/archive, fonts, RTL, retrieval
tools and all existing flag defaults remain compatible. Two-slot admission,
bounded body reading, cancellation-safe capacity and sanitized errors harden the
endpoint in both modes. A shared service token still does not establish tenant
identity/isolation. No production dependency, DB migration or frontend redesign
was introduced. Existing mobile workspace overflow remains unchanged.

## Executed validation

| Check | Actual result |
| --- | --- |
| Existing full Python baseline | 1,469 PASS |
| Final full Python regression | 1,540 PASS, including 71 added tests, no failures/skips |
| Feature compatibility | 16 combinations: eight existing subsystem states × both role modes |
| Real HTTP smoke | PASS auth/schema/roles, generation citations/SSE, bounded input and local 429; external fakes |
| Local production Next.js proxy | PASS real FastAPI/v2 core, bilingual negative roles/exact offsets/server-only token; direct no-token 401 |
| Frontend lint / TypeScript / build | All PASS, exit 0 |
| Compile / diff checks | PASS |
| Engineering corpus | 30 fictional docs, 210 provisions, 131 roles, 10 genuinely mixed docs, 30 negative and 3 adversarial provisions |
| Evidence spans | Legacy 1,111/1,111; v2 1,771/1,771 valid |
| Unsupported interpretation attacks | 120/120 rejected per mode |
| Local bounded stress | 20/20 expected outcomes; excessive inputs safely rejected |
| Lawyer packet | 30 cases prepared, empty/unattested forms, actual review NOT RUN |
| Live Gemini / Supabase / real e5 | BLOCKED, not executed |

The new corpus was explicitly authored separately from prediction generation and
frozen before v2 measurement. SHA:
`cd7f039bda844d7165b66715369e632ca94ebd634895b20647013a4f19cbb682`.
Gold did not change after measuring. It is synthetic/development-visible, not
independently lawyer-adjudicated or a continuing untouched holdout. The original
Phase 2B fixture/results remain intact and reproducible under the legacy runner.

## Measured role findings

| Measure | Legacy | V2 |
| --- | --- | --- |
| Actor P / R / F1 | .915789 / .713115 / .801843 | 1 / 1 / 1 |
| Action P / R / F1 | .741667 / .679389 / .709163 | .984733 / .984733 / .984733 |
| Beneficiary P / R / F1 | undefined / 0 / 0 | .722222 / .722222 / .722222 |
| Modality / polarity accuracy | .810606 / .810606 | 1 / 1 |
| Conditionality accuracy | .795455 | 1 |
| Trigger / condition / exception F1 | .894737 / .266667 / .896552 | 1 / 1 / 1 |
| Deadline association accuracy | .893939 | 1 |
| Actor-action pair accuracy | .643939 | .984733 |
| Action-beneficiary pair accuracy | .409091 | .908397 |
| Strict full tuple | 0/132 | 118/131 = .900763 |

Full tuples include all 11 evaluated fields; legacy's duplicated subject/action
also counts. Zero full legacy tuples is not zero general understanding. There are
119 legacy partial slots and 13 v2 partial slots. All 30 documents have fewer
erroneous slots; none regresses by that document-level count. Both modes' raw
field errors and category/complex/tag strata are retained in the artifact.

V2 English/Arabic/mixed full-tuple accuracy is .883721/.880952/.934783. Mixed
beneficiary F1 is .769231, not hidden in aggregate scores. Remaining strict errors
are ten beneficiary identity-label differences (defined name versus gold role alias),
two Arabic action readings (`رد` as return instead of reject/reimburse), and one
object boundary. Beneficiary differences count 10 FP/10 FN without a post-hoc
alias-equivalence adjustment, but are not ten proven wrong legal beneficiaries.
These are machine-observed, not lawyer-adjudicated errors. Exact metric definitions
and denominators are in the semantic-role and bilingual reports.

Small-shadow-document performance (separate memory-traced run):

| Mode | Mean ms | p95 ms | Maximum ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
| legacy | 11.711597 | 16.494800 | 21.696915 | 63831 |
| role_v2 | 18.957052 | 25.578934 | 43.176828 | 101148 |

These timings are actual local deterministic runs; memory peaks are traced
Python allocations, not process RSS. Bounded stress results and limits are in
the security report; no production/model/network performance claim is made.

## Live, legal and production limits

**BLOCKED — LIVE GEMINI EVALUATION NOT EXECUTED.**
**BLOCKED — LIVE SUPABASE / REAL E5 VALIDATION NOT EXECUTED.**
Current GOOGLE_API_KEY/SUPABASE_URL/SUPABASE_KEY and integration packages are absent.
The read-only metadata audit stops at its safe missing-prerequisite message.
No credentials were printed, requested in chat or changed. Existing migration
deployment state is unknown; no Phase 2C production or disposable SQL was applied.
Offline fakes prove contracts, not provider reasoning/current law. A reproducible
authorized nonproduction procedure is documented separately.

Track B lawyer evaluation, agreement and adjudication are **NOT RUN**. The prepared
packet has no invented lawyer identities, signatures or approvals. Comparison
requires actual supplied independent attestations/annotations; software does not
verify professional qualification. Legal approval and signature approval remain
unprovided. The 30-gate acceptance matrix distinguishes local passes from blockers.

This limited controlled vocabulary, simple synthetic structure and development-
visible gold do not establish general semantic accuracy or improved legal reasoning.
Complex passive constructions, negation/coordination, unknown role names, ambiguous
Arabic meanings, incomplete qualifications and language alignment need further
review. Provider timeouts, authenticated frontend ingress, distributed quotas,
production privacy/load review and representative expert evaluation remain required.

Engineering is ready for scoped subsequent development/nonproduction professional
review; **production legal readiness is not granted**. Priorities are genuine
independent lawyer annotation/adjudication, untouched externally authored bilingual
evaluation, beneficiary identity-label policy, richer ambiguous-action/object/role
coverage, authorized live integration comparison and deployment access/privacy/
capacity validation. These are recommendations, not completed work.

No branch merge, main-branch change, force push, PR, deployment, environment
publication, production SQL/credential/data mutation or real-client upload occurred.
Only the designated development branch is used for delivery. Temporary local
test services were stopped after validation.

## Exact file inventory

Created: 39 files. Modified: 6 files.

### Created

- `benchmarks/roles/__init__.py`
- `benchmarks/roles/author_corpus.py`
- `benchmarks/roles/corpus.json`
- `benchmarks/roles/lawyer-review-status.json`
- `benchmarks/roles/lawyer_review.py`
- `benchmarks/roles/manifest.json`
- `benchmarks/roles/metrics.py`
- `benchmarks/roles/results.json`
- `benchmarks/roles/review-packet/coordinator-only/blinding-map.json`
- `benchmarks/roles/review-packet/packet.json`
- `benchmarks/roles/review-packet/review-status.json`
- `benchmarks/roles/review-packet/reviewer-1-empty.json`
- `benchmarks/roles/review-packet/reviewer-2-empty.json`
- `benchmarks/roles/review_packet.py`
- `benchmarks/roles/runner.py`
- `benchmarks/roles/stress-results.json`
- `benchmarks/roles/stress.py`
- `clause_intelligence/alignment.py`
- `clause_intelligence/conditions_v2.py`
- `clause_intelligence/consistency_v2.py`
- `clause_intelligence/reasoning_v2.py`
- `clause_intelligence/review_priority.py`
- `clause_intelligence/role_contracts.py`
- `clause_intelligence/role_text.py`
- `clause_intelligence/roles_v2.py`
- `clause_intelligence/terms_v2.py`
- `docs/phase2c-acceptance.md`
- `docs/phase2c-architecture.md`
- `docs/phase2c-bilingual-benchmark.md`
- `docs/phase2c-completion-report.md`
- `docs/phase2c-lawyer-review-protocol.md`
- `docs/phase2c-live-validation.md`
- `docs/phase2c-security-performance.md`
- `docs/phase2c-semantic-role-evaluation.md`
- `scripts/evaluate_phase2c_reviews.py`
- `scripts/smoke_phase2c.py`
- `tests/clause_intelligence/test_role_evaluation.py`
- `tests/clause_intelligence/test_role_security.py`
- `tests/clause_intelligence/test_roles_v2.py`

### Modified

- `.env.example`
- `README.md`
- `benchmarks/clauses/runner.py`
- `clause_intelligence/config.py`
- `clause_intelligence/engine.py`
- `main.py`
