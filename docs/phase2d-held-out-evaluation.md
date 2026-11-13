# Phase 2D external held-out evaluation

**NOT_RUN — INDEPENDENT HELD-OUT DATASET NOT PROVIDED.**

`validation.datasets` implements offline validation/freeze/evaluation; it does not
generate claimed external ground truth. The existing synthetic corpus remains an
engineering regression set. No new synthetic set is described as lawyer-adjudicated.

## Format and provenance

Top-level fields: `version`, `source_provenance`, `annotation_provenance`,
`documents`. Each provenance has `origin`, `reference`, `independent_attested`.
These attestations are supplier records, not software verification of expertise.
Each document has document_id, version, exact text, sha256, language (`en`, `ar`,
`bilingual`) and provisions. Each provision contains start/end/quote/roles. Each
role explicitly provides actor, action, beneficiary, object, modality, polarity,
conditional, trigger, condition, exception and deadline; unknowns are null.

UTF-8 hashes bind source bytes; offsets follow existing Unicode code-point,
end-exclusive conventions. Duplicate IDs, wrong source hashes, altered quotes,
invalid offsets/types/provenance and excessive input fail validation. Source and
annotation provenance remain separate. No client document is loaded automatically.

```sh
python -m validation.dataset_cli freeze --source /private/supplied-corpus.json \
  --destination /private/new-frozen-corpus
python -m validation.dataset_cli evaluate --frozen /private/new-frozen-corpus \
  --output /private/new-evaluation.json
```

Freeze destinations must be outside Git and new. Gold and manifest become
owner-read-only; engine evaluation only reads them and refuses hash/provenance
changes. Output overwrite is refused. The manifest records version, provenance,
configuration and exact development-provision overlap. Detection is literal
trimmed-text hashing, not semantic leakage detection. It cannot prove untouchedness.

Comparison uses exact provision boundary then role ordinal, counts unmatched
predictions, and retains legacy/v2/precision results. Null metrics stay null.
The engine cannot rewrite gold. A human annotation correction requires a new
version and retained old results, not a score-improving silent rewrite.

Unit tests use explicitly fictional manually authored fixtures to test format,
freeze, tampering, overlap and no mutation. Those are not external validation
results. Calling evaluation without an actual supplied corpus returns the NOT_RUN
status above and null metrics. No actual independent corpus was ingested here.
