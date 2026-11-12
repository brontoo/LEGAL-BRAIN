# Phase 2B fictional benchmark

The executed artifact is [results.json](../benchmarks/clauses/results.json), with
all per-document false positives/negatives and timings. The frozen authored
dataset is [fixture.json](../benchmarks/clauses/fixture.json); its explicit
authoring source does not import the analyzer or derive gold predictions.

Fixture SHA-256:
`dbdeb162e1fe5ff2c97f81b0d76496c093af5ad0d0512ce398c35f9ac3fb0e13`.
The builder refuses to overwrite it. Labels remained unchanged after the first
evaluation. Parser repairs addressed nested parentage, attached Arabic reference
prepositions, Arabic comma boundaries and right-lapse extraction, not gold labels.

## Dataset and protocol

20 fictional documents, 120 individually annotated provisions plus 20 document
titles (140 segments). Ten English, nine Arabic and one mixed document cover
marketing, brokerage, property MOU, maintenance, NDA/IP, recruitment, shares,
payment periods, ADGM, DIFC, leases, consultancy, limited agency, renewal,
ambiguous parties, incomplete text and conflicting language/law wording.
Twelve documents are adversarial or incomplete. All 27 taxonomy keys appear in
the authored labels. Important entities, modal-kind obligations, references,
potential-conflict pairs, source offsets and unsupported conclusions are explicit.
No real client documents or fabricated real UAE legislation are present.

The real offline engine receives each full document. No rankings, extracted
labels or answers are substituted. Three annotated unsupported propositions and
four evidence attacks per document test unsupported inference with a valid quote,
legal conclusions with a quote, a fabricated quote and unavailable document version.
All 140 such claims must avoid supported/contradicted verification. All nested
accepted evidence spans must reproduce the exact source/version/clause slice.
These strict integrity gates pass. Extraction scores remain diagnostic and retain
actual mistakes; there is no fabricated perfect-accuracy acceptance gate.

Reproduce from repository root:

```sh
python -m benchmarks.clauses.runner --output /tmp/new-phase2b-results.json
python -m unittest discover -s tests/clause_intelligence -t . -v
```

Output paths must not already exist. No package install, network/model key or
database migration is required. Latency varies by host/load.

## Actual results

| Measure | TP / FP / FN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- |
| Exact segmentation, including titles | 140 / 0 / 0 | 1.000000 | 1.000000 | 1.000000 |
| Multi-label classification | 160 / 8 / 6 | 0.952381 | 0.963855 | 0.958084 |
| Important entity names | 21 / 1 / 0 | 0.954545 | 1.000000 | 0.976744 |
| Clause-level obligation kinds | 56 / 1 / 1 | 0.982456 | 0.982456 | 0.982456 |
| Reference clause/status/ordinal | 12 / 0 / 0 | 1.000000 | 1.000000 | 1.000000 |
| Potential-conflict clause pairs | 3 / 0 / 0 | 1.000000 | 1.000000 | 1.000000 |

Exact category-set accuracy: **129/140 = 0.921429**. Accepted evidence-span
validity: **673/673 = 1.000000**, including repeated spans in nested output.
Unsupported-claim rejection: **140/140 = 1.000000**. Reference resolution accuracy
(intersection/union of annotated reference tuples): **12/12 = 1.000000**.

Classification false-positive rate is **8/3614 = 0.002214**, using absent labels
in the 27-label per-gold-segment universe. Classification false-negative rate is
**6/166 = 0.036145**. Classification false discovery rate is **8/168 = 0.047619**.
These denominators differ intentionally; no undefined negative universe is
invented for open-ended extraction. Other metrics report precision, recall,
false discovery and false-negative rates, with null for undefined denominators.

| Language | Segments | Classification P / R / F1 | Entity P / R | Obligation P / R | References |
| --- | --- | --- | --- | --- | --- |
| English | 70 | 0.940476 / 0.951807 / 0.946108 | 0.909091 / 1.000000 | 1.000000 / 1.000000 | 6/6 |
| Arabic | 63 | 0.960000 / 0.972973 / 0.966443 | 1.000000 / 1.000000 | 1.000000 / 1.000000 | 4/4 |
| Bilingual | 7 | 1.000000 / 1.000000 / 1.000000 | 1.000000 / 1.000000 | 0.666667 / 0.666667 | 2/2 |

Segmentation and accepted evidence-span validity are 1.0 in each group. Arabic-only
potential-conflict precision/recall are **undefined**: no positive pair exists in
that stratum; the bilingual conflict is a separate group. Do not imply the three
positive conflict examples establish broad precision or Arabic conflict coverage.

Recorded end-to-end local processing: mean **18.070292 ms**, p95 **28.523684 ms**,
maximum **32.080154 ms** over 20 documents. This run overlapped frontend checks;
it is not a production-load, WAN, model latency or large-document benchmark.

## Errors and interpretation limits

The artifact retains all errors. Topic words in names (Repair/Invoice/Renewal)
create unwanted category labels. The baseline misses scoped “Neither party may
compete,” some warranty/consent/Arabic forms and a notice plural. A mixed-language
reference sentence containing “notice is required” is classified as a fact rather
than the annotated conditional obligation. Do not infer language equivalence.

The additional extracted `Fictional Nora` signatory is outside the annotated
important-party-name set and therefore counts as an entity FP; this is not proof
the signatory extraction itself is wrong. Gold annotations are engineering-authored,
not independent lawyer adjudications. Obligation scoring uses clause/kind pairs,
not exhaustive actor/action/beneficiary/exception correctness; multiple same-kind
candidates in one clause collapse in that metric. Financial/date/context correctness
is exercised by focused tests but is not presented as a separate corpus accuracy.

This small, development-visible fixture contains simple line boundaries and
limited language constructions. There is no held-out legal corpus, expert inter-
annotator agreement, learned classifier evaluation, proven NLI, enforceability
metric or live Gemini comparison. Perfect integrity/segmentation scores apply
only to these measured cases. They establish neither general legal accuracy nor
improved model reasoning. Model/database validation remains blocked separately.
