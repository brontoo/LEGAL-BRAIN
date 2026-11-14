# Phase 2C qualified-lawyer evaluation protocol

**Track B: NOT RUN.** No genuine qualified-lawyer annotations, signatures or
approval records were supplied. No inter-annotator agreement is reported as a
human result. Engineering arithmetic tests do not substitute for legal reviewers.

## Prepared packet

[review-packet/packet.json](../benchmarks/roles/review-packet/packet.json) contains
30 anonymized case identifiers, fictional source/version/hash, source provisions
and randomized A/B extraction candidates. Both reviewer files are empty and
unattested. The status is `PREPARED_NOT_REVIEWED`, not approved. The coordinator
must withhold `coordinator-only/blinding-map.json` and the engineering gold/results
from reviewers. Formatting differences may reveal the engine; blinding is an
assignment protocol, not a guarantee of indistinguishable outputs.

Recreate in a new directory:

```sh
python -m benchmarks.roles.review_packet --output-dir /tmp/new-lawyer-packet
```

The generator uses only the frozen fictional corpus. It does not invent reviewer
names, qualifications, signatures or approval. It performs no network upload.
There is no lawyer-review API, automatic persistent client store or email sending.

## Independent annotation instructions

The coordinator appoints two actual appropriately qualified legal professionals,
records qualification/independence checks outside the engine, and obtains approved
confidentiality/access arrangements. Anonymous reviewer codes identify real
reviewers; the application does not verify professional registration. Each reviewer
works independently, first reading source without candidates/gold, then assessing
A/B without knowing which is the improved implementation. Preserve both original
assessments before any discussion or adjudication.

For each source provision and each separate obligation, record:

- `case_id`, source unit such as `P-0002:1`, and actor/action/beneficiary/object.
- Modality, polarity, trigger, conditions, exceptions and deadline associations.
- Exact original quotations with document ID/version/hash/clause/offsets; do not translate evidence.
- Interpretation support using the existing six states; legal applicability separately.
- Uncertainty, missing information and contrary contractual evidence.
- Review error severity and approve/reject/needs-review **analysis** decision, with reasons.

Review the identities behind aliases, passive actors, negation, mixed-language
terms, scope, amendment/language precedence, dates and financial entitlement.
Contract wording does not establish event fulfilment, current enforceability or
actual liability. Never record signature approval through this evaluation field.

## Submission format

Each empty template has `reviewer_id: null`, `origin: null`, false qualification/
independence attestations, the frozen `corpus_sha256` and no annotations. Human
submission requires `origin: "human_supplied"`, actual reviewer ID, true supplied
attestations and nonempty annotations. These are attestations, not independent
verification by software. `annotation_fields` lists the accepted fields.

An annotation has `case_id`, `unit_id`, `field`, `label`, optional `notes` and
`evidence` (list of full existing EvidenceSpan objects). Use `unknown`, `not_present`
or `ambiguous` rather than inventing roles. A positive documentary role annotation
requires evidence. The comparison CLI checks known cases and exact spans against
the frozen document/version, rejecting wrong source/version/quote/offsets.

```sh
PYTHONPATH=. python scripts/evaluate_phase2c_reviews.py \
  --first /approved/local/reviewer-one.json \
  --second /approved/local/reviewer-two.json \
  --output /approved/local/new-review-comparison.json
```

No such genuine inputs were available or executed in this phase. Running the
command without reviewer paths creates only a `NOT_RUN` status. Synthetic,
unattested, duplicate-unit, same-reviewer and wrong-corpus submissions are rejected.

## Disagreement and agreement

Compare only common case/unit/field entries and report overlap versus annotation
union. Record both labels and unresolved disagreement; never silently overwrite
one reviewer with the other. Cohen's categorical kappa and observed agreement are
computed **per field**, only for supplied independent annotations. No pooling of
actor names, severity and legal-support labels into a meaningless overall kappa.
All-one-category expected agreement yields undefined kappa, not invented 1.0.
Small samples and coverage must accompany any future statistic.

A distinct adjudicator records a bounded reason, chosen label and validated exact
evidence through `lawyer_review.adjudicate`; both original labels remain in the
record. Adjudication records disagreement resolution, not automatic enforceability
or signature approval. Actual adjudication was NOT RUN.

Machine-observed error priorities and reviewer-adjudicated findings are separate.
Critical documentary errors include wrong actor, reversed negation, lost condition,
ignored contrary evidence and fabricated/wrong-version quotations. Material errors
include missed obligation/exception, wrong beneficiary/trigger and unjustified
entitlement. Ambiguities and secondary topic issues have separate review categories.
This taxonomy prioritizes validation; it is not a UAE legal-risk scoring standard.
