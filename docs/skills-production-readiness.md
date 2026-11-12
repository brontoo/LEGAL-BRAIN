# Production safeguards and readiness (Phase 1.5)

Technical stabilization passes the executed checks. **Production legal acceptance
is not granted.** Live Gemini/Supabase validation is blocked and qualified-lawyer
review remains NOT RUN. No deployment, production data write, schema change,
merge or environment publication occurred.

## Authentication configuration

Development remains compatible: an unset `API_TOKEN` is allowed when no production
marker or explicit requirement is set. Existing configured-token bearer protection
is unchanged for generation, chat, archives, revisions and both skills endpoints.

Set `APP_ENV=production` in every production backend deployment and configure a
nonempty `API_TOKEN` securely. `ENVIRONMENT=production`, `NODE_ENV=production`, or
`REQUIRE_API_TOKEN=true` also require authentication. Any production marker wins
over a conflicting development marker. The backend fails import/startup with a
fixed, value-free error when required authentication is missing. Values are never
included in this error. An unmarked server cannot infer whether its operator
considers it production: explicit deployment configuration remains required.

The Dockerfile now defaults to `APP_ENV=production` and disables Uvicorn access
logs so query strings containing document names/search text do not enter those
logs. For a non-container production launch use:

```bash
# Supply API_TOKEN using deployment secret management, not this command line.
APP_ENV=production uvicorn main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Next.js production proxy requests return 503 before contacting the backend if
its server-side `API_TOKEN` is empty. Build does not require a token. At runtime
set the same token in backend and Next.js server environments, with **no
NEXT_PUBLIC_ prefix**. The existing server-side proxy still adds the bearer
header; browser code never receives it. Proxy connection failures use a generic
message and do not expose internal backend URLs or exception payloads.

**Authorization limit:** this shared backend token is service authentication,
not user authentication or tenant isolation. Anyone allowed to use an otherwise
public Next.js proxy can invoke its authorized backend operations. Restrict access
to the frontend and backend at ingress/VPN/access gateway before external use.
No new identity provider or multi-tenancy was introduced.

## Confidentiality and diagnostics

RAG tool logs no longer include queries. Application failure logs retain only
operation context and exception class, not provider messages, prompts, documents
or credentials. Unexpected provider errors sent over SSE/chat/storage responses
are also sanitized. Known schema-missing guidance remains specific. Input
validation messages remain useful to the authenticated submitter; they are not
application logs. CLI tools intentionally displaying a requested document are
interactive output, not a protected audit-log sink.

Keep SDK/HTTP wire debugging disabled and configure reverse-proxy/hosting logs to
omit bodies, authorization headers and sensitive query strings. External logging
systems and standalone ingestion utilities were not comprehensively certified;
this work verifies the generation/review/tool application paths under test.

Skill identifiers and jurisdiction metadata are validated. Explicit IDs are now
validated even if a case is already jurisdiction-incompatible. Risk band labels
are bounded machine identifiers (`[a-z][a-z0-9_]{0,31}`), preventing arbitrary
multiline instructions from entering the trusted workflow suffix. Existing path,
symlink, remote-loading and arbitrary-execution protections remain active.

Selected workflows add an advisory `skill_diagnostics` object to the existing
`done` SSE frame. It records observed/missing expected section labels, not source
text, legal correctness, completeness, enforceability or approval. Arabic and
English aliases are supported. Missing labels do not edit/reject the document;
diagnostic failures return `status: unavailable` and still deliver the document.
Flag-off frames omit the object. Current frontend clients safely ignore it.
After an automatic revision actually changes the draft, the original citation
verifier and language checker run again. Updated `citations` and `language` frames
replace earlier reports before delivery; consumers must use the latest frame of
each type, as the existing frontend does. No new event type or verifier is added.
Unchanged drafts retain their original citation report.

## Fonts and frontend

Amiri regular/bold and variable Noto Kufi Arabic are bundled unchanged from
`google/fonts` commit `c30b221beb0c1da59d563feb91ec8656a1fa972a` via verified HTTPS.
Both families permit redistribution under SIL OFL 1.1, reviewed before inclusion.
Family notices are beside assets and publicly linked from Credits. Source URLs,
SHA-256 digests and sizes are in `frontend/app/fonts/provenance.json`.
`next/font/local` preserves the two-family visual design. No Google font network
request is needed during build or runtime. No font package/dependency was added.

Lint, TypeScript, production build, real production proxy requests and desktop UI
smoke checks passed. Mobile library controls passed at 390px. During exploratory
mobile workspace testing, the existing fixed-width layout put the generation
button outside the viewport. No layout change in this phase caused or fixed it;
full mobile workspace acceptance remains unresolved. Do not treat desktop smoke
coverage as proof of complete responsive accessibility.

## Controlled live validation procedure

Current instance status: **BLOCKED**. `GOOGLE_API_KEY`, `GEMINI_API_KEY`,
`SUPABASE_URL`, and `SUPABASE_KEY` are absent; there is no repository `.env` file
or configured managed secret binding. Real `supabase`, `sentence_transformers`
and Gemini integration packages are also absent from the current Python runtime.
No live model, embedding download, production token or database was used.

1. Prepare the repository's documented dependencies in a development environment
   using its existing `requirements.txt` (including CPU torch where appropriate).
   Do not alter model dimensions or database schema for acceptance testing.
2. Configure authorized **nonproduction** Gemini and Supabase credentials securely.
   Use a dedicated sanitized/fictional knowledge base with read-only retrieval;
   inspect sources before allowing queries. Do not reuse production credentials
   or client records. Confirm applicable network access separately.
3. Start two backend processes on loopback with identical model/settings,
   knowledge base, token and code revision. Set `ENABLE_LEGAL_SKILLS=false` for
   port 18001 and `true` for port 18002. Both should use `APP_ENV=production`
   for checking the guard and `--no-access-log`. Verify `/health` and protected
   `/skills` responses. No ingester or write endpoint is needed.
4. Run one fictional scenario/language pair first (two generations; existing
   review/revision may make additional model calls). Explicitly confirm the
   nonproduction dataset, then run:

```bash
LEGAL_ACCEPTANCE_NONPRODUCTION=true PYTHONPATH=. python scripts/compare_legal_skills.py \
  --live --scenario 01 --language en \
  --original-url http://127.0.0.1:18001 \
  --skilled-url http://127.0.0.1:18002 \
  --output /tmp/legal-acceptance-live-01-en.json
```

5. The runner only accepts loopback origins, refuses redirects with credentials,
   checks server flags, sends identical bodies to both modes and refuses to
   overwrite prior output. It writes results with mode 0600. Keep outputs outside
   Git. Inspect actual citation/authority/review/revision frames; an HTTP 200 alone
   is not evidence of legal correctness. A generation error is a failed run.
6. Only after reviewing the first result, repeat the other scenario IDs/languages
   as needed. Model stochasticity remains; identical settings do not guarantee
   identical output. Do not infer improvements from one unblinded pair.
7. Complete the [lawyer scorecard](skills-legal-test-scenarios.md). Record official
   sources/applicability/current-force evidence for any legal conclusion. Missing
   authoritative material remains unverified. No fixture or rubric approves law.

The default comparison command is offline and cannot establish model quality:
`PYTHONPATH=. python scripts/compare_legal_skills.py --output /tmp/offline-run.json`.

Phase 2 may use the validated local framework. Before public/production use,
complete live validation, lawyer acceptance, ingress authorization review, and
mobile workspace/accessibility validation.
