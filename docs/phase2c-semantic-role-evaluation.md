# Phase 2C semantic-role evaluation

The measured artifact is [results.json](../benchmarks/roles/results.json).
Both modes analyze identical frozen source/labels in one revision. Prediction
code has no document IDs, fixture text, gold labels or scripted answer lookup.
The annotation authoring module imports no extraction implementation.

## Stable matching and denominator rules

Match exact provision start/end, then extraction ordinal inside that provision.
There is no fuzzy/best-match assignment, deduplication or selected-success filtering.
Unmatched/extra records remain slots and false positives. A wrong nonempty field
counts both FP and FN. Missing expected values count FN. Undefined precision is
null, not invented success. Case/whitespace/Arabic diacritics/digits and explicit
party articles/prepositions are normalized only for comparison.

The legacy presentation adapter reads only fields already returned by Phase 2B.
It maps its first action token through a disclosed fixed bilingual vocabulary;
it never searches the rest of a sentence or invents a missing beneficiary.
Legacy full `subject` remains its original value. Improved canonical actions
come from the actual v2 extractor. Results measure these explicit contracts,
not general semantic similarity or lawyer-adjudicated meaning.

A full tuple must match actor, action, beneficiary, object, modality, polarity,
conditionality, trigger, condition, exception and deadline. Partial tuples count
separately. Null/null only counts correct when both records exist and the gold
value is absent. Actor-action and action-beneficiary pairs require both fields.
Field accuracy includes absent-field cases, so positive-only P/R/F1 are also
reported for triggers, conditions, exceptions and deadlines.

## Executed aggregate results

| Field | Legacy TP/FP/FN | Legacy P / R / F1 | V2 TP/FP/FN | V2 P / R / F1 |
| --- | --- | --- | --- | --- |
| Actor | 87 / 8 / 35 | .915789 / .713115 / .801843 | 122 / 0 / 0 | 1 / 1 / 1 |
| Action | 89 / 31 / 42 | .741667 / .679389 / .709163 | 129 / 2 / 2 | .984733 / .984733 / .984733 |
| Beneficiary | 0 / 0 / 36 | undefined / 0 / 0 | 26 / 10 / 10 | .722222 / .722222 / .722222 |
| Trigger | 34 / 3 / 5 | .918919 / .871795 / .894737 | 39 / 0 / 0 | 1 / 1 / 1 |
| Condition | 4 / 2 / 20 | .666667 / .166667 / .266667 | 24 / 0 / 0 | 1 / 1 / 1 |
| Exception | 13 / 3 / 0 | .812500 / 1 / .896552 | 13 / 0 / 0 | 1 / 1 / 1 |
| Deadline | 11 / 0 / 1 | 1 / .916667 / .956522 | 12 / 0 / 0 | 1 / 1 / 1 |

| Accuracy | Legacy | V2 |
| --- | --- | --- |
| Modality | 107/132 = .810606 | 131/131 = 1 |
| Negation/polarity | 107/132 = .810606 | 131/131 = 1 |
| Conditionality | 105/132 = .795455 | 131/131 = 1 |
| Trigger association | 114/132 = .863636 | 131/131 = 1 |
| Exception association | 116/132 = .878788 | 131/131 = 1 |
| Deadline association | 118/132 = .893939 | 131/131 = 1 |
| Actor-action pair | 85/132 = .643939 | 129/131 = .984733 |
| Action-beneficiary pair | 54/132 = .409091 | 119/131 = .908397 |
| Full role tuple | 0/132 = 0 | 118/131 = .900763 |

Legacy has 119 partially matching slots; v2 has 13. Different slot counts reflect
a legacy extra/misaligned record and missing coordinated records. Zero legacy
full tuples is an intentionally strict contract comparison, including the legacy
duplicated action/subject field; it does **not** mean Phase 2B understood nothing.

Pair accuracies include correctly absent fields (for example, a gold obligation
with no beneficiary). They are not positive-link precision/recall. The separate
beneficiary P/R/F1 over 36 annotated positive beneficiaries exposes the remaining
weakness and must accompany action-beneficiary accuracy.

All 30 documents have fewer erroneous slots under v2; none has a higher total.
This document-level count does not erase field-level changes. The artifact retains
both modes' per-slot errors and contract-category/complex/tag strata. No claim is
made that every real-world input improves or that critical errors cannot recur.

## Grounding and rejection

Legacy accepted spans: **1,111/1,111 valid**. V2: **1,771/1,771 valid**, including
nested roles/definitions and repeated references in the serialized reports.
Each mode rejects all **120/120** unsupported interpretation, enforceability,
fabricated-quote and wrong-version attacks from textual verification. Strict
integrity gates fail the evaluation regardless of extraction-score improvements.

V2 structural predicates accept only the exact template
`Source contains {field}: {value}`, with a matching validated field-expression
span and no contrary evidence. Supported fields are actor/action/beneficiary,
trigger/exception/amount. This verifies expression presence, **not** that the
linguistic role, interpretation, performance or legal effect is correct. Unknown
or ambiguous roles cannot supply deterministic role support. Legal conclusions
still require verified authority and qualified review. Existing six states remain.

## Remaining measured errors

The 13 v2 erroneous slots comprise ten beneficiary label mismatches, two Arabic
action meanings and one object boundary. All ten beneficiary differences are
defined legal-name versus gold role-alias labels (e.g. named company versus Buyer).
No post-measurement alias-equivalence adjustment or gold rewrite was used to
manufacture a better score. They are counted as 10 FP and 10 FN but are not ten
proven wrong legal beneficiaries; counsel must review identity/annotation policy.

Arabic `رد الطلب` and `رد المصروفات` remain canonical `return` instead of the
gold `reject` and `reimburse`. One prohibited disclosure object retains “to any
outsider” instead of only “records.” These failures remain visible. Broad unknown
grammar, passive duties, coordination, word numbers and semantic scope exceed the
controlled vocabulary. Machine error priorities are test/review prompts, not
adjudicated legal-risk ratings. Genuine lawyer adjudication remains NOT RUN.
