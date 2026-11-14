# Hybrid retrieval benchmark — executed results

Executed against a local disposable PostgreSQL 16.12 / pgvector 0.8.1 instance.
**100 queries (50 Arabic, 50 English), 300 fictional rows, five families.**
Actual PostgreSQL vector/lexical functions and production Python fusion/eligibility/
evidence code ran. Vectors are deterministic 1024-dimensional SHA-feature fixtures,
**not multilingual-e5 outputs**. No live LLM, source corpus or legal-quality gain is claimed.

## Metrics

| Mode | Recall@K | Precision@K | MRR | nDCG@K | Hit rate | Mean measured ms |
| --- | --- | --- | --- | --- | --- | --- |
| semantic_only | 0.550000 | 0.375000 | 0.525000 | 0.517300 | 0.600000 | 0.993670 |
| hybrid | 1.000000 | 0.700000 | 1.000000 | 1.000000 | 1.000000 | 5.461530 |
| hybrid_strict | 1.000000 | 0.700000 | 1.000000 | 1.000000 | 1.000000 | 4.673170 |

K uses the original per-family final cap (legislation 3, drafts 2, contracts 4,
notices 3, POA 3). Precision uses a fixed K denominator, including short lists.
There are two relevant eligible rows per query. Precision below 1 is expected
when K>2; returned research leads/irrelevant extras remain false positives under
the strict relevance definition, even when safely labeled unverified. No query
with an eligible target is omitted. The runner does not alter ground truth.

Both hybrid modes achieved 1.0 jurisdiction exclusion, legal exclusion, fixture
provenance-status accuracy and displayed citation-evidence integrity. Legacy
semantic-only exclusion accuracy was 0.1; provenance/evidence bridge metrics for
legacy mode are NOT RUN/null, not invented failures or successes. Existing legacy
citation behavior is covered separately by the regression suite.

| Language | Queries | Semantic Recall@K / MRR | Hybrid Recall@K / MRR |
| --- | --- | --- | --- |
| ar | 50 | 0.550 / 0.525 | 1.000 / 1.000 |
| en | 50 | 0.550 / 0.525 | 1.000 / 1.000 |

Per-family and jurisdiction breakdowns, per-query rankings/metrics, false positives,
false negatives, operational diagnostics and regression IDs are in
[`benchmarks/hybrid/results.json`](../benchmarks/hybrid/results.json). Final default
hybrid had 0 recall regressions against the measured baseline.

## Design and measurement limits

- `fixture.json` is frozen/versioned; its authoring script refuses overwrite.
  Labels distinguish relevant eligible, relevant ineligible, relevant unverified,
  and default irrelevant. Raw numbers, wrong regimes, expired sources, policies,
  missing provenance, exact references, paraphrases, titles, normalization and
  embedded prompt injection are covered. Unreturned evidence is tested through
  the real citation verifier after the final displayed bridge.
- Synthetic semantic features represent family/topic, intentionally creating hard
  semantically similar confusers. SQL cosine distance and FTS are actually computed;
  no adapter returns scripted per-query rankings. This controlled space cannot
  establish real e5 accuracy, Arabic morphology or generalization to client corpora.
- The original semantic-only RPC uses its original threshold/count and ordering.
  Legacy cosine ties/ANN details can depend on the database version/plan. Inputs,
  fixture vectors, labels, metric formulas and new fusion tie-breaking are fixed;
  the published artifact records one executed pinned-database run, not a guarantee
  of identical legacy tie order on every platform.
- Initial measured baseline was inspected before setting acceptance: hybrid recall
  and nDCG must not regress in aggregate; legal/provenance/citation invariants must
  pass 100%. Labels were not changed. A separately configurable metadata preference
  prevents unverified leads crowding equally exact compatible sources. Its RRF
  score remains the standard rank sum; see architecture for ordering details.
- Earlier test failures were corrected: SQL syntax/parenthesis issues during
  development, stale test-role privileges on repeat runs, invalid-metadata parity
  fixture handling and fake-encoder cache isolation. Final 20 database checks pass.
- A preliminary provenance metric incorrectly counted an irrelevant unknown source
  as a status error; it was corrected to compare provenance independently of topical
  relevance. Final status accuracy uses the frozen corpus metadata, not altered labels.
- Mean timings are tiny warm-cache local measurements. Semantic-only measures its
  SQL call; hybrid additionally includes adapter validation/fusion. Synthetic query
  vectors are precomputed. Real embedding generation, Supabase WAN latency, large
  tables, cold caches, role timeouts and LLM cost are NOT RUN. Per-query branch,
  fusion, total and displayed/context size counters are provided; no production
  throughput or latency claim follows.
- Legal relevance labels and positive review flags are fictional test inputs, not
  certification of instruments, current law, court jurisdiction or human acceptance.

## Reproduction

Use the disposable procedure in [migration guide](hybrid-retrieval-migration.md).
The optional driver requires psycopg; the standard unit suite requires no database,
network, model download or API credit. The test driver applies the reviewed migration
and seed data only after explicit disposable acknowledgement and a loopback/database
name guard. It refuses output overwrite.

Fixture SHA-256: `1eb0150c7e67142932a5d2bba5b7ab2f35714e91da1060774a517cb48a3a0492`.

Legal NLP methodological references and licensing are recorded in
[legal safeguards](hybrid-retrieval-legal-safeguards.md). No linked research dataset
or model was downloaded or added to the knowledge base.
