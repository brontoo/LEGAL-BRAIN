# Legal skills provenance and license review

Reviewed 12 November 2026. LEGAL BRAIN remains the only application target.
External repositories were inspected in temporary reference checkouts, not
vendored as dependencies or loaded at runtime.

| Reference | Reviewed commit | License |
| --- | --- | --- |
| [Corporate skills](https://github.com/w95/awesome-claude-corporate-skills) | `78dbc7c719920610d5b1c60bd13d9bb52d711c7a` | MIT, copyright 2026 Enrike |
| [Awesome Legal NLP](https://github.com/maastrichtlawtech/awesome-legal-nlp) | `397ef5e0fbbe52be13867c43072332376ea4c28f` | MIT, copyright 2022 Antoine Louis |

Repository licenses and the relevant skill directories were inspected. No
additional license files or per-file restrictions were found in the six corporate
skill directories listed below. Other directories have separate notices; none of
those were reused. Copies of both repository notices are retained in
[third-party](third-party/) for conservative attribution.

| New independent workflow | Reviewed corporate skill path(s) | Methodological influence |
| --- | --- | --- |
| `uae-contract-review` | `06-legal-compliance/contract-review/SKILL.md` | Whole-document review, approved positions, clause findings |
| `uae-nda-review` | `06-legal-compliance/nda-triage/SKILL.md` | Confidentiality checklist and workflow triage colors |
| `uae-legal-risk` | `06-legal-compliance/legal-risk-assessment/SKILL.md` | Evidence-supported severity/likelihood and escalation |
| `uae-contract-negotiation` | `12-procurement-supply-chain/contract-negotiation/SKILL.md` | Objectives, alternatives, preferred/fallback positions |
| `uae-corporate-due-diligence` | `01-executive-leadership/ma-due-diligence/SKILL.md`; `02-finance-accounting/dd-checklist/SKILL.md` | Scope, workstream checklist, evidence requests and gaps |

Each manifest records immutable source links. The new text is independently
written for LEGAL BRAIN. No corporate skill body was copied. Foreign data-protection
timelines, NDA duration conventions, liability thresholds and automatic signature
approval language were not adopted as UAE rules. Ordinal risk scoring is an
organizational methodology; it is not a legal requirement or statistical model.

Awesome Legal NLP's README was reviewed for its separation of classification,
retrieval, entailment, summarization and jurisdiction/language-specific resources.
This reinforces keeping task classification separate from source retrieval and
legal verification. No dataset, model weights, linked tool code or benchmark
content was imported. Licenses of linked assets are independent and have not been
cleared for future use.

No new official UAE legal reference text is bundled: applicable propositions must
come through the existing verified knowledge base/official-source research.
Playbooks contain process safeguards, not statements of current law. Support for
ADGM/DIFC means the workflow can identify questions and gaps in those regimes;
it does not assert complete substantive coverage or equivalence with onshore law.
