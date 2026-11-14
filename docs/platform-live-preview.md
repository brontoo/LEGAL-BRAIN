# LEGAL BRAIN visual preview

Date: 2026-11-14 (Asia/Dubai).
Branch: `feature/platform-live-preview`.
Verified Phase 2D base: `058f5a5988ae2b4109ccd39e05cc08866c6abf4e` (fetched remote head).

## Delivery status

**BLOCKED for external HTTPS access; locally validated demo. No verified preview URL exists.**
The application was built and exercised locally in a real headless Chromium browser.
The selected Cloud environment has no exposed `open_cloud_preview`, port-forwarding,
desktop JavaScript or viewer-opening tool. Its reported desktop capability does not
establish an accessible preview URL. The user's selected delivery method is private
preview forwarding. No public tunnel was created and no port was made public.

Smallest remaining operator action: make private preview forwarding available for
the running frontend on **port 4010**, using the platform's preview/port controls.
Use authenticated access and supply its generated HTTPS address for verification.
If those controls are unavailable, enable the private-preview capability in this
Cloud workspace. This is an infrastructure capability, not an application setting
that can be activated by choosing the forwarding option in chat. The preview is
session-dependent and must be restarted if the environment stops.

Vercel alternative: securely connect an authorized existing project/team, grant
access to its Preview deployment environment and permit `api.vercel.com` and any
actual deployment hosts through the environment network policy. Do not paste
credentials into chat. No Vercel login files, token, organization/project variables
or `.vercel/project.json` link were present in this checkout/user configuration.
An actual read-only Vercel API request was denied with proxy CONNECT HTTP 403.
Team, project permissions, Git integration, existing deployments, Preview variables
and Deployment Protection therefore remain **UNVERIFIED**, not configured.

No deployment, promotion, domain change, environment publication, merge, backend
startup, model download, production credential use or database change occurred.

## Scope and isolation

`NEXT_PUBLIC_LEGAL_BRAIN_DEMO=true` explicitly enables a public **boolean** build
flag. It defaults off. Set it at build and run time; **rebuild** when changing
modes because Next.js inlines public variables. Do not promote a demo build into
ordinary operation by changing only a runtime variable. Never put service secrets
in `NEXT_PUBLIC_*` variables.

- The actual home, workspace, library/archive, chat and credits pages remain.
  There is no separate archive or statistics route in this revision: archive is
  `/library`; home is the existing dashboard. No replacement landing page was added.
- A persistent Arabic/English Demo Preview notice labels fictional data and warns
  against entering confidential information. Fixtures are deterministic and contain
  no real people, documents, laws, citations or verified legal conclusions.
- Demo browser operations use an in-memory `Response` adapter. Search and sample
  actions make **zero browser API requests** and do not transmit user input.
- Independently, the real Next API boundary dispatches every request locally in
  demo mode, before token validation or upstream fetch. Only fictional archive GETs,
  health and fixed sample drafting/chat responses are allowed. Unknown operations,
  archive writes, uploads, revisions, exports and analysis return 403. Request bodies
  are not read, saved, reflected or forwarded. No Gemini/Supabase backend runs.
- Drafting/chat use read-only fictional prompts. Drafts are explicitly unapproved;
  no legal/source verification is simulated. Editing, saving and clipboard export
  controls are disabled or absent for sample results.
- Ordinary mode continues through the existing proxy with the original server-only
  `API_TOKEN`, backend URL, methods, bodies, queries and streaming response behavior.
  This work does not establish user/tenant authorization for connected deployments.
- Existing Arabic RTL, dark palette, locally bundled Amiri/Kufi fonts, icons and
  desktop design remain. Demo-scoped CSS fixes the mobile sidebar/content collision:
  the original layout left 102 pixels for content at a 390-pixel viewport. Desktop
  and non-demo styles are unchanged.

## Run the isolated preview

Node 24.22.1/npm 11.9.0 were used, consistent with README's tested Node 24 guidance.
From `frontend`:

```sh
npm ci
npm run lint
npx tsc --noEmit
NEXT_PUBLIC_LEGAL_BRAIN_DEMO=true npm run build
NEXT_PUBLIC_LEGAL_BRAIN_DEMO=true npm run start -- --hostname 127.0.0.1 --port 4010
```

Backend credentials are unnecessary. No `.env` file is created or committed.
Use private platform forwarding for port 4010; localhost is not a delivered HTTPS
preview URL. A local working page does not prove remote access or protection.

## Deployment configuration inspection

Root `vercel.json` declares FastAPI and Next.js services and routes its wildcard to
the FastAPI service. It was left untouched; support/routing on an actual authorized
Vercel project could not be established. A successful frontend build is not evidence
that this multi-service configuration is supported or that it serves the frontend.

`frontend/vercel.preview.json` provides an isolated Next.js-only configuration for
an operator to use with an authorized Preview project rooted at `frontend`. Verify
the existing linked project's root/team before deploying; do not create a duplicate
project automatically. Set the demo flag in the **Preview** environment, rebuild,
leave backend credentials absent, and verify Deployment Protection separately.
The file does not configure or claim account-level private access. Never use
`--prod`, promote this build or alter the production project's root/domain settings.

FastAPI is not part of this visual preview. `main.py` imports `legal_agent`, which
initializes the Gemini SDK and imports sentence-transformers/LangGraph/Supabase.
The existing real multilingual-e5-large model needs about 2.2 GB on first load.
These dependencies, weights, credentials, startup and execution constraints require
a separately verified backend environment. They are not assumed to fit a frontend
serverless deployment. No authorized nonproduction backend was configured here, so
connected health/API/end-to-end validation remains **BLOCKED**.

## Reproducible validation

After building Demo mode and starting Next locally, run:

```sh
python scripts/validate_platform_preview.py \
  --url http://127.0.0.1:4010 --output /tmp/legal-preview-new-results
```

Requires Playwright Python and Chromium. For the local upstream-isolation check,
start Next with `BACKEND_URL=http://127.0.0.1:4011` and a fictional canary token,
then add `--local-canary`. The script owns that local canary listener, asserts zero
upstream calls, and shuts it down. No real backend or credential is used.

The same script accepts an actual HTTPS preview URL after private forwarding is
available. Do not bypass protection or report READY before that address has been
tested through the intended user access path.

Executed local results:

- `npm ci`, ESLint, TypeScript and production Demo build passed.
- Existing generate-input contract checks: **45/45 passed**.
- Five routes at desktop 1440×1000 and mobile 390×844: **10/10 passed**, including
  direct navigation, page refresh, RTL/dark rendering, loaded local fonts and assets.
- Both viewports: navigation, fixed drafting sample, library document panel/chunks,
  disabled clipboard controls, and fixed chat interaction passed.
- Zero browser console errors, failed assets or browser API requests. Next's cancelled
  speculative RSC navigation prefetches are counted separately, not missing assets.
- Actual server API boundary: **30 denied operations**, two fixed sample responses,
  filtering and limits passed. Submitted sentinel text was never reflected.
- With a backend URL/token deliberately configured to a local canary: **0 upstream
  requests**, proving the demo guard precedes forwarding.

Ordinary-mode build and proxy guard verification are recorded alongside these
results in `benchmarks/preview/validation.json`. These are local engineering checks,
not external deployment or live legal integration acceptance.

## Source changes

Added demo flag/prompts, fictional fixtures, an in-browser fetch adapter, an explicit
API boundary, a small preview indicator, demo-scoped mobile CSS, an optional frontend
Vercel configuration and browser validation. Existing pages received small conditional
hooks; `.env.local.example` documents the default-off flag. No new authentication
system, legal workflow, UI component framework or production configuration was added.
