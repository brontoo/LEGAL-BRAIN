# Phase 2D blinded evaluation security

The committed Phase 2C assignment map compromised its A/B packet. A directory
called coordinator-only supplied no repository access control. The old packet,
mapping and empty forms are removed from the current tree and the case identifiers
are explicitly `RETIRED_FOR_BLINDED_REVIEW` in
`benchmarks/roles/review-packet/RETIREMENT.json`.

**Git history still contains the old map and identifiers. No history purge,
rewrite or force push occurred.** Old reports are historical; their packet
instructions are superseded. The old generator rejects its unsafe invocation.

## Replacement

- Fresh 128-bit opaque case/study identifiers and A/B choices use `secrets`.
  Fixed/deterministic RNG is accepted only through an explicit test-only function
  interface. Test packets cannot count as actual human review.
- Separate explicit reviewer/coordinator destinations must be outside this or any
  detected Git tree, disjoint, nonsymlinked and new. Defaults are unique private
  directories under the operator's local data directory, not the checkout.
- Directories are owner-only 0700, files exclusive-create 0600. Reusing a
  destination fails. Keys never enter reviewer-visible data or CLI status output.
- Reviewer-1 and reviewer-2 get separate outputs. Source-first material excludes
  candidates; candidates use A/B only and omit implementation labels/gold.
- Actual records require assignment, supplied source-first/qualification/
  independence attestations, valid source spans, full provision/field coverage and
  explicit finalization. Coordinator confirmation of the external submission's
  origin is separate from the annotation JSON and binds its digest.
- Partial revisions append; originals remain immutable. Finalized submissions
  cannot change. Adjudicator must differ from both reviewers; each disagreement
  needs a reasoned evidenced decision. Original files are not rewritten.
- Unblinding requires complete accepted independent reviews, resolved disagreements
  where present, and explicit coordinator confirmation. Audit records commit the
  packet and submission hashes. No annotation approval authorizes contract signing.

Filesystem permissions protect against other OS accounts, **not another process
running as the coordinator's user**. Actual reviewer distribution, separate access
accounts/ACLs, secure channels and staged release remain operator responsibilities.
The coordinator can read its key; the audit workflow is not tamper-proof notarization.
No reviewer-facing service or key-retrieval endpoint exists.

## Execution

An engineering-only 30-case packet was generated and inspected in separate private
temporary destinations. Fresh IDs, permissions, separate outputs and absence of
key/implementation labels in visible material passed. No packet/key/submission
from that run is committed. Only sanitized status/counts are retained.
Real study, actual lawyer assignment/submissions, agreement, adjudication and
unblinding are **NOT RUN**. Fictional unit tests exercise states only.

Future operator commands (new private destinations required):

```sh
python -m validation.review_cli prepare --sources /private/approved-sources.json \
  --confirm-approved-sanitized --reviewer-dir /private/new-reviewer-outputs \
  --coordinator-dir /private/new-coordinator
python -m validation.review_cli assign --coordinator-dir /private/new-coordinator \
  --reviewer-1 ACTUAL_CODE_ONE --reviewer-2 ACTUAL_CODE_TWO
python -m validation.review_cli submit --coordinator-dir /private/new-coordinator \
  --record /private/actual-reviewer-submission.json
python -m validation.review_cli confirm-origin --coordinator-dir /private/new-coordinator \
  --record /private/external-origin-confirmation.json
python -m validation.review_cli status --coordinator-dir /private/new-coordinator
```

Adjudication and unblinding are separate commands; unblinding additionally requires
`--confirm-finalized`. Never share the coordinator directory with reviewers.
`.gitignore` covers keys, coordinator folders, actual responses and generated study
files as a second precaution; it cannot retract already committed history.
