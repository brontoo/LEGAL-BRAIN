# Manual Phase 2A migration and rollback

**Production migration status: NOT EXECUTED.** Application startup never runs DDL.
The SQL files were executed only in a fresh disposable database with fictional
records. Review/backup/authorization are separate operator prerequisites.

## Preconditions and additions

Use PostgreSQL >=15 (for an invoker-security view), compatible pgvector exposing
`vector_norm(vector)`, and the five existing `public.legal_*` knowledge tables with
`vector(1024)` embedding columns and the documented JSONB metadata/text columns.
The migration explicitly rejects an incompatible platform/dimension and never
upgrades an extension or changes an embedding column. Tested: the versions recorded
in `benchmarks/hybrid/results.json` using pgvector image
`pgvector/pgvector:0.8.1-pg16@sha256:33198da2828a14c30348d2ccb4750833d5ed9a44c88d840a0e523d7417120337`.

`migrations/phase2a_hybrid_retrieval.sql` adds:

- Six v1 normalization/date/metadata/filter/exact-reference helper functions.
- An invoker-security union view over the five existing families.
- `hybrid_semantic_v1`, `hybrid_lexical_v1`, `hybrid_metadata_audit_v1`.
- Five normalized `simple` FTS GIN indexes and fifteen structured-reference B-tree
  expression indexes (article, clause and instrument per table).

It does not change original text/metadata, tables, vectors, HNSW indexes, RLS
policies or the five `match_legal_*` signatures/semantics. No new database is
required for normal application operation. The feature flag remains off.

New view/RPC/helper access is revoked from PUBLIC. Existing `service_role`, if
present, gets new-function execution and view access; base-table privileges and
RLS still govern reads. No anonymous/authenticated policies are introduced. Review
custom backend/ingestion roles explicitly: expression indexes invoke the normalizer,
so existing authorized writer roles may need narrow EXECUTE grants. Do not grant
broad table permissions or disable RLS to make retrieval pass. Existing service-role
bypass must remain a conscious deployment choice.

## RPC contracts

| Function | Arguments | Returns |
| --- | --- | --- |
| `hybrid_semantic_v1` | `p_family`, `p_embedding` vector(1024), `p_threshold`, `p_limit` 1..100, `p_filters` | Original ID/title/type/passage/metadata plus cosine similarity |
| `hybrid_lexical_v1` | `p_family`, `p_query` <=20000 chars, `p_references` <=16, `p_limit`, `p_filters` | Original ID/title/type/passage/metadata, `lexical_score`, `exact_match` |
| `hybrid_metadata_audit_v1` | Allowlisted `p_family` | Aggregate counts only |

Families are `legislation`, `drafts`, `contracts`, `notices`, `poa`. Filters contain
only `jurisdiction`, optional ISO `as_of`, and `unknown_policy` (`research_lead` or
`exclude`). Exact references use allowlisted kinds and validated numeric paths;
year-specific instruments use `12:2020`. Values are parameters, never executable
SQL or dynamic table names. Both search functions apply eligibility before LIMIT.

## Authorized deployment sequence (manual)

1. Confirm the target, backup, extension/version, base schema, authorized roles,
   RLS behavior, available disk and a maintenance window. Do not apply `schema.sql`
   as an upgrade/rebuild on production.
2. Review the entire additive migration and test it against a sanitized clone.
   Normal CREATE INDEX can lock writes and scan large tables. Index size/build time
   and actual plans have not been measured on the production corpus. A DBA may
   stage equivalent CONCURRENTLY indexes separately outside this transaction.
3. Apply the reviewed migration using existing secure database authentication,
   e.g. `psql "$AUTHORIZED_DB_DSN" -v ON_ERROR_STOP=1 -f migrations/phase2a_hybrid_retrieval.sql`.
   Never put secret values in chat, Git or logs. This action is not performed by Codex.
4. Verify the three RPC signatures, nine function security/grants, invoker view,
   five GIN/fifteen B-tree additions, original HNSW indexes, and old RPC definitions.
   Test under the actual backend role and an unauthorized role with fictional data.
5. Run the aggregate audit; review incomplete provenance before enabling stricter
   legal scopes. No automatic migration/backfill follows a missing-RPC error.
6. Configure query/caller timeouts and evaluate production-sized plans. ANN filters
   may underfill pools; common FTS terms can be expensive. Do not infer operational
   performance from the tiny test corpus.
7. Enable `ENABLE_HYBRID_LEGAL_RETRIEVAL=true` only for a controlled nonproduction
   rollout first. Skills remains independently configurable. Verify actual evidence,
   degraded failure states and authority checks with qualified reviewers.

Repeated application is tested. Future changes to an immutable normalization
expression require a new index/function version or planned index refresh; changing
an immutable function alone does not rebuild stored expression-index keys.

## Dry-run provenance audit and backfill proposal

With authorized read-only configuration and installed existing Supabase dependencies:

```bash
PYTHONPATH=. python scripts/audit_retrieval_metadata.py
```

It calls only the aggregate audit RPC and rejects unexpected/raw result fields.
Counts cover known/unknown declared governing jurisdiction, source URL presence,
instrument IDs, temporal metadata and manual-review needs. Counts describe metadata
presence/review flags, not certified legal accuracy. No document text/URL/ID is printed.

Proposed backfill is a separate authorized job: export an access-controlled review
inventory; verify official source identity, classification, six-dimensional scope,
versions and dates; retain provenance evidence; update only reviewed JSONB entries
transactionally with an audit trail. Re-audit aggregates and test before enabling
strict mode. Never derive current force or official status from a table name, upload
age, document title or similarity. No real backfill or reingestion occurred here.

## Rollback

First turn the hybrid flag off and restart workers. Legacy retrieval needs no new
objects. After reviewing dependencies, run the separate
`migrations/phase2a_hybrid_retrieval_rollback.sql`. It removes only v1 new RPCs,
view, indexes and helpers without CASCADE; it never drops knowledge tables, data,
HNSW indexes or old matching functions. New objects can also be left installed with
the flag off. Rollback and reapplication were tested in the disposable database.

## Reproduce the disposable integration suite

Never use production or a tunneled production endpoint. The runner requires explicit
acknowledgement, a loopback DSN, and database name `legal_brain_test`. It TRUNCATES
that disposable fixture database's five tables, so use only a fresh test instance.

```bash
docker run -d --rm --name legal-brain-phase2a-pg \
  -p 127.0.0.1:15432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust \
  -e POSTGRES_DB=legal_brain_test pgvector/pgvector:0.8.1-pg16
# Wait for pg_isready, then initialize the disposable baseline only:
docker exec -i legal-brain-phase2a-pg psql -U postgres -d legal_brain_test \
  -v ON_ERROR_STOP=1 < schema.sql
docker exec legal-brain-phase2a-pg psql -U postgres -d legal_brain_test \
  -c 'create role service_role; create role anon;'
python -m venv /tmp/legal-brain-db-test
/tmp/legal-brain-db-test/bin/pip install 'psycopg[binary]==3.2.13'
PYTHONPATH=. /tmp/legal-brain-db-test/bin/python scripts/test_hybrid_database.py \
  --acknowledge-disposable --output /tmp/new-hybrid-benchmark.json
docker stop legal-brain-phase2a-pg
```

The trust setting is for a loopback-only, short-lived fictional test database, not
a production authentication recommendation. No database is exposed as a preview.
The twenty executed checks include migration repetition, original RPC fingerprints,
all families, GIN plans, normalization, exact/year identities, SQL/Python eligibility
parity, permissions/RLS, audit aggregates, original text and rollback/reapplication.
