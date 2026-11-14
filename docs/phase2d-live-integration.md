# Phase 2D controlled live integration

**BLOCKED — LIVE GEMINI VALIDATION NOT EXECUTED.**
**BLOCKED — LIVE SUPABASE / REAL E5 VALIDATION NOT EXECUTED.**

The executable preflight/harness commands ran and stopped without provider access:
credentials, project identity/nonproduction confirmation and integration packages
are absent. No model was loaded or genuine cloud result invented. Test database
configuration is also absent. `benchmarks/phase2d/*-status.json` and `preflight.json`
record these outcomes, with zero provider requests. Presence is not authorization.

```sh
python -m validation.preflight
python -m validation.live --kind gemini --execute --confirm-nonproduction \
  --max-calls 1 --max-cost-usd .01 --timeout 20 --output /private/new-gemini-report.json
python -m validation.live --kind supabase --execute --confirm-nonproduction \
  --max-calls 5 --timeout 30 --output /private/new-retrieval-report.json
```

Operator must separately configure verified `LEGAL_BRAIN_LIVE_ENV=nonproduction`,
approved credentials in secure environment settings and appropriate network access.
No values belong in arguments, logs or Git. The execution flags alone cannot
override missing configuration/dependencies. Commands refuse output overwrite and
repository destinations. Current runtime did not satisfy prerequisites.

## Gemini harness

Only pinned fictional engineering inputs are sent, with the existing Gemini
integration/model configuration; no automatic fallback/provider is added. Runtime
SDK fields are inspected before execution. Missing timeout/retry/output interfaces
fail closed. Actual model ID, installed SDK version, temperature and configuration
are recorded only when exercised. The declared historical model name is not assumed
valid or successfully deployed. No actual SDK/provider interface was live-validated
in this environment because its package is absent.

Maximum three calls, explicit timeout, zero retries and 512 output tokens bound the
evaluation arm. Operator-supplied input/output prices and a positive USD budget
(maximum 5) are required; conservative token reserves gate each attempt. Usage
metadata yields a declared-price estimate when available. Actual billed cost stays
null unless genuinely known; this is not a billing guarantee. Parent wall timeout
kills a stuck worker, while provider-side completion/billing may remain unknown.

Identical inputs also run legacy and role_v2 deterministic analysis. Structured
proposals use the same role fields and strict comparison rules; malformed output,
hallucinated parties, wrong beneficiaries/negation, unsupported legal claims and
invalid quotations are counted. Existing exact spans validate model evidence;
confidence never certifies it. Raw prompts/replies/party text are not saved.
All model proposals remain NOT_ASSESSED and no legal approval is granted.

## Supabase/e5 harness

Separate read-only path does not require initializing Gemini. Confirmed project
reference must match the HTTPS Supabase host, without URL credentials/extra paths.
A JWT backend-role claim/expiry is inspected; that is not signature verification.
Actual server RPC authentication/privileges remain necessary. Opaque keys remain
BLOCKED until a supported independent role-verification path is available; the
harness does not guess their authority.

Only metadata-audit, semantic and lexical RPC names are allowlisted. There is no
table-write/ingestion/migration path. Actual RPC executions are counted and capped
at five (audit plus up to two two-branch queries). Loaded SDK HTTP timeout support
is checked, with a parent hard wall bound. Missing migration/RPC, authorization,
empty sources and technical failures remain distinct observations, not success.

The existing configured e5 identity is read without executing Gemini initialization.
Weights must be locally available: automatic model downloads are disabled. Real
construction, actual 1,024-dimensional finite/nonzero output and loaded dimension
must succeed before claiming model execution. Imports alone never establish loading.
Existing HybridRetrievalEngine applies source, jurisdiction, provenance, temporal
and exact-reference checks. Nonfictional selected sources fail the fixture check;
empty results cannot prove filtering. Known nonproduction fixture expectations
still require operator validation. No real embedding-quality comparison is inferred
from historical synthetic vectors.

Preflight reports only configuration presence and package availability with
READY_FOR_TEST/BLOCKED_MISSING_CONFIGURATION/BLOCKED_MISSING_DEPENDENCY/
BLOCKED_ENVIRONMENT_UNVERIFIED/FAILED_PREFLIGHT. Backend readiness means offline
tests can run with disclosed integration fakes, not that the real application
has all model/database dependencies. No secret, full database URL or confidential
document path is printed. Mock contract and timeout tests are not live results.
