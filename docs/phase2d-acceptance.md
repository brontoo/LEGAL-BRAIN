# Phase 2D acceptance record

Date: 2026-11-13 (Asia/Dubai). PASSED means executed engineering scope, not legal
approval or live cloud success. Unavailable external validation is not PASSED.

| Gate | Status | Evidence |
| --- | --- | --- |
| AC-01 branch/ancestry | PASSED | Existing designated branch, `81f34abcb1973394a5db2c6328d5e01ae4f614a8` ancestry verified |
| AC-02 baseline | PASSED | Actual 1,540 tests before changes |
| AC-03 compromised packet | PASSED | Retired IDs/generator, current exposed packet/key removed, history exposure documented |
| AC-04 secure preparation | PASSED | Crypto default, test-only determinism, fresh IDs, new destinations |
| AC-05 external key | PASSED | Git-tree/symlink/overlap rejection, owner-only permissions, no key in visible outputs |
| AC-06 independent submissions | PASSED | Separate slots, origin confirmation, original revisions preserved |
| AC-07 review states | PASSED | Completion, invalid, disagreement, adjudication and unblinding tests |
| AC-08 no fabricated humans | PASSED | Actual review NOT RUN; fictional tests explicitly marked and never count as human outcomes |
| AC-09 identities | PASSED | Surface/role/canonical/definition/ambiguity fields, wrong-party/scope tests |
| AC-10 scoring | PASSED | Historical strict, literal surface and separately versioned equivalence scores retained |
| AC-11 Arabic | PASSED | Known plus unseen contextual رد tests, unresolved cases abstain |
| AC-12 object boundaries | PASSED | Direct object/recipient/destination/qualifier, Arabic/multi-preposition tests |
| AC-13 evidence | PASSED | 1,711/1,711 baseline and 1,823/1,823 precision spans valid in new comparison |
| AC-14 legal safety | PASSED | 60/60 unsupported-claim probes rejected per mode; existing attacks/regressions retained |
| AC-15 external interface | PASSED | Offline format, provenance, hash/overlap/freeze/no-mutation tests |
| AC-16 independent held-out | NOT RUN | No actual independently supplied corpus |
| AC-17 lawyer assessment | NOT RUN | No actual reviewer submissions or approvals |
| AC-18 Gemini live | BLOCKED | Harness/preflight executed; no authorized available prerequisites/provider calls |
| AC-19 Supabase/e5 live | BLOCKED | Harness/preflight executed; no authorized available prerequisites/model loading |
| AC-20 mock distinction | PASSED | All fakes/local surrogate results explicitly labeled |
| AC-21 preflight | PASSED | Presence/package-only run, no secrets/URLs/doc paths printed |
| AC-22 auth boundaries | PASSED audit | Actual local anonymous proxy 200/direct backend 401; public release BLOCKED |
| AC-23 performance | PASSED local scope | Core/HTTP/concurrency/memory/CPU and 20 bounded stress cases |
| AC-24 infrastructure | PASSED | Full skill/retrieval/evidence/revision regressions and HTTP generation checks |
| AC-25 flags | PASSED | Existing defaults retained; new precision flag default off; 32 configurations tested |
| AC-26 Python | PASSED | Final 1,584 tests, 44 added; no failures/skips |
| AC-27 frontend | PASSED | Lint, TypeScript, production build exit 0; no UI redesign |
| AC-28 reports | PASSED | Ten reports, artifacts and exact inventory |
| AC-29 boundaries | PASSED | No merge/deploy/production mutation, secrets change or confidential upload |
| AC-30 Git delivery | PASSED at delivered head | Implementation SHA and verified designated-branch push in final response/history |
| AC-31 readiness separation | PASSED | Engineering scoped PASS; live BLOCKED; legal NOT APPROVED; public BLOCKED |

Commands actually executed: full unittest discovery before/after; focused
`tests/validation` discovery; `validation.benchmark`, preflight, guarded live
commands, external-evaluation NOT_RUN path, private test-packet generation/status,
core performance, local HTTP validation, bounded stress, compile checks and
`git diff --check`. Frontend lint/tsc/build and a local production-proxy audit ran.

Earlier unseen mixed-object testing exposed an Arabic conjunction classification
bug; it was fixed and tests rerun. No gold label was altered. No final required
local check is failing. There is no actual independent disagreement statistic,
live SDK/model/DB acceptance, public authorization acceptance or legal approval.
