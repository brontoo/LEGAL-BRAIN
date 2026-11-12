# Phase 2C controlled live validation

**BLOCKED — LIVE GEMINI EVALUATION NOT EXECUTED.**

**BLOCKED — LIVE SUPABASE / REAL E5 VALIDATION NOT EXECUTED.**

Current runtime presence checks found GOOGLE_API_KEY, SUPABASE_URL and SUPABASE_KEY
absent; real `langchain_google_genai`, `supabase` and `sentence_transformers` packages
are absent from the ordinary runtime. Managed-environment status reports no secrets.
No values were printed, requested in chat, copied from other services or edited.
The existing read-only metadata audit command was attempted and returned its safe
BLOCKED prerequisite message before any remote access. Migration state is unknown.

Mocked model/RPC tests and real local HTTP transport validate engineering contracts,
not paid model success, deployed SQL, RLS against a live project or real e5 quality.
Historical disposable Phase 2A SQL results were not counted as new live tests.
Missing infrastructure did not block offline implementation/evaluation.

## Reproducible future nonproduction procedure

1. An authorized operator selects and verifies a dedicated nonproduction project/
   server, approved fictional/sanitized documents and a bounded call budget. Verify
   the project identity outside document content; do not point tests at production.
2. Configure credentials securely in environment settings and install the repository's
   existing integrations in an isolated test runtime. Do not put secrets in chat,
   command arguments, browser variables, logs or committed `.env` files.
3. Inspect the existing Phase 2A migration/RPC/view state read-only. Run:

   ```sh
   PYTHONPATH=. python scripts/audit_retrieval_metadata.py
   ```

   This reports aggregate allowlisted counts only. It does not apply SQL, backfill
   metadata or prove source authenticity. Do not automatically apply migrations or
   seed an archive because the endpoint exists. Any sanctioned nonproduction fixture
   provisioning needs the operator's separate review; no such operation ran here.
4. On identical fictional corpus bytes, compare deterministic legacy and v2 with
   `ENABLE_CLAUSE_ROLE_V2=false/true`. Keep other settings and inputs fixed. Record
   failures, timing, returned source IDs and support statuses, including empty results.
5. For the optional Gemini arm only, explicitly enable
   `ENABLE_CLAUSE_MODEL_ASSISTANCE=true` and request `analysis_mode: "model_assisted"`.
   Use only approved fictional/sanitized text within the documented bound. Current
   existing configuration is `gemini-3.8-flash`, temperature `0.3`; the clause adapter
   bounds output to 2,048 tokens. Record actual deployed SDK/model/configuration rather
   than assuming the current configuration was successfully exercised.
6. Call authenticated `/api/analyze/clauses` through the existing server proxy. Hold
   document ID, version, SHA, language and client role constant. Capture safe result
   artifacts locally; count successful/failed API calls, malformed outputs, hallucinated
   roles, invalid source spans, unsupported interpretations, latency and provider usage/
   cost metadata when available. Do not log full prompts or confidential quotations.
7. Request external research only through explicit `research_query`, with the hybrid
   flag independently enabled and confirmed jurisdiction/as-of context. Verify known
   nonproduction source filtering, source classes, jurisdiction mismatches, unknown
   provenance, missing sources and unavailable-RPC behavior. A drafting precedent
   must not verify law. Unknown provenance remains a lead or is excluded by policy.
8. Reject the run for any accepted fabricated/wrong-version quotation or automatic
   legal approval, regardless of extraction-score gains. Provider confidence never
   determines legal reliability. Route actual legal conclusions through existing
   authority/application checks and qualified UAE lawyer review.

Keep a separate live-result record: project/environment identity (no secrets),
fixture hash, exact model/configuration, call/usage counters, successes/failures,
filter/support checks, model-role errors, costs if known and review status. All
these live result fields are currently **unmeasured**, not zero-cost/success claims.

No live production SQL, ingestion, knowledge-record mutation or client-document
upload was performed. No new model/provider, embedding migration or remote crawler
was added. Production legal acceptance remains ungranted.
