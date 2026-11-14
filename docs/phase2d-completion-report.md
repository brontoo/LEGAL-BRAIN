# Phase 2D completion report

Repository: `brontoo/LEGAL-BRAIN`.
Branch: `feature/phase2d-independent-legal-validation` (existing remote branch).
Starting SHA: `81f34abcb1973394a5db2c6328d5e01ae4f614a8`.
Latest remote, clean tree and ancestry were verified before editing; no newer
branch commits were present at inspection. A local tracking/fetch mapping was
added, not a duplicate remote branch. Final SHA/verified push appear in Git and
the completion response. No user work was reset or discarded.

## Delivered workstreams

**Evaluation integrity:** retired the exposed Phase 2C packet/key/identifiers and
unsafe generator. Historical Git still exposes them; no purge is claimed. New
crypto-randomized packets use disjoint external private destinations, separate
reviewer outputs and owner-only files. Original revisions, finalized submissions,
external origin confirmation, adjudication and audited unblinding have explicit
guards. Actual human material and new assignment keys are not in Git.

**Targeted corrections:** default-off precision mode adds evidence-backed identity
metadata, rejects conflicting/schedule-scoped equivalence, disambiguates Arabic رد
where context supports one meaning, abstains otherwise, and separates object from
recipient/destination/scope. It requires role_v2; existing defaults/schema, legal
safeguards and generation behavior remain. No new NLP/orchestration provider.

**Controlled live integration:** presence-only preflight and executable opt-in
Gemini/Supabase/e5 workers enforce project/nonproduction/configuration guards,
call/request/wall/token/cost-reserve bounds and read-only allowlisted RPCs. Existing
model and retrieval layers are reused. SDK interface support is checked at runtime,
not assumed. No raw SDK prompt/reply/secret logging, automatic model download,
migration or archive ingestion occurs. Actual live evaluation remains BLOCKED.

**Operational readiness:** SDK timeout/retry/output bounds fail closed for optional
clause-model calls. Local capacity/cancellation, privacy, resources and proxy auth
were tested. Anonymous proxy access is a verified release blocker, not fixed or
masked by the service token. No identity provider or public portal was added.

## Actual tests and engineering measurements

- Baseline: **1,540** passing Python tests.
- Final: **1,584**, including **44 added**, no failures/skips. Focused new tests ran separately.
- All **32** subsystem/role/precision configurations passed real local HTTP and
  existing generation citation/SSE/auth checks with external dependencies faked.
- Frontend lint, TypeScript and production build passed; compile/diff checks passed.
- Bounded local stress: **20/20 expected outcomes**, no resource limits relaxed.
- New private test-only workflow: 30 cases, fresh IDs/key, separate outputs and
  permissions checked; **no actual human review or approval**.

Frozen source/labels remain Phase 2C's 30-doc/210-provision/131-role engineering
corpus, SHA `cd7f039bda844d7165b66715369e632ca94ebd634895b20647013a4f19cbb682`.
No retrospective gold changes or independent-expert claims were made.

| Measure | Existing role_v2 | Precision corrections |
| --- | --- | --- |
| Historical strict beneficiary F1 | .722222 | .722222 |
| Literal beneficiary mention accuracy | 36/36 | 36/36 |
| Verified definition-equivalence subset | 10/10; 26 unresolved canonical identities | 10/10; 26 unresolved canonical identities |
| Strict full tuples | 118/131 | 121/131 |
| Separately equivalence-aware full tuples | 128/131 | 131/131 |
| Arabic رد subset | 1/3 | 3/3 |
| Exact object spans | 114/115 | 115/115 |
| Accepted source spans | 1,711/1,711 | 1,823/1,823 |
| Unsupported-claim probes | 60/60 rejected | 60/60 rejected |

The beneficiary policy change is separate from strict extraction accuracy: ten
differences were valid defined names versus role labels. Exact role-label matches
without definitions are not verified canonical entities. Small controlled perfect
scores are not general Arabic/legal accuracy or semantic entailment. New unseen
regressions test ambiguity, wrong parties, scopes and object attachment separately.
All language/category/complexity metrics, strict errors and policy hash are retained.

| Core mode (100 samples) | p50 ms | p95 ms | p99 ms | CPU seconds | Python peak bytes | Process peak RSS KiB | Retained growth bytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| role_v2 | 4.358245 | 5.158831 | 5.477068 | 1.838805 | 166248 | 22264 | 74649 |
| precision_v3 | 4.435790 | 5.578412 | 5.845406 | 1.900461 | 139561 | 22648 | 74908 |

Local HTTP burst returned {'200': 32, '429': 8}; p50/p95/p99 and scope/limits are detailed in the performance report. All 20 stress outcomes matched expectations. No genuine provider/database performance was measured.

## External outcomes and readiness

Independent held-out evaluation: **NOT_RUN — INDEPENDENT HELD-OUT DATASET NOT PROVIDED**.
Actual lawyer assessment/IAA/adjudication: **NOT RUN**, legal review **NOT APPROVED**.
**BLOCKED — LIVE GEMINI VALIDATION NOT EXECUTED**.
**BLOCKED — LIVE SUPABASE / REAL E5 VALIDATION NOT EXECUTED**.

Credentials, required packages and verified nonproduction/project configuration
are absent. Preflight/harnesses stopped without network/provider requests; no model
was loaded. Presence would not establish authorization. Unit fakes and the local
timeout surrogate are not genuine provider results. Compatible SDK/cache/project
role and actual approved fixtures must be supplied and verified externally.

The local production Next.js audit observed anonymous proxy clause-analysis and
archive-overview 200, versus direct unauthenticated backend 401. The service token
stayed server-side, but user authorization was not established. Different-request
isolation does not establish tenant/session ownership. No real client data was used.
Public deployment remains **BLOCKED** pending authenticated ingress, operation/
tenant/session authorization, compatible body/time limits, distributed quotas and
independent privacy/access validation.

Engineering readiness is **PASSED_EXECUTED_SCOPE**. Live readiness is **BLOCKED**.
Legal readiness is **NOT_APPROVED**. Public readiness is **BLOCKED**. These are
independent categories, never one production-ready boolean. See the 31-gate matrix
for PASSED/BLOCKED/NOT RUN outcomes; none of the unavailable validations is PASSED.

## Remaining work and operator decisions

Obtain genuine separately authored source/gold, externally verify two qualified
reviewers and independent origin, approve sanitized source access, distribute
source-first/candidates separately, collect and adjudicate real submissions before
controlled unblinding. Self-attestation is not software verification of a license.
Keep private files under separate OS accounts/ACLs; one coordinator user can read
its own key. Gitignore is not access control or historical erasure.

Configure authorized nonproduction credentials/project identity, compatible SDKs,
cached real e5 weights and explicit budgets/prices, then execute and inspect live
results. Opaque backend-role credentials currently fail closed until a supported
verification interface exists. Model API success, usage estimates or retrieved
quotes never establish correct law, liability or enforceability.

Continue testing unknown grammar/aliases, multi-instrument scopes, Arabic senses,
preposition attachment and wider untouched bilingual materials. Existing mobile
workspace overflow is unchanged. The next step is controlled external evaluation
and authorization/privacy closure, not public deployment or further feature expansion.

No main-branch change, merge, force push, deployment, environment publication,
production SQL/data/secret mutation, real-client upload or public review portal
occurred. Temporary local test servers were stopped. Only the designated branch
is used for delivery.

## Exact file inventory

Created: 42. Modified: 8. Deleted retired synthetic packet files: 5.

### Created

- `benchmarks/phase2d/comparison.json`
- `benchmarks/phase2d/gemini-status.json`
- `benchmarks/phase2d/heldout-status.json`
- `benchmarks/phase2d/http.json`
- `benchmarks/phase2d/performance.json`
- `benchmarks/phase2d/preflight.json`
- `benchmarks/phase2d/proxy-audit.json`
- `benchmarks/phase2d/readiness.json`
- `benchmarks/phase2d/review-workflow-status.json`
- `benchmarks/phase2d/stress.json`
- `benchmarks/phase2d/supabase-status.json`
- `benchmarks/roles/review-packet/RETIREMENT.json`
- `clause_intelligence/identity.py`
- `clause_intelligence/precision.py`
- `docs/phase2d-acceptance.md`
- `docs/phase2d-architecture.md`
- `docs/phase2d-beneficiary-and-arabic-accuracy.md`
- `docs/phase2d-blinded-evaluation-security.md`
- `docs/phase2d-completion-report.md`
- `docs/phase2d-held-out-evaluation.md`
- `docs/phase2d-lawyer-assessment.md`
- `docs/phase2d-live-integration.md`
- `docs/phase2d-performance.md`
- `docs/phase2d-privacy-authentication.md`
- `scripts/phase2d_http_validation.py`
- `tests/validation/__init__.py`
- `tests/validation/test_guards.py`
- `tests/validation/test_precision.py`
- `tests/validation/test_review.py`
- `validation/__init__.py`
- `validation/benchmark.py`
- `validation/dataset_cli.py`
- `validation/datasets.py`
- `validation/live.py`
- `validation/live_worker.py`
- `validation/performance.py`
- `validation/preflight.py`
- `validation/private.py`
- `validation/provider_bounds.py`
- `validation/readiness.py`
- `validation/review_cli.py`
- `validation/secure_review.py`

### Modified

- `.env.example`
- `.gitignore`
- `README.md`
- `benchmarks/roles/review_packet.py`
- `benchmarks/roles/runner.py`
- `clause_intelligence/config.py`
- `clause_intelligence/engine.py`
- `main.py`

### Deleted

- `benchmarks/roles/review-packet/coordinator-only/blinding-map.json`
- `benchmarks/roles/review-packet/packet.json`
- `benchmarks/roles/review-packet/review-status.json`
- `benchmarks/roles/review-packet/reviewer-1-empty.json`
- `benchmarks/roles/review-packet/reviewer-2-empty.json`
