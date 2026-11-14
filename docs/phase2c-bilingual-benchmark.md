# Phase 2C bilingual shadow benchmark

Track A is an engineering-authored synthetic shadow benchmark. It is not external
expert validation, a trained-model test or a lawyer-adjudicated legal corpus.
The authoring module and labels were completed separately from prediction
generation and frozen before v2 predictions. After measurement, the corpus is
development-visible; it must not be marketed as a continuing untouched held-out set.

Frozen SHA-256:
`cd7f039bda844d7165b66715369e632ca94ebd634895b20647013a4f19cbb682`.
`author_corpus.py` refuses to overwrite gold. A pinned test checks its digest and
authoring-source reproduction. The runner refuses a corpus/manifest mismatch.
No gold labels were changed after measuring the improved engine.

## Composition

- 30 new fictional documents, 210 individually annotated provisions, 131 role records.
- 10 English, 10 Arabic, 10 genuinely mixed/parallel-language documents.
- 30 explicitly negative provisions, three adversarial instruction cases, 18
  incomplete cases; 101 provisions carry one or more complex/negative tags.
- Sales, confidentiality, brokerage, logistics, leases, consultancy/services,
  employment, corporate transfers, procurement, agency and financial conditions.
- Mixed scripts, English duties with Arabic legal names, attached Arabic role
  prepositions, multiple actors/actions, opposite parallel polarity, different
  periods/amounts/currencies, omitted annexes and unconfirmed events.

Annotation records exact actor/action surfaces, canonical action candidates,
beneficiary/object, modality/polarity, conditionality, trigger, condition,
exception, deadline and source spans. Definitions/aliases have limited engineering
annotation coverage; beneficiary identity-label mismatches remain scored errors.
No original Phase 2B provision text is reused. No real client matter, fabricated
real statute, invented judicial decision or synthetic lawyer approval is included.

## Actual language breakdown

| Group | Legacy actor F1 | V2 actor F1 | Legacy action F1 | V2 action F1 | Legacy beneficiary F1 | V2 beneficiary F1 |
| --- | --- | --- | --- | --- | --- | --- |
| English | .878049 | 1 | .880952 | 1 | 0 | .666667 |
| Arabic | .655172 | 1 | .430380 | .952381 | 0 | .727273 |
| Mixed | .831169 | 1 | .795455 | 1 | 0 | .769231 |

| Group | Legacy full tuple | V2 full tuple | V2 partial tuples |
| --- | --- | --- | --- |
| English | 0/44 | 38/43 = .883721 | 5 |
| Arabic | 0/42 | 37/42 = .880952 | 5 |
| Mixed | 0/46 | 43/46 = .934783 | 3 |

On these selected constructions v2 modality, polarity, conditionality, positive
trigger/condition/exception extraction and deadline association match all gold
labels in each language stratum. That does not establish general bilingual
accuracy. The mixed beneficiary F1 remains .769231, and its three identity-label
mismatches are retained. Detailed category, complex/negative and tag results are
in [results.json](../benchmarks/roles/results.json), including every erroneous slot.

Alignment requires explicit same-number AR/EN version markers. Different numbers,
missing sides and repeated labels are not forcibly paired. Matching lexical
features do not prove equivalent meaning; no contractual language prevails merely
because the engine found a precedence phrase. Divergences remain review candidates.

## Reproduction and future held-out work

```sh
python -m benchmarks.roles.runner --memory --output /tmp/new-role-results.json
python -m benchmarks.clauses.runner --output /tmp/reproduced-phase2b-results.json
```

Outputs must be new paths. The original Phase 2B runner explicitly pins the
legacy mode, preserving its original measurements even when the server environment
enables v2. Neither fixture nor old phase reports/results were overwritten.

For future genuinely unseen material: a separate author/reviewer prepares the
same source/annotation schema, freezes bytes and a sibling `manifest.json` SHA,
then supplies the untouched corpus to `--corpus /path/to/corpus.json`. Do not
generate gold from predictions or amend labels after seeing results. Document any
necessary annotation correction as a new corpus version and retain prior scores.
Use the lawyer protocol for independent expertise and disagreement adjudication.

This development-visible, small, controlled corpus overrepresents recognizable
roles and modal grammar. It is not statistically representative of UAE contracts,
damaged extraction or complex language. No independently held-out/expert legal
accuracy, live Gemini performance or improved legal reasoning is asserted.
