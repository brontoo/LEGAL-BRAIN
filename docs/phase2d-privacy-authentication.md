# Phase 2D privacy and authentication audit

**Public deployment readiness: BLOCKED.** No new identity provider, tenant model
or public legal-review portal was introduced. Engineering isolation does not
establish user authorization.

## Concrete local observations

A local production Next.js server with its server-side API_TOKEN forwarded to
real FastAPI/core; external SDKs were faked and all supplied text was fictional.

| Probe without browser authorization | Observed |
| --- | --- |
| `/api/analyze/clauses` through proxy | 200 |
| `/api/archive/overview` through proxy | 200 |
| Direct backend `/analyze/clauses` without token | 401 |
| Oversized proxied analysis request | 413 |

The service token remained server-side, but an anonymous browser still reached
backend operations. No public internet deployment or real client archive was
probed. `benchmarks/phase2d/proxy-audit.json` contains sanitized statuses, no source
content or credentials. Temporary servers were stopped.

The catch-all proxy forwards GET/POST/PUT/PATCH/DELETE using path/query/body and
adds one backend service token. It has no built-in browser user authentication,
per-operation authorization or tenant ownership checks. Backend service-token
comparison is not user identity. The static token has no inherent expiry protocol;
tests of an “expired” fixture token mean an invalid token, not implemented expiry.
The live harness separately rejects expired JWT role claims before access.

Different document/version/ref requests remain isolated in tests. This does not
prove session ownership: caller-supplied session identifiers/shared service access
must be bound to authenticated users before multi-user release. No real cross-client
document or conversation was used. Do not infer tenant isolation from memory maps.

## Required mitigations before public use

1. Authenticate and authorize browser users at a verified ingress or existing
   sanctioned identity boundary before Next.js routes are reachable.
2. Enforce operation-specific permissions, tenant/document ownership and user-bound
   session IDs at a trusted backend boundary. Never trust client identity headers.
3. Apply an explicit route/method allowlist and least-privilege backend credentials.
4. Enforce compatible body limits before proxy buffering, request/provider timeouts,
   distributed user/IP quotas and deployment-wide concurrency/memory budgets.
5. Disable prompt/document/secret logging and tracing in ingress, application and
   SDK infrastructure; review retention and audit only safe access metadata.
6. Independently test unauthorized archive/revision/generation access, revocation,
   rotation, session ownership and privacy using approved fictional fixtures.

The current process-local semaphore remains two admitted clause requests with 429,
not a distributed rate limiter. Next.js buffers request text before backend size
validation; no new matching proxy-side 650,000-byte limit was implemented. The
optional clause model now uses verified SDK request/retry/token bounds, but actual
SDK behavior is untested here and other generation paths retain existing policy.

No actual sensitive documents, full prompts, secrets or confidential paths were
logged by the new validation flow. Provider stdout/stderr is suppressed; artifacts
are allowlisted counts/configuration/status. External subprocess timeout behavior
was tested with a local sleeping surrogate, not a real provider. Source evidence,
fact/authority/jurisdiction/citation checks and cancellation-safe admission remain.

Coordinator/reviewer files use separate external destinations and OS permissions.
Separate accounts/ACLs and controlled human distribution must still be arranged;
one user owning both directories can read both. Gitignore is defense in depth,
not access control or erasure of historical commits. No production access-control
or privacy acceptance was granted by passing engineering tests.
