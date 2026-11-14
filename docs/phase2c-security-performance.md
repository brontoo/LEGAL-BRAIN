# Phase 2C security and local performance

The new flow remains explicitly supplied-text analysis with request-local documents,
evidence and refs. Exact identity/version/hash/offset/quote checks reject invalid
spans. Source content is never executed. Optional model input uses existing fences;
invalid model evidence/JSON is rejected and arbitrary interpretations stay uncertain.
No automatic document upload, arbitrary HTTP/file source loading, production write,
debug endpoint or client-analysis persistence was introduced.

## Endpoint hardening and executed negative tests

- Existing token dependency, constant-time comparison and production auth guard remain.
  Clause analysis still requires a configured token even in development.
- Two process-local admitted requests cover body reading and analysis. Excess demand
  returns **429 / Retry-After: 2**, without an unbounded analysis queue. Cancellation
  of a client task does not free a still-running worker's slot.
- Body limit remains 650,000 bytes; body read now times out after 10 seconds with 408.
  Invalid JSON, recursion, bad document fields/offsets and disconnects return fixed
  sanitized errors. Unexpected internal exceptions return fixed 500 without provider/
  document exception text.
- Model calls reject tracing opt-ins and debug SDK/HTTP logging. Existing model
  configuration/output limits remain. No live SDK confidentiality guarantee is
  inferred from mocked tests; operator tracing/privacy review is still required.
- Tests cover all 16 feature combinations, concurrent document/version/ref isolation,
  malformed/oversized/slow input, injection, invalid model output, unknown actors,
  cancellation/admission and no source content in stdout/stderr/count diagnostics.
- Real FastAPI HTTP smoke exercises both modes, generation citations/SSE/auth, actual
  transport capacity/429 and safe input errors, with external service fakes.
- A local production Next.js server forwarded the nested analysis path and server-only
  token to real FastAPI/v2 core; bilingual negative roles and exact offsets passed.
  Direct unauthenticated backend access returned 401. This was a loopback test, not
  a deployment. Temporary test servers were stopped.

## Unchanged operational boundaries

The shared service token does **not** establish user identity or tenant isolation.
The catch-all frontend proxy adds that token server-side, so deployment requires
authenticated/authorized ingress before Next.js, approved route restrictions,
per-user/IP request quotas, upstream body/time limits and suitable access logging
that excludes document bodies. No new identity provider was introduced.

The 429 behavior is concurrency load shedding, not a distributed/per-user rate
limiter. The two-slot bound is per process and covers admitted analysis work, not
all ASGI response/network buffers or multiple server workers. There is no newly
enforced production process-memory ceiling. Client cancellation deliberately does
not kill worker threads. Long provider calls can occupy slots; deployment must
configure and validate provider/upstream timeouts and capacity. No uncontrolled
production stress test was attempted.

## Input/algorithm bounds

Existing limits remain: 100,000 Unicode code points, 4,000 newline characters,
600 segments, 20,000 characters per segment and 2,000 records per family. V2 also
rejects more than 128 modal frames in one sentence and more than 32 coordinated
actions. Conditional relationships stop at 2,000. Conflicts use a 5,000-comparison /
100-issue budget, explicitly reported when exhausted. No source is silently
truncated to manufacture a successful analysis. Long qualification expressions
retain a bounded source window and candidate/unknown status; no complete semantic
analysis is promised for arbitrary long syntax.

## Executed local stress cases

[stress-results.json](../benchmarks/roles/stress-results.json) records 20 child-
process cases: ten fixtures in each mode. All expected outcomes passed. Cases
cover 99,499-character contracts, 150-level nested labels, mixed scripts/diacritics/
combining marks/emoji, duplicates, repeated definitions and references, long
unpunctuated text, large obligation lists, and excessive paragraphs/documents.

Each disposable child had a 512 MiB address-space cap, 20 CPU-second limit and
30-second parent wall timeout. These caps were **not** applied to the application
or production. Reported CPU/memory failures would fail the run; none occurred.
Oversized paragraphs/documents were rejected in both modes. The dense single-
sentence modal fixture was rejected by v2's additional bound and accepted by legacy.

| Mode / case | Traced time (ms) | Peak Python bytes | Peak RSS (KiB) |
| --- | --- | --- | --- |
| legacy / near_limit | 3840.744720 | 4970632 | 30360 |
| legacy / repeated_definitions | 12621.415652 | 16873207 | 61632 |
| role_v2 / near_limit | 11268.822855 | 8054952 | 37716 |
| role_v2 / repeated_definitions | 5385.504670 | 3300927 | 27124 |

legacy: maximum traced wall 12621.415652 ms; maximum Python allocation 16,873,207 bytes; maximum process RSS 61,632 KiB.

role_v2: maximum traced wall 11268.822855 ms; maximum Python allocation 8,585,719 bytes; maximum process RSS 37,716 KiB.

Elapsed stress timings include tracemalloc overhead and synthetic text; they are
not production throughput. Peak RSS includes interpreter/imports, while Python
traced allocation peaks have a different scope. Shadow-corpus timing/memory uses
small fictional documents and a separate traced run; no real model/WAN/SQL latency
or real-world concurrency capacity is measured. V2 adds validation work; it is not
claimed universally faster or smaller. Load testing, privacy review, provider
timeouts and authenticated ingress remain production release prerequisites.

The Phase 1.5 mobile workspace overflow remains unchanged and is not claimed fixed.
