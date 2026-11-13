# Phase 2D beneficiary, Arabic action and object accuracy

Executed comparison: `benchmarks/phase2d/comparison.json`. Gold is the unchanged
Phase 2C engineering corpus SHA
`cd7f039bda844d7165b66715369e632ca94ebd634895b20647013a4f19cbb682`:
30 fictional documents, 210 provisions, 131 roles. This is development-visible,
not independent professional or untouched held-out legal validation.

## Scoring interpretations remain separate

| Measure | Original role_v2 | Precision corrections |
| --- | --- | --- |
| Historical strict beneficiary P/R/F1 | .722222 / .722222 / .722222 | .722222 / .722222 / .722222 |
| Literal beneficiary mention accuracy | 36/36 | 36/36 |
| Definition-backed beneficiary equivalence | 10/10 assessed; 26 unresolved canonical identities | 10/10 assessed; 26 unresolved canonical identities |
| Strict full tuples | 118/131 | 121/131 |
| Separately equivalence-aware full tuples | 128/131 | 131/131 |
| Exact object spans | 114/115 | 115/115 |
| Arabic رد action subset | 1/3 | 3/3 |

Historical strict scores are not overwritten. Ten beneficiary differences were
already a canonical legal name versus its explicit role alias, not ten proven
wrong recipients. The new representation exposes that distinction. The new
`phase2d.source_definition_equivalence.v1` scorer accepts a differing label only
when the source definition independently resolves both to the same document-bound
entity. It records the policy source hash. Twenty-six explicit beneficiary roles
lack a canonical entity definition and remain unresolved for canonical identity;
their exact label matches are not called proven entity equivalence.

Conflicting aliases, different documents/versions, similar name words and schedule
scope do not cause automatic equivalence. Changing scoring interpretation explains
the equivalence-aware gain; it is not a retrospective gold correction or a claim
of improved legal accuracy. Strict surface and strict historical-value scores
remain available beside the new policy, with language/category/complexity strata.

## Targeted corrections

Arabic رد is classified using bounded context/object classes: request/offer
rejection, expense reimbursement, physical-document return, and explicit على
response construction. Mixed object classes or unresolved money-return/refund
readings abstain with alternatives. Exact original action/definition spans remain.
Unseen cost/offer/document combinations, diacritics, nominal الرد, procedural
responses and ambiguous monetary/mixed objects were tested separately.

Disclosure and similar syntax separates direct object from explicit recipient,
destination and subsequent scope phrases. An outsider is not automatically a
contractual beneficiary. Repeated/infinitival prepositions remain ambiguous. Arabic
إلى and adversarial multi-preposition cases are covered. Existing conditions,
exceptions, triggers and deadlines remain separate.

Both runs retain every accepted span: **1,711/1,711** original and **1,823/1,823**
precision-mode spans valid. Each rejects **60/60** unsupported legal/overdue claims.
This comparison uses two claim probes per document, unlike Phase 2C's four; span
counts are not directly comparable with its 1,771-count report. Existing original
evidence-attack and citation/fact/authority tests also remain in the full suite.

Remaining strict errors are the ten retained alias/value-label differences.
Perfect scores on three known Arabic examples or this controlled corpus establish
neither broad Arabic semantics nor enforceability. All outputs remain candidates,
with legal applicability unassessed and human approval pending.
