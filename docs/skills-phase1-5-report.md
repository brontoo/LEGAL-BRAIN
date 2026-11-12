# Phase 1.5 stabilization report

Implemented 12 November 2026 on `feature/skill-registry-uae-playbooks`, continuing
Phase 1 commit `89e5f7fa26cb6f85f1291d7b2b72611b918d9a2e` after a clean status check,
remote fetch and ancestry verification. Implementation commit:
`94d71072c3d0d8e027be163d4db093de44a0b120`. The final delivery commit is identified
in Git history and the completion message. No merge, deployment, production write or
configuration publication occurred.

## Audit and fixes

Confirmed execution: `/generate` intake → bounded skills activation → existing
system/user messages → graph stream/RAG evidence collector → citation/attribution,
language and second-model review → bounded revision loop → fact/claim/authority/
deadline/rule reports → final SSE document. The graph, Gemini provider, vector
storage, embedding dimensions, database schema and five playbook bodies were
retained. Registry/loader/schema/validator required no demonstrated rewrite.

Resolved defects:

- Removed redundant card-expansion effect resets; existing stable family/id keys
  already reset component state. Moved document-panel loading/reset actions into
  user handlers, preventing synchronous effect-state churn and stale panel data.
- Replaced effect-based persisted view initialization with a hydration-safe
  `useSyncExternalStore` adapter, retaining session choice if storage is blocked.
- Removed unstable memo dependencies, unused callback argument and unnecessary
  ESLint directive. No lint rule was disabled.
- Replaced render-time session ref access with state generated in the submit
  handler. Browser revision submission confirmed a nonempty session ID.
- Replaced Google font build downloads with the same two font families bundled
  unchanged from a pinned official source, with OFL licenses/provenance retained.
- Added backend fail-closed production authentication and production proxy 503
  guard. Docker defaults to production and omits access-query logging.
- Removed RAG query text and raw provider exception payloads from active application
  logging/error responses; retained specific missing-schema guidance.
- Validated explicit IDs before jurisdiction fallback and restricted custom risk
  band labels, closing an arbitrary-text entry into the trusted workflow suffix.
- Reproduced and fixed stale citation/language reports after automatic revision.
  Changed revisions are rechecked by the original verifier; updated reports are
  sent using the same SSE event types before final delivery. Unchanged output
  retains its prior report. Whitespace outside citation blocks is preserved.
- Added bilingual advisory section diagnostics to selected-skill `done` frames.
  Missing labels never edit/reject analysis; failure of diagnostics itself does
  not prevent delivery. Successful flag-off SSE frames remain unchanged.

## Executed validation

| Command/check | Actual outcome |
| --- | --- |
| Before: `python -m unittest discover -s tests -t . -v` | PASSED: 1,209 tests |
| After: same full command | PASSED: 1,299 tests, including 90 new Phase 1.5 tests; no failures/skips |
| Dedicated `tests/acceptance` package | PASSED within full run: 90 tests, including 60 scenario/language/mode tests |
| `PYTHONPATH=. python scripts/smoke_legal_skills.py` | PASSED real FastAPI/Pydantic HTTP with scripted model/storage |
| `PYTHONPATH=. python scripts/compare_legal_skills.py --output <new /tmp file>` | PASSED offline paired harness: 20 scenario/language pairs |
| `python scripts/smoke_frontend_acceptance.py` | PASSED against actual production Next.js server with fictional browser-intercepted API fixtures |
| Actual production proxy requests (separate from browser fixtures) | PASSED discovery, resolution, generated SSE + diagnostics, authenticated upstream; missing-token instance returned 503 |
| `cd frontend && npm run lint` | PASSED: zero errors/warnings |
| `cd frontend && npx tsc --noEmit` | PASSED |
| `cd frontend && npm run build` | PASSED: production compile, type check, prerender and routes complete |
| Bundled font/license digests | PASSED: all five download artifacts match recorded SHA-256 values |
| `git diff 89e5f7f HEAD --check` | Application files PASSED; preserved upstream OFL notices have whitespace warnings |
| Real Gemini/Supabase/embedding integration | BLOCKED: credentials and integration dependencies absent; no live test executed |
| Subjective lawyer quality/current-law acceptance | NOT RUN |
| Exploratory 390px workspace generation | FAILED: existing fixed-width layout puts submit action outside viewport; unresolved |

The first browser attempt exposed the narrow-mobile workspace issue. A subsequent
explicit desktop workspace test passed; it does not replace or erase that mobile
failure. Browser coverage also includes home/chat/credits/library navigation,
Arabic/RTL/dark shell, no remote Google font requests, stored-grid hydration,
open/close/switch document panels, mobile library controls, SSE rendering and
revision session submission. No browser exception occurred during that smoke run.

The complete staged whitespace check reported trailing spaces/blank EOF lines
in the four verbatim upstream OFL notice copies. Those notices are intentionally
preserved byte-for-byte with their recorded source digests. A check excluding only
those four third-party notice paths passes; application source has no whitespace
errors. No license text or expected digest was changed to silence the warnings.

## Comparison and legal verification findings

The committed `skills-offline-comparison.json` records the actual offline paired
run: 20/20 correct skill selections, preserved host prefix/user input, identical
scripted outputs/citation reports, executed authority/review and enabled-only
advisory diagnostics. Outputs are intentionally scripted identically across modes;
this establishes pipeline compatibility, **not improved model reasoning**.

All five skills reach graph messages and the existing review/authority path.
Separate tests force genuine revision-loop calls for each playbook. An adversarial
post-revision citation test initially FAILED, proving that the initial report was
stale; it and the full suite now pass. An existing exact-output assertion also
caught unnecessary trailing-whitespace trimming during the fix; this was corrected
without relaxing the assertion. Existing
citation code verifies available fictional contractual quotations, rejects forged
quotations, flags unsupported articles and leaves missing sources unverified.
The authority layer flags secondary policy/playbook text misused as statutory
material. ADGM/DIFC contexts and conflicts remain distinct. Supported ordinal risk
4×3 gives 12; absent likelihood stays unknown. None of these checks independently
verifies current UAE legislation or proves semantic correctness of model output.

The opt-in live comparison runner sends identical inputs to two differently flagged
loopback backends, refuses redirects/remote origins, requires explicit confirmation
of a nonproduction knowledge base, saves private non-overwriting artifacts, and
leaves subjective lawyer scores null/NOT RUN. Its default mode is offline.

## Security boundaries and unresolved work

Production startup must explicitly set a documented production marker and secure
API_TOKEN; unmarked local development remains compatible. Existing token semantics
and server-side proxy architecture are preserved. A shared service token is not
user authentication: public proxy access still needs ingress authorization. SDK,
hosting and standalone ingestion logs require separate operational review; no
blanket certification of external logging systems is claimed.

Live services are BLOCKED: all required Gemini/Supabase variable names were checked
for presence without printing values; they are absent, as is `.env` and managed
secret configuration. The real Supabase, sentence-transformers and Gemini Python
packages are also absent. Installing them without credentials would not unblock
live validation, and no model download/paid API call was attempted.

Qualified UAE counsel must evaluate real paired outputs using the scenario-specific
checklist and scorecard, including jurisdiction, authority identity/applicability/
force, omissions and proposed wording. Diagnostic labels are heuristic and cannot
approve a document. The small-screen workspace issue and complete accessibility
review remain outstanding. The technical framework can support scoped Phase 2
work, but production/legal readiness is not granted.

See [acceptance matrix](skills-acceptance-matrix.md),
[scenarios/lawyer template](skills-legal-test-scenarios.md), and
[production settings/live procedure](skills-production-readiness.md).

## Exact changed-file inventory

- `.env.example`
- `Dockerfile`
- `README.md`
- `docs/legal-skills.md`
- `docs/skills-acceptance-matrix.md`
- `docs/skills-legal-test-scenarios.md`
- `docs/skills-offline-comparison.json`
- `docs/skills-phase1-5-report.md`
- `docs/skills-production-readiness.md`
- `docs/skills-provenance.md`
- `frontend/.env.local.example`
- `frontend/AGENTS.md`
- `frontend/app/api/[...path]/route.ts`
- `frontend/app/credits/page.tsx`
- `frontend/app/fonts/amiri/Amiri-Bold.ttf`
- `frontend/app/fonts/amiri/Amiri-Regular.ttf`
- `frontend/app/fonts/amiri/OFL.txt`
- `frontend/app/fonts/noto-kufi-arabic/NotoKufiArabic-Variable.ttf`
- `frontend/app/fonts/noto-kufi-arabic/OFL.txt`
- `frontend/app/fonts/provenance.json`
- `frontend/app/layout.tsx`
- `frontend/app/library/page.tsx`
- `frontend/app/library/view-preference.ts`
- `frontend/app/workspace/page.tsx`
- `frontend/components/office-scene.tsx`
- `frontend/public/fonts/Amiri-OFL.txt`
- `frontend/public/fonts/NotoKufiArabic-OFL.txt`
- `legal_agent.py`
- `main.py`
- `runtime_security.py`
- `scripts/compare_legal_skills.py`
- `scripts/smoke_frontend_acceptance.py`
- `skills/diagnostics.py`
- `skills/risk.py`
- `skills/router.py`
- `smart_office.py`
- `tests/acceptance/__init__.py`
- `tests/acceptance/harness.py`
- `tests/acceptance/scenarios.json`
- `tests/acceptance/test_legal_acceptance.py`
- `tests/test_main.py`
