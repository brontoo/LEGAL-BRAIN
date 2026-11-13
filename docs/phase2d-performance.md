# Phase 2D bounded local performance

Executed artifacts: `benchmarks/phase2d/performance.json`, `http.json`, `stress.json`.
All inputs are fictional; all measurements are local. No genuine database/model
latency or production scalability is measured.

| Core mode (100 samples) | p50 ms | p95 ms | p99 ms | CPU seconds | Python peak bytes | Process peak RSS KiB | Retained growth bytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| role_v2 | 4.358245 | 5.158831 | 5.477068 | 1.838805 | 166248 | 22264 | 74649 |
| precision_v3 | 4.435790 | 5.578412 | 5.845406 | 1.900461 | 139561 | 22648 | 74908 |

HTTP (100 sequential samples): p50 9.129021 ms, p95 11.603096 ms, p99 14.606005 ms.
Four-thread bounded burst: 40 requests, status counts {'200': 32, '429': 8}, 148.351062 requests/second.
Local slow-child timeout surrogate: 0.050792 seconds; genuine provider timeout test BLOCKED.
Two-thread core throughput, role_v2: 209.177834 requests/second over 20 calls.
Two-thread core throughput, precision_v3: 187.776180 requests/second over 20 calls.

Core: 100 sequential samples per mode on the same short bilingual input, plus a
separate traced allocation run and 20 calls through two Python threads. RSS is
process-lifetime high-water, not incremental per-request memory. Retained growth
over 30 measured repetitions includes Python/regex caches and is not proof of a
memory leak or absence of leaks. CPU includes the local measurement work.

HTTP: actual FastAPI transport and core, with external integrations faked. The
32 subsystem/role/precision combinations passed, with existing generation citations,
SSE, auth, input and capacity checks. p99 from 100 samples is a coarse descriptive
order statistic, not a reliable tail-latency SLA. The four-thread burst is bounded
and exercises admission rejection, not distributed quotas.

The local sleeping-child timeout surrogate was terminated as expected. This proves
the parent subprocess wall bound, not a real provider timeout or billing outcome.
Active worker cancellation/admission behavior is also covered by regression tests.

Twenty disposable stress cases reused Phase 2C fixtures with precision explicitly
requested. Legacy rows ignore it; role_v2 rows execute the new precision corrections.
All expected accepts/rejections passed: near 100,000-character source, deep nesting,
mixed Unicode/diacritics/emoji, duplicate labels, repeated definitions/references,
long paragraphs, dense obligations and excessive input. Child bounds remain
512 MiB address space, 20 CPU seconds, 30 wall seconds. They are not application
or production memory limits. Existing input bounds were not relaxed.

| Stress mode | Maximum traced ms | Peak Python bytes | Peak RSS KiB |
| --- | --- | --- | --- |
| legacy | 11102.410775 | 16874259 | 61968 |
| role_v2 | 12921.757603 | 9343665 | 39988 |

No uncontrolled production load test ran. Actual provider load/cost, realistic
archive queries, long-running deployment memory, authenticated multi-user quotas,
cross-worker admission and production traffic remain BLOCKED/NOT RUN prerequisites.
